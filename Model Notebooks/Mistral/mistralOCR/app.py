import streamlit as st
import base64
import tempfile
import os
from mistralai import Mistral
from PIL import Image
import io

# PDF 파일을 Mistral API 서버에 업로드하고, 처리에 사용할 임시 URL을 받아오는 함수입니다.
# 파일을 임시 폴더에 저장한 뒤 업로드하고, 처리가 끝나면 임시 파일을 삭제합니다.
def upload_pdf(client, content, filename):
    """
    Uploads a PDF to Mistral's API and retrieves a signed URL for processing.
    
    Args:
        client (Mistral): Mistral API client instance.
        content (bytes): The content of the PDF file.
        filename (str): The name of the PDF file.

    Returns:
        str: Signed URL for the uploaded PDF.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = os.path.join(temp_dir, filename)
        
        with open(temp_path, "wb") as tmp:
            tmp.write(content)
        
        try:
            with open(temp_path, "rb") as file_obj:
                file_upload = client.files.upload(
                    file={"file_name": filename, "content": file_obj},
                    purpose="ocr"
                )
            
            signed_url = client.files.get_signed_url(file_id=file_upload.id)
            return signed_url.url
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

# Mistral의 OCR API를 사용해 문서(PDF 또는 이미지)에서 텍스트를 추출하는 함수입니다.
# OCR(광학 문자 인식)이란 이미지나 PDF 속의 글자를 컴퓨터가 읽을 수 있는 텍스트로 변환하는 기술입니다.
def process_ocr(client, document_source):
    """
    Processes a document using Mistral's OCR API.

    Args:
        client (Mistral): Mistral API client instance.
        document_source (dict): The source of the document (URL or image).

    Returns:
        OCRResponse: The response from Mistral's OCR API.
    """
    return client.ocr.process(
        model="mistral-ocr-latest",
        document=document_source,
        include_image_base64=True
    )

# PDF 파일을 Streamlit 웹 앱 화면 안에 iframe으로 보여주는 함수입니다.
# PDF를 base64 문자열로 인코딩해서 브라우저에서 바로 미리보기가 가능하도록 합니다.
def display_pdf(file):
    """
    Displays a PDF in Streamlit using an iframe.

    Args:
        file (str): Path to the PDF file.
    """
    with open(file, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode("utf-8")
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="700" height="1000" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)

# Streamlit 웹 앱의 메인 실행 함수입니다.
# 사용자가 API 키를 입력하고 URL/PDF/이미지를 올리면, OCR로 텍스트를 추출해 화면에 보여줍니다.
# 추출된 텍스트는 .txt 또는 .md 파일로 다운로드할 수 있습니다.
def main():
    st.set_page_config(page_title="Mistral OCR Processor", layout="wide")
    
    # Sidebar: Authentication for Mistral API
    api_key = st.sidebar.text_input("Mistral API Key", type="password")
    
    if not api_key:
        st.warning("Enter API key to continue")
        return
    
    # Initialize Mistral API client
    client = Mistral(api_key=api_key)
    
    # Main app interface
    st.header("Mistral OCR Processor")
    
    # Input method selection: URL, PDF Upload, or Image Upload
    input_method = st.radio("Select Input Type:", ["URL", "PDF Upload", "Image Upload"])
    
    document_source = None
    preview_content = None
    content_type = None
    
    if input_method == "URL":
        # Handle document URL input
        url = st.text_input("Document URL:")
        if url:
            document_source = {
                "type": "document_url",
                "document_url": url
            }
            preview_content = url
            content_type = "url"
    
    elif input_method == "PDF Upload":
        # Handle PDF file upload
        uploaded_file = st.file_uploader("Choose PDF file", type=["pdf"])
        if uploaded_file:
            content = uploaded_file.read()
            preview_content = uploaded_file
            
            # Save the uploaded PDF temporarily for display purposes
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(content)
                pdf_path = tmp.name
            
            display_pdf(pdf_path)  # Display the uploaded PDF
            
            # Prepare document source for OCR processing
            document_source = {
                "type": "document_url",
                "document_url": upload_pdf(client, content, uploaded_file.name)
            }
            content_type = "pdf"
    
    elif input_method == "Image Upload":
        # Handle image file upload
        uploaded_image = st.file_uploader("Choose Image file", type=["png", "jpg", "jpeg"])
        if uploaded_image:
            # Display the uploaded image
            image = Image.open(uploaded_image)
            st.image(image, caption="Uploaded Image")
            
            # Convert image to base64
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            # Prepare document source for OCR processing
            document_source = {
                "type": "image_url",
                "image_url": f"data:image/png;base64,{img_str}"
            }
            content_type = "image"
    
    if document_source and st.button("Process Document"):
        # Process the document when the user clicks the button
        with st.spinner("Extracting content..."):
            try:
                ocr_response = process_ocr(client, document_source)
                
                if ocr_response and ocr_response.pages:
                    # Combine extracted text from all pages into one string
                    extracted_content = "\n\n".join(
                        [f"**Page {i+1}**\n{page.markdown}" 
                         for i, page in enumerate(ocr_response.pages)]
                    )
                    
                    # Display extracted content in Markdown format
                    st.subheader("Extracted Content")
                    st.markdown(extracted_content)
                    
                    # Prepare plain text version
                    plain_text_content = "\n\n".join(
                        [f"Page {i+1}\n{page.markdown}" 
                         for i, page in enumerate(ocr_response.pages)]
                    )
                    
                    # Add download buttons for both text and Markdown formats
                    col1, col2 = st.columns(2)
                    with col1:
                        st.download_button(
                            label="Download as Text",
                            data=plain_text_content,
                            file_name="extracted_content.txt",
                            mime="text/plain"
                        )
                    with col2:
                        st.download_button(
                            label="Download as Markdown",
                            data=extracted_content,
                            file_name="extracted_content.md",
                            mime="text/markdown"
                        )
                    
                    # Optional: Show raw response for debugging purposes
                    with st.expander("Raw API Response"):
                        st.json(ocr_response.model_dump())
                
                else:
                    st.warning("No content extracted.")
            
            except Exception as e:
                # Display an error message if processing fails
                st.error(f"Processing error: {str(e)}")

if __name__ == "__main__":
    main()
