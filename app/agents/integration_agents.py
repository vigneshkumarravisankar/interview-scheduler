"""
Integration Agents for Calendar, GMeet, and Gmail Services

This module contains specialized CrewAI agents for handling specific service integrations:
1. CalendarAgent - Google Calendar integration for scheduling interviews
2. MeetAgent - Google Meet integration for creating meeting links
3. GmailAgent - Gmail integration for sending email notifications

These agents can be used independently or as part of a larger agent crew.
"""

import os
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import uuid
import random
import string
from pydantic import BaseModel, Field

# CrewAI imports
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from langchain_openai import ChatOpenAI

# Service imports
from app.utils.calendar_service import CalendarService, create_calendar_event
from app.utils.email_service import send_email
from app.utils.email_notification import send_interview_notification
from app.utils.oauth_manager import OAuthManager
from app.services.interview_core_service import InterviewCoreService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get OpenAI API Key from environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY not found in environment. Using default key.")
    # Default key from the project setup
    OPENAI_API_KEY = "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"

# Initialize LLM model for CrewAI
llm = ChatOpenAI(
    openai_api_key=OPENAI_API_KEY,
    model_name="gpt-4o",
    temperature=0.2
)

#-----------------------
# Calendar Agent Tools
#-----------------------
class CreateCalendarEventTool(BaseTool):
    name: str = "CreateCalendarEvent"
    description: str = "Create a calendar event for an interview"
    
    class InputSchema(BaseModel):
        summary: str = Field(description="Calendar event summary/title")
        description: str = Field(description="Calendar event description")
        start_time: str = Field(description="Start time in ISO format (YYYY-MM-DDTHH:MM:SS+TZ)")
        end_time: str = Field(description="End time in ISO format (YYYY-MM-DDTHH:MM:SS+TZ)")
        attendees: List[Dict[str, str]] = Field(description="List of attendees with email addresses")
        
    args_schema = InputSchema
    
    def _run(self, summary: str, description: str, start_time: str, end_time: str, attendees: List[Dict[str, str]]) -> str:
        """Create a Google Calendar event"""
        try:
            # Create the event
            event = create_calendar_event(
                summary=summary,
                description=description,
                start_time=start_time,
                end_time=end_time,
                attendees=attendees
            )
            
            # Extract relevant details
            event_id = event.get('id', 'Unknown ID')
            html_link = event.get('htmlLink', '')
            meet_link = event.get('hangoutLink', '')
            
            # Format response
            response = f"""
Calendar event created successfully!

Event ID: {event_id}
Calendar Link: {html_link}
Google Meet Link: {meet_link}

Summary: {summary}
Start Time: {start_time}
End Time: {end_time}
Attendees: {", ".join([a.get('email', '') for a in attendees])}
            """
            
            return response
        except Exception as e:
            logger.error(f"Error creating calendar event: {e}")
            return f"Failed to create calendar event: {str(e)}"

class GetAvailableSlotsTool(BaseTool):
    name: str = "GetAvailableSlots"
    description: str = "Find available time slots for scheduling an interview"
    
    class InputSchema(BaseModel):
        date: str = Field(description="Date to check (YYYY-MM-DD)")
        calendar_ids: List[str] = Field(description="List of calendar IDs to check")
        duration_minutes: int = Field(description="Duration of meeting in minutes", default=60)
        
    args_schema = InputSchema
    
    def _run(self, date: str, calendar_ids: List[str], duration_minutes: int = 60) -> str:
        """Find available time slots on calendars"""
        try:
            # Check if we need to use the default calendar ID
            if not calendar_ids:
                calendar_ids = [os.environ.get("GOOGLE_CALENDAR_ID", "primary")]
            
            # Get busys times for the calendars
            busy_slots = []
            
            # For each calendar, get the busy times
            for calendar_id in calendar_ids:
                try:
                    events = CalendarService.list_events(
                        calendar_id=calendar_id,
                        time_min=f"{date}T00:00:00+05:30",
                        time_max=f"{date}T23:59:59+05:30"
                    )
                    
                    # Extract busy times from events
                    for event in events.get('items', []):
                        start = event.get('start', {}).get('dateTime')
                        end = event.get('end', {}).get('dateTime')
                        
                        if start and end:
                            busy_slots.append((start, end))
                except Exception as e:
                    logger.warning(f"Error retrieving events for calendar {calendar_id}: {e}")
            
            # Define working hours (9 AM to 6 PM)
            work_start = f"{date}T09:00:00+05:30"
            work_end = f"{date}T18:00:00+05:30"
            
            # Convert to datetime objects
            work_start_dt = datetime.fromisoformat(work_start)
            work_end_dt = datetime.fromisoformat(work_end)
            
            # Convert busy slots to datetime objects
            busy_slots_dt = [(datetime.fromisoformat(start), datetime.fromisoformat(end)) for start, end in busy_slots]
            
            # Sort busy slots by start time
            busy_slots_dt.sort(key=lambda x: x[0])
            
            # Find available slots
            available_slots = []
            current = work_start_dt
            
            for busy_start, busy_end in busy_slots_dt:
                # If there's time before the busy slot
                if current < busy_start:
                    # Check if we have enough time for the meeting
                    if (busy_start - current).total_seconds() / 60 >= duration_minutes:
                        available_slots.append((current, busy_start))
                # Move current time to after the busy slot
                current = max(current, busy_end)
            
            # Check if there's time after the last busy slot
            if current < work_end_dt:
                if (work_end_dt - current).total_seconds() / 60 >= duration_minutes:
                    available_slots.append((current, work_end_dt))
            
            # Format available slots for display
            formatted_slots = []
            for i, (slot_start, slot_end) in enumerate(available_slots):
                # Calculate the maximum meeting end time (either the end of the slot or slot_start + duration)
                max_meeting_end = min(slot_end, slot_start + timedelta(minutes=duration_minutes))
                
                # Format for display
                slot_start_str = slot_start.strftime("%I:%M %p")
                max_meeting_end_str = max_meeting_end.strftime("%I:%M %p")
                
                formatted_slots.append(f"Slot {i+1}: {slot_start_str} - {max_meeting_end_str}")
            
            # Build response
            if formatted_slots:
                response = f"Available slots on {date}:\n\n" + "\n".join(formatted_slots)
            else:
                response = f"No available {duration_minutes}-minute slots found on {date} between 9 AM and 6 PM."
                
            return response
        except Exception as e:
            logger.error(f"Error finding available slots: {e}")
            return f"Failed to find available slots: {str(e)}"

class DeleteCalendarEventTool(BaseTool):
    name: str = "DeleteCalendarEvent"
    description: str = "Delete a calendar event"
    
    class InputSchema(BaseModel):
        event_id: str = Field(description="ID of the calendar event to delete")
        calendar_id: str = Field(description="ID of the calendar", default="primary")
        
    args_schema = InputSchema
    
    def _run(self, event_id: str, calendar_id: str = "primary") -> str:
        """Delete a Google Calendar event"""
        try:
            # Delete the event
            result = CalendarService.delete_event(event_id, calendar_id)
            
            return f"Calendar event {event_id} deleted successfully."
        except Exception as e:
            logger.error(f"Error deleting calendar event: {e}")
            return f"Failed to delete calendar event: {str(e)}"

#-----------------------
# Meet Agent Tools
#-----------------------
class CreateMeetingLinkTool(BaseTool):
    name: str = "CreateMeetingLink"
    description: str = "Create a Google Meet link for an interview"
    
    class InputSchema(BaseModel):
        summary: str = Field(description="Meeting name/title")
        
    args_schema = InputSchema
    
    def _run(self, summary: str) -> str:
        """Create a standalone Google Meet link"""
        try:
            # Generate a meeting code - this is a simplified implementation
            # In a real implementation, you would use the Google Meet API
            meet_code = CalendarService.generate_meet_code()
            
            # Format the meeting link
            meet_link = f"https://meet.google.com/{meet_code}"
            
            return f"""
Google Meet link created successfully!

Meeting: {summary}
Link: {meet_link}

You can share this link directly with participants.
            """
        except Exception as e:
            logger.error(f"Error creating meeting link: {e}")
            return f"Failed to create meeting link: {str(e)}"

class CheckMeetingStatusTool(BaseTool):
    name: str = "CheckMeetingStatus"
    description: str = "Check if a Google Meet meeting is active and get participant information"
    
    class InputSchema(BaseModel):
        meeting_code: str = Field(description="The meeting code or full URL")
        
    args_schema = InputSchema
    
    def _run(self, meeting_code: str) -> str:
        """
        Check Google Meet meeting status
        
        Note: This is a simplified implementation as the Meet API has limitations
        on programmatically checking meeting status.
        """
        # Extract meeting code from URL if needed
        if "meet.google.com/" in meeting_code:
            meeting_code = meeting_code.split("meet.google.com/")[-1]
            
        # This is a simplified mock implementation
        # In reality, you'd need special admin privileges to access meet status via API
        
        # Randomly determine if meeting is active (for demo purposes)
        is_active = random.choice([True, False])
        
        if is_active:
            # Generate random number of participants
            participant_count = random.randint(1, 5)
            
            response = f"""
Meeting {meeting_code} is currently active.

Participants: {participant_count}
Duration: {random.randint(1, 30)} minutes

Note: For security and privacy reasons, detailed participant information 
is only available to meeting hosts and G Suite administrators.
            """
        else:
            response = f"""
Meeting {meeting_code} is not currently active.

This could mean:
- The meeting hasn't started yet
- The meeting has ended
- The meeting code is incorrect
            """
            
        return response

#-----------------------
# Gmail Agent Tools
#-----------------------
class SendEmailNotificationTool(BaseTool):
    name: str = "SendEmailNotification"
    description: str = "Send an email notification about an interview"
    
    class InputSchema(BaseModel):
        candidate_name: str = Field(description="Name of the candidate")
        candidate_email: str = Field(description="Email address of the candidate")
        interviewer_name: str = Field(description="Name of the interviewer")
        interviewer_email: str = Field(description="Email address of the interviewer")
        job_title: str = Field(description="Job title for the interview")
        interview_time: str = Field(description="Time of the interview (e.g. '10AM')")
        interview_date: str = Field(description="Date of the interview (e.g. 'Monday, June 20, 2025')")
        meet_link: str = Field(description="Google Meet link for the interview")
        round_number: int = Field(description="Interview round number")
        round_type: str = Field(description="Type of interview round (e.g. 'Technical', 'HR')", default="")
        is_rescheduled: bool = Field(description="Whether this is a rescheduled interview", default=False)
        reschedule_reason: str = Field(description="Reason for rescheduling (if applicable)", default="")
        
    args_schema = InputSchema
    
    def _run(self, candidate_name: str, candidate_email: str, interviewer_name: str, interviewer_email: str, 
              job_title: str, interview_time: str, interview_date: str, meet_link: str, 
              round_number: int, round_type: str = "", is_rescheduled: bool = False, 
              reschedule_reason: str = "") -> str:
        """Send interview notification emails"""
        try:
            # Send notification
            send_interview_notification(
                candidate_name=candidate_name,
                recipient_email=candidate_email,
                interviewer_name=interviewer_name,
                interviewer_email=interviewer_email,
                job_title=job_title,
                start_time=interview_time,
                interview_date=interview_date,
                meet_link=meet_link,
                round_number=round_number,
                round_type=round_type,
                is_rescheduled=is_rescheduled,
                reschedule_reason=reschedule_reason
            )
            
            # Determine notification type for response
            notification_type = "rescheduled interview" if is_rescheduled else "interview"
            
            return f"""
Email notifications for the {notification_type} sent successfully!

Emails were sent to:
- Candidate: {candidate_name} <{candidate_email}>
- Interviewer: {interviewer_name} <{interviewer_email}>

Interview Details:
- Job: {job_title}
- Date: {interview_date}
- Time: {interview_time}
- Round: {round_number} - {round_type if round_type else f"Round {round_number}"}
- Meet Link: {meet_link}

{f"Reschedule Reason: {reschedule_reason}" if is_rescheduled else ""}
            """
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
            return f"Failed to send email notification: {str(e)}"

class SendGenericEmailTool(BaseTool):
    name: str = "SendGenericEmail"
    description: str = "Send a generic email with custom subject and content"
    
    class InputSchema(BaseModel):
        to: List[str] = Field(description="List of recipient email addresses")
        subject: str = Field(description="Email subject line")
        body: str = Field(description="Email body content")
        cc: List[str] = Field(description="List of CC recipients", default=[])
        bcc: List[str] = Field(description="List of BCC recipients", default=[])
        
    args_schema = InputSchema
    
    def _run(self, to: List[str], subject: str, body: str, cc: List[str] = [], bcc: List[str] = []) -> str:
        """Send a generic email"""
        try:
            # Send the email
            send_email(
                to_emails=to,
                subject=subject,
                html_content=body,
                cc=cc,
                bcc=bcc
            )
            
            # Format response
            recipients = ", ".join(to)
            cc_str = f"CC: {', '.join(cc)}" if cc else "CC: None"
            bcc_str = f"BCC: {', '.join(bcc)}" if bcc else "BCC: None"
            
            return f"""
Email sent successfully!

To: {recipients}
{cc_str}
{bcc_str}
Subject: {subject}

Email Preview:
----------------
{body[:200]}{'...' if len(body) > 200 else ''}
----------------
            """
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return f"Failed to send email: {str(e)}"

#-----------------------
# Agent Definitions
#-----------------------

# Calendar Agent
calendar_agent = Agent(
    role="Calendar Management Specialist",
    goal="Efficiently manage interview scheduling and calendar operations",
    backstory="You are an expert in calendar management with years of experience optimizing schedules and finding the perfect time slots for important meetings. You understand the importance of coordinating across multiple calendars and time zones.",
    verbose=True,
    allow_delegation=True,
    llm=llm,
    tools=[
        CreateCalendarEventTool(),
        GetAvailableSlotsTool(),
        DeleteCalendarEventTool()
    ]
)

# Meet Agent
meet_agent = Agent(
    role="Google Meet Specialist",
    goal="Create and manage Google Meet video conferencing for interviews",
    backstory="You are specialized in video conferencing technology, ensuring that interviews can be conducted smoothly via Google Meet. You understand the technical aspects of video meetings and how to optimize the experience for all participants.",
    verbose=True,
    allow_delegation=True,
    llm=llm,
    tools=[
        CreateMeetingLinkTool(),
        CheckMeetingStatusTool()
    ]
)

# Gmail Agent
gmail_agent = Agent(
    role="Email Communications Expert",
    goal="Handle all email communications related to the interview process",
    backstory="You are skilled in crafting professional email communications that provide clear information and maintain a positive impression of the company. You ensure all parties receive timely and appropriate notifications about interviews and scheduling changes.",
    verbose=True,
    allow_delegation=True,
    llm=llm,
    tools=[
        SendEmailNotificationTool(),
        SendGenericEmailTool()
    ]
)

#-----------------------
# Integration Crew
#-----------------------
def create_integration_crew():
    """Create a crew of integration agents"""
    
    crew = Crew(
        agents=[calendar_agent, meet_agent, gmail_agent],
        tasks=[],  # Tasks will be added dynamically
        verbose=True,
        process=Process.sequential
    )
    
    return crew

def schedule_interview_with_integrations(interview_details: Dict[str, Any]):
    """
    Schedule an interview using the integration agents
    
    Args:
        interview_details: Dictionary containing interview details
    
    Returns:
        Dict with scheduling results
    """
    # Create dynamic tasks for each agent
    
    # Task for the Calendar Agent
    calendar_task = Task(
        description=f"""
        Schedule a calendar event for the following interview:
        
        Candidate: {interview_details.get('candidate_name')}
        Job: {interview_details.get('job_title')}
        Round: {interview_details.get('round_number')}
        
        Find an available time slot on {interview_details.get('preferred_date', 'the next business day')}.
        Then create a calendar event for a 1-hour interview.
        
        Include the candidate email ({interview_details.get('candidate_email')}) and interviewer 
        email ({interview_details.get('interviewer_email')}) as attendees.
        """,
        expected_output="Calendar event details with confirmed time slot",
        agent=calendar_agent
    )
    
    # Task for the Meet Agent
    meet_task = Task(
        description=f"""
        Create a Google Meet link for the interview between {interview_details.get('candidate_name')} 
        and {interview_details.get('interviewer_name')} for the {interview_details.get('job_title')} position.
        
        This is for round {interview_details.get('round_number')} of the interview process.
        """,
        expected_output="Google Meet link for the interview",
        agent=meet_agent
    )
    
    # Task for the Gmail Agent
    gmail_task = Task(
        description=f"""
        Send email notifications about the scheduled interview to both the candidate and interviewer.
        
        Use the calendar event details and Google Meet link from the previous tasks.
        Make sure to include all relevant information about the interview:
        - Job title: {interview_details.get('job_title')}
        - Round: {interview_details.get('round_number')}
        - Candidate: {interview_details.get('candidate_name')}
        - Interviewer: {interview_details.get('interviewer_name')}
        
        Send separate, appropriately formatted emails to both parties.
        """,
        expected_output="Confirmation of sent email notifications",
        agent=gmail_agent
    )
    
    # Create a temporary crew for this operation
    temp_crew = Crew(
        agents=[calendar_agent, meet_agent, gmail_agent],
        tasks=[calendar_task, meet_task, gmail_task],
        verbose=True,
        process=Process.sequential
    )
    
    # Execute the crew tasks
    try:
        result = temp_crew.kickoff()
        return {
            "success": True,
            "result": result,
            "message": "Interview scheduled successfully"
        }
    except Exception as e:
        logger.error(f"Error scheduling interview: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to schedule interview"
        }
