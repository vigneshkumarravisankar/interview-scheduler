from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, Query, BackgroundTasks
from app.services.interview_shortlist_service import InterviewShortlistService
from app.services.job_service import JobService
from app.agents.crew_agent_system import get_agent_system
from pydantic import BaseModel

# Create router
router = APIRouter(
    prefix="/shortlist",
    tags=["shortlist"],
    responses={404: {"description": "Not found"}},
)


class ShortlistRequest(BaseModel):
    job_id: str
    number_of_candidates: int = 3
    number_of_rounds: int = 2
    specific_time: Optional[str] = None


class ShortlistResponse(BaseModel):
    job_id: str
    shortlisted_count: int
    candidates: List[Dict[str, Any]]
    interview_records: List[Dict[str, Any]]


@router.post("/", response_model=ShortlistResponse)
async def shortlist_candidates(request: ShortlistRequest):
    """
    Shortlist top candidates for interviews based on AI fit scores.
    This will:
    1. Get candidates with highest fit scores for a job
    2. Schedule interviews with available interviewers
    3. Create interview records in Firebase
    4. Send calendar invites and email notifications
    """
    try:
        # Verify job exists
        job = JobService.get_job_posting(request.job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job posting with ID {request.job_id} not found",
            )

        # Use the shortlist service directly
        shortlisted, interview_records = InterviewShortlistService.shortlist_candidates(
            job_id=request.job_id,
            number_of_candidates=request.number_of_candidates,
            no_of_interviews=request.number_of_rounds
        )
        
        if not shortlisted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No candidates found for job {request.job_id} or shortlisting failed",
            )

        return {
            "job_id": request.job_id,
            "shortlisted_count": len(shortlisted),
            "candidates": shortlisted,
            "interview_records": interview_records
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error shortlisting candidates: {str(e)}",
        )


@router.post("/agent", response_model=Dict[str, Any])
async def agent_shortlist_candidates(request: ShortlistRequest, background_tasks: BackgroundTasks):
    """
    Use the CrewAI agent system to shortlist candidates and schedule interviews.
    This provides a more intelligent shortlisting with natural language processing.
    """
    try:
        # Get the agent system
        agent_system = get_agent_system()
        
        # Create a query for the agent to process
        query = f"Shortlist {request.number_of_candidates} candidates for job_id: {request.job_id} with {request.number_of_rounds} interview rounds"
        
        # If specific time is provided, add it to the query
        if request.specific_time:
            query += f" at {request.specific_time}"
        
        # Create a session ID for this request
        session_id = f"shortlist-{request.job_id}-{request.number_of_candidates}"
        
        # Process the query with the agent system
        result = agent_system.process_query(query, session_id)
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error using agent to shortlist candidates: {str(e)}",
        )


@router.get("/job/{job_id}", response_model=List[Dict[str, Any]])
async def get_interview_candidates_by_job(
    job_id: str, 
    status: Optional[str] = Query(None, description="Filter by status (scheduled, completed, cancelled)")
):
    """
    Get all interview candidates for a specific job
    """
    from app.services.interview_core_service import InterviewCoreService
    
    try:
        # Get all interview candidates for the job
        candidates = InterviewCoreService.get_interview_candidates_by_job_id(job_id)
        
        # Filter by status if provided
        if status:
            candidates = [c for c in candidates if c.get("status") == status]
            
        return candidates
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting interview candidates: {str(e)}",
        )
