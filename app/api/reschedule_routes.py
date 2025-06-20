from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime
from app.services.interview_core_service import InterviewCoreService
from app.agents.crew_agent_system import get_agent_system
from app.utils.calendar_service import CalendarService
from app.utils.email_notification import send_interview_notification
import random
import string

# Create router
router = APIRouter(
    prefix="/reschedule",
    tags=["reschedule"],
    responses={404: {"description": "Not found"}},
)


class RescheduleRequest(BaseModel):
    interview_id: str
    round_index: int
    new_time: str  # Format: 'YYYY-MM-DD HH:MM'
    reason: str = "Scheduling conflict"


class RescheduleResponse(BaseModel):
    success: bool
    interview_id: str
    round_index: int
    old_time: Optional[str]
    new_time: str
    meet_link: str
    calendar_link: Optional[str]
    emails_sent: bool
    message: str


@router.post("/", response_model=RescheduleResponse)
async def reschedule_interview(request: RescheduleRequest):
    """
    Reschedule an interview for a specific round.
    
    This endpoint will:
    1. Get the interview record
    2. Delete the existing calendar event
    3. Create a new calendar event
    4. Update the interview record
    5. Send email notifications
    """
    try:
        # Get the interview record
        interview_record = InterviewCoreService.get_interview_candidate(request.interview_id)
        
        if not interview_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Interview record with ID {request.interview_id} not found",
            )
                
        # Verify the round index is valid
        feedback_array = interview_record.get('feedback', [])
        if request.round_index < 0 or request.round_index >= len(feedback_array):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid round index {request.round_index}. Valid range: 0-{len(feedback_array)-1}",
            )
        
        # Get the current round details
        round_details = feedback_array[request.round_index]
        interviewer_name = round_details.get('interviewer_name', 'Unknown')
        
        # Save old time for response
        old_time = None
        if 'scheduled_event' in round_details and 'start' in round_details['scheduled_event']:
            start_info = round_details['scheduled_event']['start']
            if 'dateTime' in start_info:
                old_time = start_info['dateTime']
        
        # Parse the new time
        try:
            new_datetime = datetime.strptime(request.new_time, "%Y-%m-%d %H:%M")
            start_time = new_datetime
            end_time = new_datetime.replace(hour=new_datetime.hour + 1)  # 1 hour interview
            
            # Format dates in ISO format with timezone
            start_iso = start_time.strftime("%Y-%m-%dT%H:%M:%S+05:30")
            end_iso = end_time.strftime("%Y-%m-%dT%H:%M:%S+05:30")
            
            # Format for display
            formatted_time = start_time.strftime("%I%p").lstrip('0')  # e.g., "10AM"
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid time format. Please use the format 'YYYY-MM-DD HH:MM'",
            )
        
        # Get candidate and interviewer details for the new event
        candidate_name = interview_record.get('candidate_name', 'Candidate')
        candidate_email = interview_record.get('candidate_email', 'candidate@example.com')
        interviewer_email = round_details.get('interviewer_email', 'interviewer@example.com')
        job_role = interview_record.get('job_role', 'Unknown Position')
        round_type = round_details.get('round_type', f"Round {request.round_index+1}")
        
        # Update the calendar event if there is one
        old_event_id = round_details.get('scheduled_event', {}).get('id')
        if old_event_id:
            # Delete the old event
            CalendarService.delete_event(old_event_id)
        
        # Create event summary and description
        summary = f"Interview: {candidate_name} with {interviewer_name} - Round {request.round_index+1} ({round_type})"
        description = f"""
        RESCHEDULED INTERVIEW for {candidate_name} ({candidate_email})
        Job: {job_role}
        Round: {request.round_index+1} - {round_type} Round
        Interviewer: {interviewer_name} ({interviewer_email})
        
        Reason for rescheduling: {request.reason}
        
        Please join using the Google Meet link at the scheduled time.
        """
        
        # Create a new calendar event
        from app.utils.calendar_service import create_calendar_event
        calendar_event = create_calendar_event(
            summary=summary,
            description=description,
            start_time=start_iso,
            end_time=end_iso,
            attendees=[
                {"email": interviewer_email},
                {"email": candidate_email}
            ]
        )
        
        # Extract event details
        if calendar_event:
            event_id = calendar_event.get('id', '')
            meet_link = calendar_event.get('hangoutLink', calendar_event.get('manual_meet_link', ''))
            html_link = calendar_event.get('htmlLink', '')
        else:
            # If calendar event creation failed, create dummy data
            event_id = ''.join(random.choices(string.ascii_letters + string.digits, k=20))
            meet_link = f"https://meet.google.com/{CalendarService.generate_meet_code()}"
            html_link = f"https://calendar.google.com/calendar/event?eid=mock-event"
        
        # Update the round details
        round_details['scheduled_time'] = formatted_time
        round_details['meet_link'] = meet_link
        round_details['scheduled_event'] = {
            "end": {
                "dateTime": end_iso,
                "timeZone": "Asia/Kolkata"
            },
            "start": {
                "dateTime": start_iso,
                "timeZone": "Asia/Kolkata"
            },
            "htmlLink": html_link,
            "id": event_id
        }
        
        # Update the feedback array
        feedback_array[request.round_index] = round_details
        interview_record['feedback'] = feedback_array
        
        # Save the updated record
        InterviewCoreService.update_interview_candidate(request.interview_id, interview_record)
        
        # Send email notification about the rescheduling
        emails_sent = False
        try:
            send_interview_notification(
                candidate_name=candidate_name,
                candidate_email=candidate_email,
                interviewer_name=interviewer_name,
                interviewer_email=interviewer_email,
                job_title=job_role,
                interview_time=formatted_time,
                interview_date=start_time.strftime("%A, %B %d, %Y"),
                meet_link=meet_link,
                round_number=request.round_index+1,
                round_type=round_type,
                is_rescheduled=True,
                reschedule_reason=request.reason
            )
            emails_sent = True
        except Exception as e:
            # Log error but continue
            print(f"Error sending email notification: {e}")
        
        return {
            "success": True,
            "interview_id": request.interview_id,
            "round_index": request.round_index,
            "old_time": old_time,
            "new_time": start_iso,
            "meet_link": meet_link,
            "calendar_link": html_link,
            "emails_sent": emails_sent,
            "message": "Interview rescheduled successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error rescheduling interview: {str(e)}",
        )


@router.post("/agent", response_model=Dict[str, Any])
async def agent_reschedule_interview(request: RescheduleRequest, background_tasks: BackgroundTasks):
    """
    Use the CrewAI agent system to reschedule an interview.
    This provides a more intelligent rescheduling with natural language processing.
    """
    try:
        # Get the agent system
        agent_system = get_agent_system()
        
        # Create a query for the agent to process
        query = f"Reschedule interview {request.interview_id}, round {request.round_index} to {request.new_time}. Reason: {request.reason}"
        
        # Create a session ID for this request
        session_id = f"reschedule-{request.interview_id}-{request.round_index}"
        
        # Process the query with the agent system
        result = agent_system.process_query(query, session_id)
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error using agent to reschedule interview: {str(e)}",
        )
