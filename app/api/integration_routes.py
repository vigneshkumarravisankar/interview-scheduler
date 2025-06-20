"""
API routes for integration agents (Calendar, GMeet, Gmail)

This module provides API endpoints that expose the specialized integration agents for:
1. Calendar operations
2. Google Meet operations
3. Gmail operations

These agents can be used independently to perform specialized tasks within their domains.
"""

from fastapi import APIRouter, HTTPException, status, Body, Query, Depends
from typing import Dict, Any, List, Optional
import logging
from pydantic import BaseModel, Field

from app.agents.integration_agents import (
    calendar_agent, meet_agent, gmail_agent,
    create_integration_crew, schedule_interview_with_integrations
)

from crewai import Task, Crew, Process

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/integrations",
    tags=["integrations"],
    responses={404: {"description": "Not found"}},
)

#-----------------------
# Request/Response Models
#-----------------------

class CalendarRequestBase(BaseModel):
    """Base model for calendar requests"""
    query: str = Field(..., description="Natural language query describing what you want to do with calendar")

class MeetRequestBase(BaseModel):
    """Base model for Google Meet requests"""
    query: str = Field(..., description="Natural language query describing what you want to do with Google Meet")

class GmailRequestBase(BaseModel):
    """Base model for Gmail requests"""
    query: str = Field(..., description="Natural language query describing what you want to do with Gmail")

class ScheduleInterviewRequest(BaseModel):
    """Request model for scheduling an interview using all integrations"""
    candidate_name: str
    candidate_email: str
    interviewer_name: str
    interviewer_email: str
    job_title: str
    preferred_date: Optional[str] = None  # Format: YYYY-MM-DD
    round_number: int = 1
    round_type: Optional[str] = None
    notes: Optional[str] = None

class AgentResponse(BaseModel):
    """Response model for agent operations"""
    response: str
    agent_role: str
    success: bool

#-----------------------
# API Routes
#-----------------------

@router.post("/calendar", response_model=AgentResponse)
async def calendar_operation(request: CalendarRequestBase):
    """
    Execute a calendar operation using the Calendar Agent
    
    This endpoint allows natural language requests for calendar operations such as:
    - "Find available slots on June 25th"
    - "Schedule a meeting with John Smith tomorrow at 3 PM"
    - "Delete the meeting with ID abc123"
    """
    try:
        # Create a task for the calendar agent
        calendar_task = Task(
            description=f"Execute the following calendar operation: {request.query}",
            expected_output="Result of the calendar operation",
            agent=calendar_agent
        )
        
        # Create a temporary crew with just this agent and task
        crew = Crew(
            agents=[calendar_agent],
            tasks=[calendar_task],
            verbose=True,
            process=Process.sequential
        )
        
        # Execute the task
        result = crew.kickoff()
        
        # Convert result to string if needed
        if hasattr(result, 'raw'):
            response_text = result.raw
        elif hasattr(result, 'result'):
            response_text = result.result
        else:
            response_text = str(result)
        
        # Return the response
        return {
            "response": response_text,
            "agent_role": "Calendar Management Specialist",
            "success": True
        }
    except Exception as e:
        logger.error(f"Error in calendar operation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing calendar operation: {str(e)}"
        )

@router.post("/meet", response_model=AgentResponse)
async def meet_operation(request: MeetRequestBase):
    """
    Execute a Google Meet operation using the Meet Agent
    
    This endpoint allows natural language requests for Google Meet operations such as:
    - "Create a meeting link for interview with John Smith"
    - "Check status of meeting with code abc-defg-hij"
    """
    try:
        # Create a task for the meet agent
        meet_task = Task(
            description=f"Execute the following Google Meet operation: {request.query}",
            expected_output="Result of the Google Meet operation",
            agent=meet_agent
        )
        
        # Create a temporary crew with just this agent and task
        crew = Crew(
            agents=[meet_agent],
            tasks=[meet_task],
            verbose=True,
            process=Process.sequential
        )
        
        # Execute the task
        result = crew.kickoff()
        
        # Convert result to string if needed
        if hasattr(result, 'raw'):
            response_text = result.raw
        elif hasattr(result, 'result'):
            response_text = result.result
        else:
            response_text = str(result)
        
        # Return the response
        return {
            "response": response_text,
            "agent_role": "Google Meet Specialist",
            "success": True
        }
    except Exception as e:
        logger.error(f"Error in Google Meet operation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing Google Meet operation: {str(e)}"
        )

@router.post("/gmail", response_model=AgentResponse)
async def gmail_operation(request: GmailRequestBase):
    """
    Execute a Gmail operation using the Gmail Agent
    
    This endpoint allows natural language requests for Gmail operations such as:
    - "Send an interview confirmation email to john@example.com"
    - "Send rescheduling notification to candidate Sarah"
    """
    try:
        # Create a task for the gmail agent
        gmail_task = Task(
            description=f"Execute the following email operation: {request.query}",
            expected_output="Result of the email operation",
            agent=gmail_agent
        )
        
        # Create a temporary crew with just this agent and task
        crew = Crew(
            agents=[gmail_agent],
            tasks=[gmail_task],
            verbose=True,
            process=Process.sequential
        )
        
        # Execute the task
        result = crew.kickoff()
        
        # Convert result to string if needed
        if hasattr(result, 'raw'):
            response_text = result.raw
        elif hasattr(result, 'result'):
            response_text = result.result
        else:
            response_text = str(result)
        
        # Return the response
        return {
            "response": response_text,
            "agent_role": "Email Communications Expert",
            "success": True
        }
    except Exception as e:
        logger.error(f"Error in Gmail operation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing Gmail operation: {str(e)}"
        )

@router.post("/schedule-interview")
async def schedule_interview(request: ScheduleInterviewRequest):
    """
    Schedule an interview using all integration agents
    
    This endpoint uses a crew of agents (Calendar, Meet, Gmail) to:
    1. Find an available time slot and schedule a calendar event
    2. Create a Google Meet link for the interview
    3. Send email notifications to both candidate and interviewer
    """
    try:
        # Convert request to dictionary for the integration function
        interview_details = {
            "candidate_name": request.candidate_name,
            "candidate_email": request.candidate_email,
            "interviewer_name": request.interviewer_name,
            "interviewer_email": request.interviewer_email,
            "job_title": request.job_title,
            "preferred_date": request.preferred_date,
            "round_number": request.round_number,
            "round_type": request.round_type,
            "notes": request.notes
        }
        
        # Schedule the interview using the integration crew
        result = schedule_interview_with_integrations(interview_details)
        
        if result["success"]:
            # Extract the actual result text
            if hasattr(result["result"], 'raw'):
                result_text = result["result"].raw
            elif hasattr(result["result"], 'result'):
                result_text = result["result"].result
            else:
                result_text = str(result["result"])
                
            return {
                "success": True,
                "message": "Interview scheduled successfully",
                "details": result_text
            }
        else:
            return {
                "success": False,
                "message": result["message"],
                "error": result.get("error", "Unknown error")
            }
    except Exception as e:
        logger.error(f"Error scheduling interview: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error scheduling interview: {str(e)}"
        )
