import os
import streamlit as st
from PIL import Image
from io import BytesIO
import zipfile
from pathlib import Path

# 이미지를 WebP 형식으로 변환하고 파일 크기를 최적화하는 함수입니다.
# 품질(quality)을 단계적으로 낮추고, 그래도 목표 크기를 초과하면 이미지 해상도를 줄입니다.
# 반환값: (변환된 이미지 바이트, 최종 크기(KB), 사용된 품질, 크기 조정 여부)
def process_image(image_data, filename, max_quality, min_quality, target_kb, max_kb):
    try:
        img = Image.open(BytesIO(image_data))
        original_size = len(image_data)
        original_width, original_height = img.size
        
        # Convert RGBA to RGB if needed (WebP handles alpha channel differently)
        if img.mode == 'RGBA':
            # Create a white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            # Paste the image using alpha as mask
            background.paste(img, mask=img.split()[3])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
            
        quality = max_quality
        resized = False
        
        # Phase 1: Try with just quality reduction
        buffer = BytesIO()
        img.save(buffer, 'WEBP', quality=quality)
        final_size = buffer.tell()
        
        # If already below target size, we're done
        if final_size <= target_kb * 1024:
            buffer.seek(0)
            return buffer.read(), final_size / 1024, quality, resized
            
        # Try reducing quality incrementally
        for quality in range(max_quality, min_quality - 1, -5):
            buffer = BytesIO()
            img.save(buffer, 'WEBP', quality=quality)
            final_size = buffer.tell()
            
            if final_size <= target_kb * 1024:
                buffer.seek(0)
                return buffer.read(), final_size / 1024, quality, resized
        
        # Phase 2: If we still haven't reached target size, try resizing
        if final_size > max_kb * 1024:
            resized = True
            resize_factor = 0.9  # Start with 90% of original size
            
            while resize_factor > 0.1:
                new_width = int(original_width * resize_factor)
                new_height = int(original_height * resize_factor)
                
                # Ensure dimensions are at least 1 pixel
                new_width = max(1, new_width)
                new_height = max(1, new_height)
                
                resized_img = img.resize((new_width, new_height), Image.LANCZOS)
                
                # Try with minimum quality since we're already resizing
                buffer = BytesIO()
                resized_img.save(buffer, 'WEBP', quality=min_quality)
                final_size = buffer.tell()
                
                if final_size <= max_kb * 1024:
                    buffer.seek(0)
                    return buffer.read(), final_size / 1024, min_quality, resized
                
                resize_factor *= 0.8  # More aggressive reduction
                
                # Safety exit condition
                if new_width <= 50 or new_height <= 50:
                    # If we can't get it small enough, just return what we have
                    buffer.seek(0)
                    return buffer.read(), final_size / 1024, min_quality, resized
        
        # If we couldn't hit the target size but did our best, return what we have
        buffer.seek(0)
        return buffer.read(), final_size / 1024, quality, resized
        
    except Exception as e:
        raise Exception(f"Failed to process image {filename}: {str(e)}")

# 앱의 상태를 초기화(리셋)하는 함수입니다.
# Streamlit의 세션 상태(session_state)에 저장된 모든 데이터를 삭제하고 앱을 처음 상태로 되돌립니다.
def reset_app():
    # Clear all session state
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    # Ensure file uploader is cleared
    st.experimental_rerun()

# Streamlit 웹 앱의 메인 실행 함수입니다.
# 사용자가 이미지 파일을 업로드하면 WebP 형식으로 변환 및 최적화하고,
# 결과를 ZIP 파일로 묶어 다운로드할 수 있게 해줍니다.
def main():
    st.set_page_config(page_title="Smart Image Converter", page_icon="🖼️")
    
    st.title("🖼️ Smart Image Converter")
    st.markdown("""
    ### Optimize images for web use
    Convert to WebP format with automatic size optimization (100KB target / 200KB max)
    """)

    # Initialize session state for storing results
    if 'results' not in st.session_state:
        st.session_state.results = None
        st.session_state.zip_buffer = None
        st.session_state.total_original = 0
        st.session_state.total_optimized = 0
        st.session_state.has_processed = False

    with st.sidebar:
        st.header("Settings ⚙️")
        max_quality = st.slider("Maximum Quality", 40, 95, 85)
        min_quality = st.slider("Minimum Quality", 10, 75, 40)
        
        # Ensure min_quality is less than max_quality
        if min_quality >= max_quality:
            st.warning("Minimum quality should be less than maximum quality")
            min_quality = max_quality - 5
            
        target_kb = st.number_input("Target Size (KB)", 50, 150, 100)
        max_kb = st.number_input("Maximum Size (KB)", 150, 300, 200)
        
        # Ensure max_kb is greater than target_kb
        if max_kb <= target_kb:
            st.warning("Maximum size should be greater than target size")
            max_kb = target_kb + 50
        
        # Add the reset button to sidebar
        if st.button("🔄 Reset App"):
            reset_app()

    # Only show file uploader if we haven't processed files already
    if not st.session_state.has_processed:
        uploaded_files = st.file_uploader(
            "Upload images or a folder of images", 
            type=["jpg", "jpeg", "png", "bmp", "tiff", "webp"],
            accept_multiple_files=True
        )

        if uploaded_files:
            start_button = st.button("✨ Start Conversion")
            if start_button:
                results = []
                total_original = 0
                total_optimized = 0
                failed_count = 0
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Create a BytesIO buffer for the zip file
                zip_buffer = BytesIO()
                
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for i, uploaded_file in enumerate(uploaded_files):
                        current_progress = (i) / len(uploaded_files)
                        progress_bar.progress(current_progress)
                        status_text.text(f"Processing {i+1}/{len(uploaded_files)}: {uploaded_file.name}")
                        
                        try:
                            # Get image data
                            image_data = uploaded_file.getvalue()
                            original_size = len(image_data) / 1024
                            
                            # Process the image
                            processed, size_kb, quality_used, resized = process_image(
                                image_data,
                                uploaded_file.name,
                                max_quality,
                                min_quality,
                                target_kb,
                                max_kb
                            )
                            
                            # Add to ZIP
                            output_filename = f"{Path(uploaded_file.name).stem}.webp"
                            zipf.writestr(output_filename, processed)
                            
                            # Update totals
                            total_original += original_size
                            total_optimized += size_kb
                            
                            # Add to results
                            savings_pct = (1 - size_kb / original_size) * 100 if original_size > 0 else 0
                            results.append({
                                "filename": uploaded_file.name,
                                "original": f"{original_size:.1f}KB",
                                "optimized": f"{size_kb:.1f}KB",
                                "quality": quality_used,
                                "resized": "✓" if resized else "✗",
                                "savings": f"{savings_pct:.1f}%"
                            })
                            
                        except Exception as e:
                            failed_count += 1
                            st.error(f"Error processing {uploaded_file.name}: {str(e)}")
                    
                    # Complete the progress bar
                    progress_bar.progress(1.0)
                    status_text.text("Processing complete!")
                
                # Store results in session state
                st.session_state.results = results
                st.session_state.zip_buffer = zip_buffer.getvalue()
                st.session_state.total_original = total_original
                st.session_state.total_optimized = total_optimized
                st.session_state.failed_count = failed_count
                st.session_state.has_processed = True
                
                # Force a rerun to show results page
                st.experimental_rerun()
    
    # Results display (shown after processing)
    if st.session_state.has_processed and st.session_state.results:
        # Create a container for results
        with st.container():
            st.success(f"✅ Processed {len(st.session_state.results)} images successfully!" + 
                      (f" ({st.session_state.failed_count} failed)" if st.session_state.failed_count > 0 else ""))
            
            st.dataframe(
                data=st.session_state.results,
                column_config={
                    "filename": "File",
                    "original": "Original Size",
                    "optimized": "Optimized Size",
                    "quality": "Quality Used",
                    "resized": "Resized",
                    "savings": "Savings"
                },
                use_container_width=True
            )

            # Download section
            st.markdown("---")
            st.subheader("Download Results")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Original Size", f"{st.session_state.total_original:.1f}KB")
            with col2:
                st.metric("Total Optimized Size", f"{st.session_state.total_optimized:.1f}KB")
            with col3:
                savings_percent = (1 - st.session_state.total_optimized / st.session_state.total_original) * 100 if st.session_state.total_original > 0 else 0
                st.metric("Size Reduction", f"{savings_percent:.1f}%")

            st.download_button(
                label="📥 Download All WebP Images",
                data=st.session_state.zip_buffer,
                file_name="converted_images.zip",
                mime="application/zip"
            )
            
            # Add a "Convert More Images" button
            if st.button("🔄 Convert More Images"):
                reset_app()
    
    # If no images processed successfully
    elif st.session_state.has_processed and not st.session_state.results:
        st.warning("No images were successfully processed.")
        if st.button("Try Again"):
            reset_app()

if __name__ == "__main__":
    main()