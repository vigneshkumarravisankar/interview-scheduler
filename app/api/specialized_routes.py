"""
API Routes for Specialized Agents

This module provides API endpoints for the specialized shortlisting and scheduling agents.
These are CrewAI agents designed to handle the complete interview process pipeline:
1. Shortlisting top candidates based on AI fit scores
2. Scheduling interviews with calendar, meet, and email integrations
"""

from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import json
from datetime import datetime, timedelta

# Import specialized agents
from app.agents.specialized_agents import (
    run_shortlisting_process,
    run_scheduling_process, 
    run_end_to_end_process,
    shortlisting_agent,
    Task,
    Crew,
    Process
)

# Create router
router = APIRouter(
    prefix="/specialized",
    tags=["specialized"],
    responses={404: {"description": "Not found"}},
)

class ShortlistRequest(BaseModel):
    job_role_name: str = Field(..., description="Name of the job role to shortlist candidates for (e.g., 'AI Engineer')")
    number_of_candidates: int = Field(default=2, description="Number of candidates to shortlist (default 2)")

class ScheduleRequest(BaseModel):
    job_role_name: str = Field(..., description="Name of the job role to schedule interviews for (e.g., 'AI Engineer')")
    interview_date: Optional[str] = Field(None, description="Date for interviews in YYYY-MM-DD format (default: tomorrow)")
    number_of_rounds: int = Field(default=2, description="Number of interview rounds (default 2)")

class EndToEndRequest(BaseModel):
    job_role_name: str = Field(..., description="Name of the job role for the entire process (e.g., 'AI Engineer')")
    number_of_candidates: int = Field(default=2, description="Number of candidates to shortlist (default 2)")
    interview_date: Optional[str] = Field(None, description="Date for interviews in YYYY-MM-DD format (default: tomorrow)")
    number_of_rounds: int = Field(default=2, description="Number of interview rounds (default 2)")

@router.post("/shortlist")
async def shortlist_candidates(request: ShortlistRequest, background_tasks: BackgroundTasks):
    """
    Use the specialized shortlisting agent to select top candidates based on AI fit scores
    
    This agent will:
    1. Get all candidates for the specified job role
    2. Rank them by AI fit score
    3. Select the top N candidates
    4. Store them directly in interview_candidates collection
    """
    try:
        # Run the shortlisting process in the background
        def run_shortlisting():
            result = run_shortlisting_process(
                job_role_name=request.job_role_name,
                number_of_candidates=request.number_of_candidates
            )
            print(f"Shortlisting completed: {result}")
            return result
            
        # Add the background task
        background_tasks.add_task(run_shortlisting)
        
        return {
            "status": "processing",
            "message": f"Shortlisting top {request.number_of_candidates} candidates for job role '{request.job_role_name}'",
            "job_role_name": request.job_role_name
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error shortlisting candidates: {str(e)}",
        )
        
@router.post("/shortlist-by-role")
async def shortlist_candidates_by_role(request: ShortlistRequest, background_tasks: BackgroundTasks):
    """
    This endpoint is deprecated. Please use /shortlist instead.
    Keeping for backward compatibility.
    """
    try:
        # Redirect to the main shortlist endpoint
        return await shortlist_candidates(request, background_tasks)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error shortlisting candidates: {str(e)}",
        )

@router.post("/schedule")
async def schedule_interviews(request: ScheduleRequest, background_tasks: BackgroundTasks):
    """
    Use the specialized scheduling agent to schedule interviews for shortlisted candidates
    
    This agent will:
    1. Get previously shortlisted candidates for the job role
    2. Create calendar events with Google Meet links
    3. Send email notifications to candidates and interviewers
    4. Store interview records in the database
    """
    try:
        # Run the scheduling process in the background
        def run_scheduling():
            result = run_scheduling_process(
                job_role_name=request.job_role_name,
                interview_date=request.interview_date,
                number_of_rounds=request.number_of_rounds
            )
            print(f"Scheduling completed: {result}")
            return result
            
        # Add the background task
        background_tasks.add_task(run_scheduling)
        
        # Determine the display date
        display_date = request.interview_date if request.interview_date else "tomorrow"
        
        return {
            "status": "processing",
            "message": f"Scheduling interviews for job role '{request.job_role_name}' on {display_date} with {request.number_of_rounds} rounds",
            "job_role_name": request.job_role_name
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error scheduling interviews: {str(e)}",
        )

@router.post("/end-to-end")
async def end_to_end_process(request: EndToEndRequest, background_tasks: BackgroundTasks):
    """
    Use specialized agents to handle the complete interview process from shortlisting to scheduling
    
    This will:
    1. Shortlist top candidates based on AI fit scores
    2. Schedule interviews with calendar events and Google Meet links
    3. Send email notifications
    4. Store all records in the database
    """
    try:
        # Run the end-to-end process in the background
        def run_process():
            result = run_end_to_end_process(
                job_role_name=request.job_role_name,
                number_of_candidates=request.number_of_candidates,
                interview_date=request.interview_date,
                number_of_rounds=request.number_of_rounds
            )
            print(f"End-to-end process completed: {result}")
            return result
            
        # Add the background task
        background_tasks.add_task(run_process)
        
        # Determine the display date
        display_date = request.interview_date if request.interview_date else "tomorrow"
        
        return {
            "status": "processing",
            "message": f"Running complete interview process for job role '{request.job_role_name}': shortlisting {request.number_of_candidates} candidates and scheduling {request.number_of_rounds} interview rounds on {display_date}",
            "job_role_name": request.job_role_name
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in end-to-end process: {str(e)}",
        )

@router.get("/status/{job_role_name}")
async def get_process_status(job_role_name: str):
    """
    Check the status of specialized agent processes for a job role
    
    This endpoint will check:
    1. If candidates have been shortlisted
    2. If interviews have been scheduled
    """
    try:
        from app.database.chroma_db import FirestoreDB, ChromaVectorDB
        from app.services.job_service import JobService
        
        # First find the job_id from the job_role_name
        job = JobService.get_job_posting_by_role_name(job_role_name)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No job found with role name '{job_role_name}'",
            )
        
        job_id = job.id
        
        # Check for shortlisted candidates
        shortlisted = FirestoreDB.execute_query("shortlisted_candidates", "job_id", "==", job_id)
        
        # Check for scheduled interviews
        interviews = FirestoreDB.execute_query("interview_candidates", "job_id", "==", job_id)
        
        return {
            "job_role_name": job_role_name,
            "job_id": job_id,
            "shortlisting_complete": len(shortlisted) > 0,
            "shortlisted_count": len(shortlisted) if shortlisted else 0,
            "scheduling_complete": len(interviews) > 0,
            "scheduled_interviews": len(interviews) if interviews else 0,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking process status: {str(e)}",
        )
