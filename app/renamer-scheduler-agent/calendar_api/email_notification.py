# calendar_api/email_notification.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
 
def send_interview_notification(recipient_email, start_time, end_time, meet_link):
    """Send email notification about the scheduled interview."""
    # Email configuration
    sender_email = "rrvigneshkumar2002@gmail.com"  # Replace with your email
    password = os.environ.get("EMAIL_PASSWORD")  # Set this as an environment variable for security
 
    if not password:
        print("⚠️ Email password not found in environment variables. Email not sent.")
        return False
 
    # Create message
    message = MIMEMultipart()
    message["From"] = "rrvigneshkumar2002@gmail.com"
    message["To"] = recipient_email
    message["Subject"] = "Interview Scheduled"
 
    # Email body
    body = f"""
    <html>
    <body>
        <h2>Interview Scheduled</h2>
        <p>An interview has been scheduled for you.</p>
        <p><strong>Start Time:</strong> {start_time}</p>
        <p><strong>End Time:</strong> {end_time}</p>
        <p><strong>Google Meet Link:</strong> <a href="{meet_link}">{meet_link}</a></p>
        <p>Please make sure to join the meeting on time.</p>
        <p>This is an automated message. Please do not reply to this email.</p>
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