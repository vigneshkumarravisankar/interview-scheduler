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
    job_id: str
    number_of_candidates: int = Field(default=2, description="Number of candidates to shortlist (default 2)")
    
class ShortlistByRoleRequest(BaseModel):
    role_name: str = Field(..., description="Name of the job role to shortlist candidates for (e.g., 'AI Engineer')")
    number_of_candidates: int = Field(default=2, description="Number of candidates to shortlist (default 2)")

class ScheduleRequest(BaseModel):
    job_id: str
    interview_date: Optional[str] = Field(None, description="Date for interviews in YYYY-MM-DD format (default: tomorrow)")
    number_of_rounds: int = Field(default=2, description="Number of interview rounds (default 2)")

class EndToEndRequest(BaseModel):
    job_id: str
    number_of_candidates: int = Field(default=2, description="Number of candidates to shortlist (default 2)")
    interview_date: Optional[str] = Field(None, description="Date for interviews in YYYY-MM-DD format (default: tomorrow)")
    number_of_rounds: int = Field(default=2, description="Number of interview rounds (default 2)")

@router.post("/shortlist")
async def shortlist_candidates(request: ShortlistRequest, background_tasks: BackgroundTasks):
    """
    Use the specialized shortlisting agent to select top candidates based on AI fit scores
    
    This agent will:
    1. Get all candidates for the specified job
    2. Rank them by AI fit score
    3. Select the top N candidates
    4. Store them directly in interview_candidates collection
    """
    try:
        # Run the shortlisting process in the background
        def run_shortlisting():
            result = run_shortlisting_process(
                job_id=request.job_id,
                number_of_candidates=request.number_of_candidates
            )
            print(f"Shortlisting completed: {result}")
            return result
            
        # Add the background task
        background_tasks.add_task(run_shortlisting)
        
        return {
            "status": "processing",
            "message": f"Shortlisting top {request.number_of_candidates} candidates for job {request.job_id}",
            "job_id": request.job_id
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error shortlisting candidates: {str(e)}",
        )
        
@router.post("/shortlist-by-role")
async def shortlist_candidates_by_role(request: ShortlistByRoleRequest, background_tasks: BackgroundTasks):
    """
    Find a job by role name and shortlist top candidates for that job
    
    This agent will:
    1. Search for a job with the specified role name in the jobs collection
    2. Get all candidates for that job from candidates_data collection
    3. Rank them by AI fit score
    4. Select the top N candidates
    5. Store them directly in interview_candidates collection
    """
    try:
        # Run a custom shortlisting process for role in the background
        def run_shortlisting_by_role():
            # Create a shortlisting task specifically for role name
            shortlisting_task = Task(
                description=f"""
                Shortlist the top {request.number_of_candidates} candidates for the role: "{request.role_name}".
                
                Steps:
                1. Find the job with role name "{request.role_name}" in the jobs collection
                2. Get all candidates for this job
                3. Shortlist the top {request.number_of_candidates} candidates based on AI fit scores
                4. Store the candidates directly in the interview_candidates collection
                
                Use the ShortlistCandidatesByRole tool for this task.
                """,
                expected_output=f"List of top {request.number_of_candidates} candidates for role '{request.role_name}', sorted by AI fit score",
                agent=shortlisting_agent
            )
            
            # Create a simple crew with just this task
            crew = Crew(
                agents=[shortlisting_agent],
                tasks=[shortlisting_task],
                verbose=True,
                process=Process.sequential
            )
            
            result = crew.kickoff()
            print(f"Role-based shortlisting completed: {result}")
            return result
            
        # Add the background task
        background_tasks.add_task(run_shortlisting_by_role)
        
        return {
            "status": "processing",
            "message": f"Finding job and shortlisting top {request.number_of_candidates} candidates for role '{request.role_name}'",
            "role_name": request.role_name
        }
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
    1. Get previously shortlisted candidates for the job
    2. Create calendar events with Google Meet links
    3. Send email notifications to candidates and interviewers
    4. Store interview records in the database
    """
    try:
        # Run the scheduling process in the background
        def run_scheduling():
            result = run_scheduling_process(
                job_id=request.job_id,
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
            "message": f"Scheduling interviews for job {request.job_id} on {display_date} with {request.number_of_rounds} rounds",
            "job_id": request.job_id
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
                job_id=request.job_id,
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
            "message": f"Running complete interview process for job {request.job_id}: shortlisting {request.number_of_candidates} candidates and scheduling {request.number_of_rounds} interview rounds on {display_date}",
            "job_id": request.job_id
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in end-to-end process: {str(e)}",
        )

@router.get("/status/{job_id}")
async def get_process_status(job_id: str):
    """
    Check the status of specialized agent processes for a job
    
    This endpoint will check:
    1. If candidates have been shortlisted
    2. If interviews have been scheduled
    """
    try:
        from app.database.firebase_db import FirestoreDB
        
        # Check for shortlisted candidates
        shortlisted = FirestoreDB.execute_query("shortlisted_candidates", "job_id", "==", job_id)
        
        # Check for scheduled interviews
        interviews = FirestoreDB.execute_query("interview_candidates", "job_id", "==", job_id)
        
        return {
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
