from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from app.agents.langgraph_agent import get_langgraph_agent
from app.services.job_service import JobService
from app.services.candidate_service import CandidateService
import uuid
from datetime import datetime

# Create router
router = APIRouter(
    prefix="/langgraph",
    tags=["langgraph"],
    responses={404: {"description": "Not found"}},
)


class LangGraphRequest(BaseModel):
    query: str
    job_id: str
    candidate_ids: Optional[List[str]] = None


class LangGraphResponse(BaseModel):
    session_id: str
    job_id: str
    output: str
    analysis: Dict[str, Any]
    interview_plan: Dict[str, Any]
    interview_schedule: Dict[str, Any]
    thought_process: List[Dict[str, Any]]
    timestamp: str


@router.post("/process", response_model=LangGraphResponse)
async def process_with_langgraph(request: LangGraphRequest):
    """
    Process a query using the LangGraph-based interview agent system.
    
    This endpoint allows access to a sophisticated state-based agent workflow that:
    1. Analyzes job requirements
    2. Screens candidates
    3. Plans interview processes
    4. Schedules interviews
    
    All in one coordinated workflow.
    """
    try:
        # Verify job exists
        job = JobService.get_job_posting(request.job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job posting with ID {request.job_id} not found",
            )

        # Convert job to dictionary for the agent
        job_data = job.dict()
        
        # Get candidate data if provided
        candidate_data = None
        if request.candidate_ids:
            candidates = []
            for candidate_id in request.candidate_ids:
                candidate = CandidateService.get_candidate(candidate_id)
                if candidate:
                    candidates.append(candidate.dict())
            
            if candidates:
                candidate_data = {"candidates": candidates}
        
        # Get the agent
        langgraph_agent = get_langgraph_agent()
        
        # Process the query
        result = langgraph_agent.process_query(
            query=request.query,
            job_data=job_data,
            candidate_data=candidate_data
        )
        
        # Format the response
        session_id = str(uuid.uuid4())
        return {
            "session_id": session_id,
            "job_id": request.job_id,
            "output": result.get("output", "No output available"),
            "analysis": result.get("analysis", {}),
            "interview_plan": result.get("interview_plan", {}),
            "interview_schedule": result.get("interview_schedule", {}),
            "thought_process": result.get("thought_process", []),
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing with LangGraph: {str(e)}",
        )


@router.post("/analyze-job/{job_id}")
async def analyze_job(job_id: str):
    """
    Analyze a job posting using the LangGraph agent system
    """
    try:
        # Get job posting
        job = JobService.get_job_posting(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job posting with ID {job_id} not found",
            )
            
        # Convert to dict
        job_data = job.dict()
        
        # Get the agent
        langgraph_agent = get_langgraph_agent()
        
        # Create a simple query to analyze the job
        query = f"Please analyze the job posting for {job.job_role_name}"
        
        # Process with the agent
        result = langgraph_agent.process_query(
            query=query,
            job_data=job_data
        )
        
        return {
            "job_id": job_id,
            "job_title": job.job_role_name,
            "analysis": result.get("analysis", {}),
            "interview_plan": result.get("interview_plan", {}),
            "thought_process": result.get("thought_process", []),
            "output": result.get("output", "No output available")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing job with LangGraph: {str(e)}",
        )


@router.post("/plan-interviews/{job_id}")
async def plan_interviews(
    job_id: str, 
    candidate_ids: List[str]
):
    """
    Plan interviews for specific candidates using the LangGraph agent system
    """
    try:
        # Get job posting
        job = JobService.get_job_posting(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job posting with ID {job_id} not found",
            )
            
        # Get candidates
        candidates = []
        for candidate_id in candidate_ids:
            candidate = CandidateService.get_candidate(candidate_id)
            if candidate:
                candidates.append(candidate.dict())
        
        if not candidates:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No valid candidates found from the provided IDs",
            )
            
        # Prepare candidate data
        candidate_data = {"candidates": candidates}
        
        # Get the agent
        langgraph_agent = get_langgraph_agent()
        
        # Create a query to plan interviews
        query = f"Plan interviews for {len(candidates)} candidates for the {job.job_role_name} position"
        
        # Process with the agent
        result = langgraph_agent.process_query(
            query=query,
            job_data=job.dict(),
            candidate_data=candidate_data
        )
        
        return {
            "job_id": job_id,
            "job_title": job.job_role_name,
            "candidates": [c.get("name", "Unknown") for c in candidates],
            "interview_plan": result.get("interview_plan", {}),
            "interview_schedule": result.get("interview_schedule", {}),
            "thought_process": result.get("thought_process", []),
            "output": result.get("output", "No output available")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error planning interviews with LangGraph: {str(e)}",
        )
