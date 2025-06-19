"""
Email notification service for interview scheduling
"""
import os
import smtplib
import uuid
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Store for tracking responses
RESPONSE_FILE = "interview_responses.json"

# Add alias function for backward compatibility
def send_interview_invitation(
    recipient_email: str,
    start_time: str,
    end_time: str,
    meet_link: Optional[str] = None,
    event_id: Optional[str] = None,
    interviewer_name: Optional[str] = None,
    candidate_name: Optional[str] = None,
    job_title: Optional[str] = None,
    additional_note: Optional[str] = None,
    interviewer_email: Optional[str] = None
) -> bool:
    """
    Alias for send_interview_notification for backward compatibility
    
    This function simply forwards all parameters to send_interview_notification
    """
    return send_interview_notification(
        recipient_email=recipient_email,
        start_time=start_time,
        end_time=end_time,
        meet_link=meet_link,
        event_id=event_id,
        interviewer_name=interviewer_name,
        candidate_name=candidate_name,
        job_title=job_title,
        additional_note=additional_note,
        interviewer_email=interviewer_email
    )

import os
import smtplib
import uuid
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Store for tracking responses
RESPONSE_FILE = "interview_responses.json"

def load_responses() -> Dict[str, Dict[str, Any]]:
    """Load response tracking data from file"""
    if os.path.exists(RESPONSE_FILE):
        with open(RESPONSE_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print(f"Error decoding {RESPONSE_FILE}, returning empty dict")
                return {}
    return {}

def save_response(response_id: str, data: Dict[str, Any]) -> None:
    """Save response tracking data to file"""
    responses = load_responses()
    responses[response_id] = data
    try:
        with open(RESPONSE_FILE, 'w') as f:
            json.dump(responses, f, indent=2)
    except Exception as e:
        print(f"Error saving to {RESPONSE_FILE}: {e}")

def generate_response_id() -> str:
    """Generate a unique ID for tracking responses"""
    return str(uuid.uuid4())

def send_interview_notification(
    recipient_email: str,
    start_time: str,
    end_time: str,
    meet_link: Optional[str] = None,
    event_id: Optional[str] = None,
    interviewer_name: Optional[str] = None,
    candidate_name: Optional[str] = None,
    job_title: Optional[str] = None,
    additional_note: Optional[str] = None,
    interviewer_email: Optional[str] = None  # Added parameter for interviewer email
) -> bool:
    """
    Send email notification about the scheduled interview with accept/decline buttons
    
    Args:
        recipient_email: Email address of the recipient
        start_time: Start time of the interview (ISO format)
        end_time: End time of the interview (ISO format)
        meet_link: Google Meet link (optional)
        event_id: Calendar event ID (optional)
        interviewer_name: Name of the interviewer (optional)
        candidate_name: Name of the candidate (optional)
        job_title: Job title (optional)
        additional_note: Additional information to include in the email (optional)
        interviewer_email: Email address of the interviewer (optional)
    
    Returns:
        True if the email was sent successfully, False otherwise
    """
    # Email configuration
    sender_email = os.environ.get("EMAIL_SENDER", "rrvigneshkumar2002@gmail.com")
    password = os.environ.get("EMAIL_PASSWORD")

    if not password:
        print("⚠️ Email password not found in environment variables. Email not sent.")
        return False

    # Generate unique response IDs for this recipient
    accept_id = generate_response_id()
    decline_id = generate_response_id()

    # Save initial response tracking data
    response_data = {
        "recipient": recipient_email,
        "start_time": start_time,
        "end_time": end_time,
        "meet_link": meet_link,
        "event_id": event_id,
        "interviewer_name": interviewer_name,
        "interviewer_email": interviewer_email,
        "candidate_name": candidate_name,
        "job_title": job_title,
        "additional_note": additional_note,
        "sent_time": datetime.now().isoformat(),
        "status": "pending"
    }
    save_response(accept_id, {**response_data, "action": "accept"})
    save_response(decline_id, {**response_data, "action": "decline"})

    # Create message
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = recipient_email
    message["Subject"] = "Interview Scheduled - Please Confirm"

    # Create response URLs (in a real app, these would point to your server)
    base_url = os.environ.get("RESPONSE_SERVER_URL", "http://localhost:8000/api/respond")
    accept_url = f"{base_url}?id={accept_id}&action=accept"
    decline_url = f"{base_url}?id={decline_id}&action=decline"

    # Google Meet section - include the provided Meet link directly
    meet_link_section = ""
    if meet_link:
        meet_link_section = f"""
        <div style="background-color: #e8f0fe; padding: 15px; border-radius: 5px; margin: 15px 0; border-left: 4px solid #1a73e8;">
            <h3 style="margin-top: 0; color: #1a73e8;">Join Meeting</h3>
            <p><a href="{meet_link}" style="display: inline-block; background-color: #1a73e8; color: #ffffff; text-decoration: none; padding: 10px 20px; border-radius: 4px; font-weight: bold;">Join Google Meet</a></p>
            <p style="margin-bottom: 0; font-size: 0.9em;">Or copy this link: <a href="{meet_link}">{meet_link}</a></p>
        </div>
        """

    # Additional note section if provided
    additional_note_section = ""
    if additional_note:
        additional_note_section = f"""
        <div style="background-color: #fff3e0; padding: 15px; border-radius: 5px; margin: 15px 0; border-left: 4px solid #ff9800;">
            <p style="margin: 0;"><strong>Note:</strong> {additional_note}</p>
        </div>
        """

    # Email body with response buttons
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #f9f9f9; padding: 20px; border-radius: 5px; box-shadow: 0 0 10px rgba(0,0,0,0.1);">
            <h2 style="color: #4285f4; border-bottom: 1px solid #eee; padding-bottom: 10px;">Interview Scheduled</h2>
            
            <p>{'An interview has been scheduled for you' if not job_title else f"An interview for the {job_title} position has been scheduled"}.</p>
            
            {additional_note_section}
            
            {meet_link_section}
            
            <div style="background-color: #fff; padding: 15px; border-radius: 5px; margin: 15px 0; border-left: 4px solid #4285f4;">
                <p><strong>{'Candidate' if interviewer_name else 'Interviewee'}:</strong> {candidate_name or "Not specified"}</p>
                <p><strong>{'Interviewer' if candidate_name else 'Interviewer'}:</strong> {interviewer_name or "Not specified"}</p>
                <p><strong>Start Time:</strong> {start_time}</p>
                <p><strong>End Time:</strong> {end_time}</p>
            </div>

            <p style="margin: 20px 0;">Please confirm your availability:</p>

            <table width="100%" cellspacing="0" cellpadding="0" style="margin: 20px 0;">
                <tr>
                    <td style="padding-right: 10px;">
                        <a href="{accept_url}" 
                           style="display: inline-block; background-color: #4CAF50; color: #ffffff; text-decoration: none;
                                  padding: 12px 30px; border-radius: 4px; font-weight: bold; text-align: center;">
                            Accept
                        </a>
                    </td>
                    <td style="padding-left: 10px;">
                        <a href="{decline_url}" 
                           style="display: inline-block; background-color: #f44336; color: #ffffff; text-decoration: none;
                                  padding: 12px 30px; border-radius: 4px; font-weight: bold; text-align: center;">
                            Decline
                        </a>
                    </td>
                </tr>
            </table>

            <p style="font-size: 0.9em; color: #666; margin-top: 30px; border-top: 1px solid #eee; padding-top: 10px;">
                This is an automated message from the Interview Scheduler system. 
                If you did not expect this message, please disregard it.
            </p>
        </div>
    </body>
    </html>
    """

    # Attach the body to the email
    message.attach(MIMEText(body, "html"))

    try:
        # Connect to Gmail's SMTP server
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, password)

        # Send email
        server.send_message(message)
        server.quit()
        print(f"✅ Email notification sent to {recipient_email}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False
