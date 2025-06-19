# calendar_api/email_notification.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import uuid
import json
from datetime import datetime

# Store for tracking responses
RESPONSE_FILE = "interview_responses.json"

def load_responses():
    if os.path.exists(RESPONSE_FILE):
        with open(RESPONSE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_response(response_id, data):
    responses = load_responses()
    responses[response_id] = data
    with open(RESPONSE_FILE, 'w') as f:
        json.dump(responses, f, indent=2)

def generate_response_id():
    return str(uuid.uuid4())

def send_interview_notification(recipient_email, start_time, end_time, meet_link):
    """Send email notification about the scheduled interview."""
    # Email configuration
    sender_email = "rrvigneshkumar2002@gmail.com"  # Replace with your email
    password = os.environ.get("EMAIL_PASSWORD")  # Set this as an environment variable for security

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
    base_url = "http://localhost:5000/respond"
    accept_url = f"{base_url}?id={accept_id}&action=accept"
    decline_url = f"{base_url}?id={decline_id}&action=decline"

    # Email body with response buttons
    body = f"""
    <html>
    <body>
        <h2>Interview Scheduled</h2>
        <p>An interview has been scheduled for you.</p>
        <p><strong>Start Time:</strong> {start_time}</p>
        <p><strong>End Time:</strong> {end_time}</p>
        <p><strong>Google Meet Link:</strong> <a href="{meet_link}">{meet_link}</a></p>

        <p>Please confirm your availability:</p>

        <table width="100%" cellspacing="0" cellpadding="0">
            <tr>
                <td>
                    <table cellspacing="0" cellpadding="0">
                        <tr>
                            <td style="border-radius: 4px; background-color: #4CAF50;">
                                <a href="{accept_url}" 
                                   style="padding: 10px 20px; border-radius: 4px; color: #ffffff; text-decoration: none; display: inline-block; background-color: #4CAF50;">
                                    Accept
                                </a>
                            </td>
                        </tr>
                    </table>
                </td>
                <td>
                    <table cellspacing="0" cellpadding="0">
                        <tr>
                            <td style="border-radius: 4px; background-color: #f44336;">
                                <a href="{decline_url}" 
                                   style="padding: 10px 20px; border-radius: 4px; color: #ffffff; text-decoration: none; display: inline-block; background-color: #f44336;">
                                    Decline
                                </a>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>

        <p>This is an automated message.</p>
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