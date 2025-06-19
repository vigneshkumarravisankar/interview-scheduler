from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, status, Query, Depends
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from app.utils.calendar_service import CalendarService

# Create router
router = APIRouter(
    prefix="/calendar",
    tags=["calendar"],
    responses={404: {"description": "Not found"}},
)


class InterviewSlotRequest(BaseModel):
    """Request model for finding interview slots"""
    duration_minutes: int = Field(60, description="Duration of the interview in minutes")
    days_ahead: int = Field(14, description="Number of days to look ahead for availability")
    working_hours_start: int = Field(9, description="Start of working hours (24-hour format)")
    working_hours_end: int = Field(17, description="End of working hours (24-hour format)")


class InterviewEventRequest(BaseModel):
    """Request model for creating an interview event"""
    job_id: str = Field(..., description="ID of the job posting")
    job_title: str = Field(..., description="Title of the job")
    job_description: str = Field(..., description="Description of the job")
    interview_questions: List[str] = Field([], description="List of interview questions")
    candidate_email: str = Field(..., description="Email of the candidate")
    interviewer_email: Optional[str] = Field(None, description="Email of the interviewer")
    start_time: datetime = Field(..., description="Start time of the interview")
    end_time: datetime = Field(..., description="End time of the interview")
    location: str = Field("Google Meet", description="Location of the interview")
    timezone: str = Field("Asia/Kolkata", description="Timezone for the interview")


@router.get("/availability", status_code=status.HTTP_200_OK)
async def find_available_slots(
    request: InterviewSlotRequest = Depends()
):
    """
    Find available slots for interviews
    """
    try:
        # Set up parameters
        start_date = datetime.now()
        end_date = start_date + timedelta(days=request.days_ahead)
        working_hours = {
            'start': request.working_hours_start, 
            'end': request.working_hours_end
        }
        
        # Find available slots
        available_slot = CalendarService.find_available_slot(
            duration_minutes=request.duration_minutes,
            start_date=start_date,
            end_date=end_date,
            working_hours=working_hours
        )
        
        if available_slot:
            return {
                "available_slot": {
                    "start_time": available_slot['start'].isoformat(),
                    "end_time": available_slot['end'].isoformat()
                },
                "status": "Available"
            }
        else:
            return {
                "status": "No available slots",
                "message": "No available slots found in the specified time range."
            }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find available slots: {str(e)}",
        )


@router.post("/schedule", status_code=status.HTTP_201_CREATED)
async def schedule_interview(
    event_request: InterviewEventRequest
):
    """
    Schedule an interview in Google Calendar
    """
    try:
        # Format questions
        questions_formatted = "\n".join([f"- {q}" for q in event_request.interview_questions])
        
        # Format description
        description = f"""Job Interview
        
Position: {event_request.job_title}

Description: {event_request.job_description}

Questions:
{questions_formatted}
        """
        
        # Format attendees
        attendees = [{'email': event_request.candidate_email}]
        if event_request.interviewer_email:
            attendees.append({'email': event_request.interviewer_email})
        
        # Create event
        event = CalendarService.create_interview_event(
            summary=f"Interview for {event_request.job_title}",
            description=description,
            start_time=event_request.start_time,
            end_time=event_request.end_time,
            attendees=attendees,
            location=event_request.location,
            timezone=event_request.timezone
        )
        
        return {
            "event_id": event.get('id'),
            "status": "Scheduled",
            "meet_link": event.get('hangoutLink', 'No link available'),
            "start_time": event_request.start_time.isoformat(),
            "end_time": event_request.end_time.isoformat(),
            "attendees": [a.get('email') for a in attendees]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to schedule interview: {str(e)}",
        )


@router.get("/events", status_code=status.HTTP_200_OK)
async def get_upcoming_events(
    days: int = Query(7, description="Number of days ahead to look for events"),
    max_results: int = Query(10, description="Maximum number of events to return")
):
    """
    Get upcoming events from the calendar
    """
    try:
        # Set up parameters
        time_min = datetime.now()
        time_max = time_min + timedelta(days=days)
        
        # Get events
        events = CalendarService.get_events(
            time_min=time_min, 
            time_max=time_max, 
            max_results=max_results
        )
        
        # Format response
        formatted_events = []
        for event in events:
            start_time = event.get('start', {}).get('dateTime')
            end_time = event.get('end', {}).get('dateTime')
            
            formatted_events.append({
                "event_id": event.get('id'),
                "summary": event.get('summary'),
                "start_time": start_time,
                "end_time": end_time,
                "location": event.get('location'),
                "meet_link": event.get('hangoutLink'),
                "attendees": [a.get('email') for a in event.get('attendees', [])]
            })
        
        return {
            "events": formatted_events,
            "count": len(formatted_events)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get calendar events: {str(e)}",
        )
