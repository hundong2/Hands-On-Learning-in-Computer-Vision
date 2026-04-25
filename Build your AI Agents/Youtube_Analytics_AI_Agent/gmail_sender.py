import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import dotenv_values
from datetime import datetime
import os

# Load environment variables
API = dotenv_values('.env')
GMAIL_USER = API.get('GMAIL_USER')
GMAIL_APP_PASSWORD = API.get('GMAIL_APP_PASSWORD')

# 분석 텍스트를 HTML 형식으로 변환하는 함수입니다.
# **굵은 제목**, * 불릿 포인트, | 표, 들여쓰기 코드 등 마크다운 스타일을 HTML 태그로 바꿔줍니다.
# 이메일로 보낼 때 보기 좋게 꾸미기 위해 사용됩니다.
def convert_to_html_markdown(text_content):
    """Convert analysis text to HTML with markdown-like formatting"""
    
    # Split into lines for processing
    lines = text_content.split('\n')
    html_lines = []
    
    for line in lines:
        # Skip the initial report header lines
        if line.startswith('YOUTUBE ANALYTICS REPORT') or line == '=' * 80:
            continue
        if line.startswith('Generated on:') or line.startswith('GEMINI ANALYSIS:'):
            continue
            
        # Convert headers (lines starting with **)
        if line.strip().startswith('**') and line.strip().endswith('**'):
            header_text = line.strip()[2:-2]  # Remove ** from both ends
            html_lines.append(f'<h3 style="color: #1a73e8; margin-top: 20px;">{header_text}</h3>')
            
        # Convert bullet points (lines starting with *)
        elif line.strip().startswith('*'):
            bullet_text = line.strip()[1:].strip()  # Remove * and whitespace
            html_lines.append(f'<li style="margin: 5px 0;">{bullet_text}</li>')
            
        # Convert table headers and rows (lines with |)
        elif '|' in line and line.strip():
            cells = [cell.strip() for cell in line.split('|')]
            if len(cells) > 2:  # Valid table row
                if 'Metric' in line:  # Header row
                    row_html = '<tr style="background-color: #f0f8ff;">'
                    for cell in cells[1:-1]:  # Skip empty first and last
                        row_html += f'<th style="padding: 8px; border: 1px solid #ddd;">{cell}</th>'
                    row_html += '</tr>'
                    html_lines.append('<table style="border-collapse: collapse; margin: 10px 0;">')
                    html_lines.append(row_html)
                elif not line.strip().startswith('|---'):  # Data row (not separator)
                    row_html = '<tr>'
                    for cell in cells[1:-1]:  # Skip empty first and last
                        row_html += f'<td style="padding: 8px; border: 1px solid #ddd;">{cell}</td>'
                    row_html += '</tr>'
                    html_lines.append(row_html)
                    
        # Convert code blocks or preformatted text (indented lines)
        elif line.startswith('    ') or line.startswith('\t'):
            code_text = line.strip()
            html_lines.append(f'<pre style="background-color: #f5f5f5; padding: 10px; margin: 5px 0; border-left: 3px solid #4CAF50;">{code_text}</pre>')
            
        # Regular paragraphs
        elif line.strip():
            html_lines.append(f'<p style="margin: 8px 0; line-height: 1.5;">{line.strip()}</p>')
            
        # Empty lines for spacing
        else:
            html_lines.append('<br>')
    
    # Close any open tables
    html_content = '\n'.join(html_lines)
    if '<table' in html_content and '</table>' not in html_content:
        html_content += '</table>'
    
    return html_content

# 유튜브 분석 보고서를 Gmail로 이메일 전송하는 함수입니다.
# 분석 결과 파일을 읽어 HTML 형식으로 변환한 뒤, 수신자에게 이메일을 보냅니다.
# Gmail 앱 비밀번호(.env 파일에 설정)가 필요합니다.
def send_analysis_email(analysis_filename, recipient_email=None):
    """Send YouTube analysis report via Gmail"""
    
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("❌ Gmail credentials not found in .env file")
        return False
    
    if not recipient_email:
        recipient_email = GMAIL_USER
    
    if not os.path.exists(analysis_filename):
        print(f"❌ Analysis file {analysis_filename} not found")
        return False
    
    try:
        # Read the analysis file
        with open(analysis_filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Convert to HTML
        html_content = convert_to_html_markdown(content)
        
        # Create email
        msg = MIMEMultipart('alternative')
        msg['From'] = GMAIL_USER
        msg['To'] = recipient_email
        msg['Subject'] = f"📊 YouTube Analytics Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Create HTML email body
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ padding: 20px; background-color: #ffffff; }}
                .footer {{ background-color: #f8f9fa; padding: 15px; text-align: center; font-size: 12px; color: #666; border-radius: 0 0 8px 8px; }}
            </style>
        </head>
        <body>
            <div style="max-width: 800px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px;">
                <div class="header">
                    <h1 style="margin: 0;">🎥 YouTube Analytics Report</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
                </div>
                <div class="content">
                    {html_content}
                </div>
                <div class="footer">
                    <p>📈 Automated YouTube Analytics System | 🤖 AI-Powered Insights</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Attach HTML
        html_part = MIMEText(html_body, 'html')
        msg.attach(html_part)
        
        # Send email
        print("📧 Sending analysis report...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, recipient_email, msg.as_string())
        server.quit()
        
        print(f"✅ Email sent successfully to {recipient_email}")
        return True
        
    except smtplib.SMTPAuthenticationError:
        print("❌ Gmail authentication failed! Use App Password from: https://myaccount.google.com/apppasswords")
        return False
    except Exception as e:
        print(f"❌ Error sending email: {str(e)}")
        return False

# Gmail 서버에 실제로 접속이 되는지 연결 테스트를 하는 함수입니다.
# 이메일 전송 전에 인증 정보가 올바른지 미리 확인할 때 사용합니다.
def test_gmail():
    """Test Gmail connection"""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("❌ Add GMAIL_USER and GMAIL_APP_PASSWORD to your .env file")
        return False
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.quit()
        print(f"✅ Gmail connection successful for {GMAIL_USER}")
        return True
    except Exception as e:
        print(f"❌ Gmail connection failed: {str(e)}")
        return False