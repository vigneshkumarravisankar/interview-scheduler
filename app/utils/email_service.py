"""
Email service for sending offer letters using Gmail API
"""
import os
import base64
import mimetypes
import time
from datetime import datetime
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
import json
from typing import List, Optional, Dict, Any
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from fastapi import BackgroundTasks

from app.utils.oauth_manager import OAuthManager
from app.schemas.final_candidate_schema import FinalCandidateResponse
from app.utils.pdf_generator import generate_offer_letter_pdf


def send_email(to_emails: List[str], subject: str, html_content: str, 
               cc: List[str] = None, bcc: List[str] = None) -> bool:
    """
    Send a generic email using the Gmail API
    
    Args:
        to_emails: List of recipient email addresses
        subject: Email subject
        html_content: HTML content of the email
        cc: List of CC email addresses (optional)
        bcc: List of BCC email addresses (optional)
        
    Returns:
        True if the email was scheduled to be sent
    """
    try:
        # Initialize OAuth manager
        oauth_manager = EmailService.get_oauth_manager()
        creds = oauth_manager.get_credentials()
        service = build('gmail', 'v1', credentials=creds)
        
        # Create message
        message = MIMEMultipart('alternative')
        message['Subject'] = subject
        message['From'] = "me"  # Special value for authenticated user
        message['To'] = ", ".join(to_emails)
        
        if cc:
            message['Cc'] = ", ".join(cc)
        
        if bcc:
            message['Bcc'] = ", ".join(bcc)
        
        # Create plain text version by stripping HTML
        from html.parser import HTMLParser

        class MLStripper(HTMLParser):
            def __init__(self):
                super().__init__()
                self.reset()
                self.strict = False
                self.convert_charrefs = True
                self.text = []
            
            def handle_data(self, d):
                self.text.append(d)
            
            def get_data(self):
                return ''.join(self.text)

        def strip_tags(html):
            s = MLStripper()
            s.feed(html)
            return s.get_data()
        
        plain_text = strip_tags(html_content)
        
        # Attach parts
        part1 = MIMEText(plain_text, 'plain')
        part2 = MIMEText(html_content, 'html')
        
        message.attach(part1)
        message.attach(part2)
        
        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        # Send message
        EmailService.send_message(service, "me", {'raw': raw_message})
        return True
        
    except Exception as e:
        print(f"Error sending email: {e}")
        import traceback
        traceback.print_exc()
        return False


class EmailService:
    """Email service for sending offer letters"""

    # Singleton instance of OAuth manager
    _oauth_manager = None
    
    @classmethod
    def get_oauth_manager(cls):
        """Get the OAuth manager instance"""
        if cls._oauth_manager is None:
            # Use OAuthManager's default paths
            cls._oauth_manager = OAuthManager()
            print("OAuth manager initialized for email service")
        return cls._oauth_manager
    
    @staticmethod
    def create_offer_letter_html(candidate: FinalCandidateResponse, job_title: str, company_name: str = "Our Company", 
                                 hr_name: str = "HR Representative", hr_email: str = "hr@company.com") -> str:
        """Create HTML content for offer letter email"""
        # Current date in format: June 18, 2025
        current_date = datetime.now().strftime("%B %d, %Y")
        
        offer_letter_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Job Offer: {job_title} Position</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    margin: 0;
                    padding: 0;
                    color: #333;
                    background-color: #f9f9f9;
                }}
                .container {{
                    max-width: 650px;
                    margin: 0 auto;
                    background-color: #ffffff;
                    padding: 30px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                    border-bottom: 2px solid #2c5282;
                    padding-bottom: 20px;
                }}
                .logo {{
                    max-height: 80px;
                    margin-bottom: 15px;
                }}
                .header h1 {{
                    color: #2c5282;
                    margin-bottom: 10px;
                    font-weight: 600;
                }}
                .content {{
                    margin-bottom: 30px;
                }}
                .signature {{
                    margin-top: 40px;
                    border-top: 1px solid #eaeaea;
                    padding-top: 20px;
                }}
                .highlight {{
                    font-weight: bold;
                    color: #2c5282;
                }}
                .details-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }}
                .details-table td {{
                    padding: 10px;
                    border-bottom: 1px solid #eaeaea;
                }}
                .details-table td:first-child {{
                    width: 150px;
                    font-weight: bold;
                    color: #4a5568;
                }}
                .cta-button {{
                    display: inline-block;
                    background-color: #2c5282;
                    color: white;
                    padding: 12px 25px;
                    text-decoration: none;
                    border-radius: 4px;
                    font-weight: 600;
                    margin: 20px 0;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 40px;
                    color: #718096;
                    font-size: 0.9em;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{company_name}</h1>
                    <p>Job Offer Letter | {current_date}</p>
                </div>
                
                <div class="content">
                    <p>Dear <span class="highlight">{candidate.candidate_name}</span>,</p>
                    
                    <p>We are delighted to offer you the position of <span class="highlight">{job_title}</span> at {company_name}. 
                    After thorough consideration of your impressive qualifications, experience, and performance throughout 
                    the interview process, our team believes you would make an exceptional addition to our organization.</p>
                    
                    <p>Please find attached to this email a formal offer letter with complete details. Here's a summary of the offer:</p>
                    
                    <table class="details-table">
                        <tr>
                            <td>Position:</td>
                            <td>{job_title}</td>
                        </tr>
                        <tr>
                            <td>Compensation:</td>
                            <td>{candidate.compensation_offered}</td>
                        </tr>
                        <tr>
                            <td>Start Date:</td>
                            <td>To be determined upon acceptance</td>
                        </tr>
                    </table>
                    
                    <p>This offer includes our complete benefits package, including health insurance, retirement benefits, 
                    paid time off, and professional development opportunities. Further details can be found in the attached offer letter.</p>
                    
                    <p>To accept this offer, please:</p>
                    <ol>
                        <li>Review the attached offer letter thoroughly</li>
                        <li>Sign the acceptance section of the offer letter</li>
                        <li>Return the signed document to us within 7 days</li>
                    </ol>
                    
                    <p>Should you have any questions or require clarification on any aspect of this offer, please don't 
                    hesitate to contact {hr_name} directly at <a href="mailto:{hr_email}">{hr_email}</a>.</p>
                </div>
                
                <div class="signature">
                    <p>Sincerely,</p>
                    <p><b>{hr_name}</b><br>
                    Human Resources Department<br>
                    {company_name}<br>
                    <a href="mailto:{hr_email}">{hr_email}</a></p>
                </div>
                
                <div class="footer">
                    <p>This offer is contingent upon completion of any background checks or other pre-employment requirements 
                    as specified in the attached offer letter.</p>
                    <p>© {datetime.now().year} {company_name}. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return offer_letter_html

    @staticmethod
    def create_message_with_attachments(sender: str, to: str, subject: str, 
                                         message_text: str, html_content: Optional[str] = None,
                                         file_paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Create a message for an email with attachments
        
        Args:
            sender: Email address of the sender
            to: Email address of the receiver
            subject: The subject of the email message
            message_text: The plain text of the email message
            html_content: The HTML content of the email message (optional)
            file_paths: List of paths to files to be attached (optional)
            
        Returns:
            A dictionary containing a base64url encoded email object
        """
        message = MIMEMultipart('alternative')
        message['To'] = to
        message['From'] = sender
        message['Subject'] = subject
        message['Date'] = formatdate(localtime=True)
        
        # Add plain text and HTML parts
        part1 = MIMEText(message_text, 'plain')
        message.attach(part1)
        
        if html_content:
            part2 = MIMEText(html_content, 'html')
            message.attach(part2)
        
        # Add attachments if any
        if file_paths:
            # Convert the message to a multipart/mixed message to support attachments
            mixed_message = MIMEMultipart('mixed')
            # Set the headers from the original message
            for key, value in message.items():
                mixed_message[key] = value
            
            # Attach the body
            mixed_message.attach(message)
            
            # Now the mixed_message is our main message
            message = mixed_message
            
            # Add attachments
            for file_path in file_paths:
                if not os.path.exists(file_path):
                    print(f"Warning: Attachment file not found: {file_path}")
                    continue
                    
                content_type, encoding = mimetypes.guess_type(file_path)
                
                if content_type is None or encoding is not None:
                    content_type = 'application/octet-stream'
                
                main_type, sub_type = content_type.split('/', 1)
                
                if main_type == 'text':
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
                        attachment = MIMEText(file.read())
                elif main_type == 'image':
                    with open(file_path, 'rb') as file:
                        attachment = MIMEImage(file.read(), _subtype=sub_type)
                elif main_type == 'audio':
                    with open(file_path, 'rb') as file:
                        attachment = MIMEAudio(file.read(), _subtype=sub_type)
                else:
                    # Handle all other file types as binary
                    with open(file_path, 'rb') as file:
                        attachment = MIMEBase(main_type, sub_type)
                        attachment.set_payload(file.read())
                        # Encode the payload using Base64
                        import email.encoders
                        email.encoders.encode_base64(attachment)
                
                filename = os.path.basename(file_path)
                attachment.add_header('Content-Disposition', 'attachment', filename=filename)
                message.attach(attachment)
        
        # Encode message for sending
        return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}
    
    @staticmethod
    def send_message(service, user_id: str, message: Dict[str, Any]):
        """
        Send an email message
        
        Args:
            service: Authorized Gmail API service instance
            user_id: User's email address. The special value "me" can be used to
                    indicate the authenticated user
            message: Message to be sent
            
        Returns:
            Sent Message ID
        """
        try:
            sent_message = service.users().messages().send(
                userId=user_id, body=message).execute()
            print(f'Message Id: {sent_message["id"]}')
            return sent_message
        except HttpError as error:
            print(f'An error occurred: {error}')
            raise
    
    @classmethod
    async def send_offer_letter(cls, candidate: FinalCandidateResponse, job_title: str, 
                           background_tasks: BackgroundTasks, company_name: str = "YourCompany, Inc.", 
                           hr_name: str = "HR Representative", hr_email: str = "hr@company.com") -> bool:
        """
        Send offer letter to a candidate with PDF attachment
        
        Args:
            candidate: Candidate information
            job_title: Job title
            background_tasks: FastAPI background tasks
            company_name: Name of the company
            hr_name: Name of the HR representative
            hr_email: Email of the HR representative
            
        Returns:
            True if the email was scheduled to be sent
        """
        # This will be run in the background
        def _send_offer_task(candidate, job_title, company_name, hr_name, hr_email):
            try:
                start_time = time.time()
                print(f"Starting offer letter email process for {candidate.candidate_name}")
                
                # Get Gmail credentials
                oauth_manager = cls.get_oauth_manager()
                creds = oauth_manager.get_credentials()
                service = build('gmail', 'v1', credentials=creds)
                print("Gmail API service built successfully")
                
                # Prepare email content
                sender_email = "me"  # Special value for authenticated user
                recipient_email = candidate.email if hasattr(candidate, 'email') and candidate.email else "candidate@example.com"
                
                subject = f"Job Offer: {job_title} Position at {company_name}"
                
                # Create plain text version of the email
                plain_text = f"""
                Dear {candidate.candidate_name},
                
                We are delighted to offer you the position of {job_title} at {company_name}.
                
                After thorough consideration of your qualifications and experience, we believe you would make an exceptional addition to our team.
                
                The details of our offer:
                - Position: {job_title}
                - Compensation: {candidate.compensation_offered}
                - Start Date: To be determined upon acceptance
                
                Please find attached our formal offer letter with all details. To accept this offer:
                1. Review the attached offer letter thoroughly
                2. Sign and return the offer letter within 7 days
                
                If you have any questions, please contact {hr_name} at {hr_email}.
                
                Sincerely,
                {hr_name}
                Human Resources Department
                {company_name}
                {hr_email}
                """
                
                # Create HTML version
                html_content = cls.create_offer_letter_html(
                    candidate=candidate, 
                    job_title=job_title, 
                    company_name=company_name, 
                    hr_name=hr_name,
                    hr_email=hr_email
                )
                
                # Generate PDF offer letter
                print("Generating PDF offer letter...")
                pdf_path = generate_offer_letter_pdf(
                    candidate_name=candidate.candidate_name,
                    job_title=job_title,
                    compensation=candidate.compensation_offered,
                    company_name=company_name,
                    hr_name=hr_name
                )
                
                # Prepare attachments
                attachments = []
                if pdf_path and os.path.exists(pdf_path):
                    print(f"PDF generated successfully at {pdf_path}")
                    attachments.append(pdf_path)
                else:
                    print("⚠️ Warning: PDF generation failed, sending email without attachment")
                
                # Create and send the message
                print(f"Creating email message with {len(attachments)} attachments")
                message = cls.create_message_with_attachments(
                    sender=sender_email,
                    to=recipient_email,
                    subject=subject,
                    message_text=plain_text,
                    html_content=html_content,
                    file_paths=attachments
                )
                
                # Send the message
                print("Sending email...")
                cls.send_message(service, "me", message)
                
                # Clean up temporary PDF file
                if pdf_path and os.path.exists(pdf_path):
                    try:
                        os.unlink(pdf_path)
                        print("Temporary PDF file deleted")
                    except Exception as pdf_e:
                        print(f"Warning: Could not delete temporary PDF file: {pdf_e}")
                
                elapsed_time = time.time() - start_time
                print(f"✅ Offer letter sent to {candidate.candidate_name} in {elapsed_time:.2f} seconds")
                return True
            
            except Exception as e:
                print(f"❌ Failed to send offer letter: {e}")
                import traceback
                traceback.print_exc()
                return False
        
        # Add task to background tasks queue
        background_tasks.add_task(_send_offer_task, candidate, job_title, company_name, hr_name, hr_email)
        return True
