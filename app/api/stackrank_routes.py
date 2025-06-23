"""
API Routes for Stackranking Operations
"""
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from app.services.stackrank_service import StackrankService

# Create router
router = APIRouter(
    prefix="/api/stackrank",
    tags=["stackrank"],
)

class StackrankRequest(BaseModel):
    """Request model for stackranking"""
    job_role_name: str = Field(..., description="Job role name (case insensitive)")
    top_percentage: float = Field(1.0, description="Percentage of top candidates to select (default: 1.0)")
    compensation_offered: str = Field("", description="Compensation to offer (optional)")
    joining_date: str = Field("", description="Joining date for selected candidates (YYYY-MM-DD format)")

class CandidateInfo(BaseModel):
    """Candidate information model"""
    candidate_name: str
    candidate_email: str
    total_score: int
    feedback_rounds: int
    average_score: float

class StackrankResponse(BaseModel):
    """Response model for stackranking"""
    success: bool
    job_role: Optional[str] = None
    job_id: Optional[str] = None
    eligible_candidates: int
    selected_candidates: int
    top_percentage: Optional[float] = None
    compensation_offered: Optional[str] = None
    joining_date: Optional[str] = None
    candidates: List[CandidateInfo] = []
    error: Optional[str] = None

class JobValidationResponse(BaseModel):
    """Response model for job validation"""
    exists: bool
    job_id: Optional[str] = None
    job_role_name: str
    message: str

class CandidateCountResponse(BaseModel):
    """Response model for candidate count"""
    success: bool
    job_role: Optional[str] = None
    job_id: Optional[str] = None
    total_candidates: int
    eligible_candidates: int
    ineligible_candidates: Optional[int] = None
    error: Optional[str] = None

@router.post("/process", response_model=StackrankResponse)
async def stackrank_candidates(request: StackrankRequest):
    """
    Stackrank candidates for a specific job role
    
    This endpoint:
    1. Finds the job_id from jobs collection using job_role_name (case insensitive)
    2. Queries interview_candidates collection using the job_id
    3. Applies eligibility criteria: feedback != null, isSelectedForNextRound == 'yes', rating_out_of_10 != null
    4. Ranks candidates by total interview scores
    5. Selects top percentage of candidates
    6. Moves selected candidates to final_candidates collection
    
    Args:
        request: StackrankRequest with job_role_name and optional parameters
        
    Returns:
        StackrankResponse with results of the stackranking process
    """
    try:
        # Call the stackranking service
        result = StackrankService.stackrank_by_job_role(
            job_role_name=request.job_role_name,
            top_percentage=request.top_percentage,
            compensation_offered=request.compensation_offered,
            joining_date=request.joining_date
        )
        
        # Convert result to response model
        candidates_info = []
        for candidate in result.get('candidates', []):
            candidates_info.append(CandidateInfo(
                candidate_name=candidate['candidate_name'],
                candidate_email=candidate['candidate_email'],
                total_score=candidate['total_score'],
                feedback_rounds=candidate['feedback_rounds'],
                average_score=candidate['average_score']
            ))
        
        return StackrankResponse(
            success=result['success'],
            job_role=result.get('job_role'),
            job_id=result.get('job_id'),
            eligible_candidates=result['eligible_candidates'],
            selected_candidates=result['selected_candidates'],
            top_percentage=result.get('top_percentage'),
            compensation_offered=result.get('compensation_offered'),
            joining_date=result.get('joining_date'),
            candidates=candidates_info,
            error=result.get('error')
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing stackrank request: {str(e)}")

@router.get("/validate-job/{job_role_name}", response_model=JobValidationResponse)
async def validate_job_role(job_role_name: str):
    """
    Validate if a job role exists in the jobs collection
    
    Args:
        job_role_name: Job role name to validate (case insensitive)
        
    Returns:
        JobValidationResponse with validation results
    """
    try:
        result = StackrankService.validate_job_role_exists(job_role_name)
        
        return JobValidationResponse(
            exists=result['exists'],
            job_id=result['job_id'],
            job_role_name=result['job_role_name'],
            message=result['message']
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating job role: {str(e)}")

@router.get("/candidates-count/{job_role_name}", response_model=CandidateCountResponse)
async def get_candidates_count(job_role_name: str):
    """
    Get count of candidates for a specific job role
    
    This endpoint shows:
    - Total candidates who applied for the job
    - Eligible candidates who meet stackranking criteria
    - Ineligible candidates who don't meet criteria
    
    Args:
        job_role_name: Job role name (case insensitive)
        
    Returns:
        CandidateCountResponse with candidate counts
    """
    try:
        result = StackrankService.get_candidates_count_for_job_role(job_role_name)
        
        return CandidateCountResponse(
            success=result['success'],
            job_role=result.get('job_role'),
            job_id=result.get('job_id'),
            total_candidates=result['total_candidates'],
            eligible_candidates=result['eligible_candidates'],
            ineligible_candidates=result.get('ineligible_candidates'),
            error=result.get('error')
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting candidates count: {str(e)}")

@router.get("/", tags=["stackrank"])
async def stackrank_info():
    """
    Get information about the stackranking system
    
    Returns:
        Information about available stackranking endpoints and their usage
    """
    return {
        "message": "Stackranking API - Direct access without CrewAI",
        "description": "This API allows you to stackrank candidates by job role name",
        "workflow": {
            "1": "Provide job role name (case insensitive)",
            "2": "System finds job_id from jobs collection",
            "3": "System queries interview_candidates using job_id", 
            "4": "Applies eligibility criteria: feedback != null, isSelectedForNextRound == 'yes', rating_out_of_10 != null",
            "5": "Ranks candidates by total interview scores",
            "6": "Selects top percentage of candidates",
            "7": "Moves selected candidates to final_candidates collection"
        },
        "endpoints": {
            "POST /api/stackrank/process": "Stackrank candidates for a job role",
            "GET /api/stackrank/validate-job/{job_role_name}": "Validate if job role exists",
            "GET /api/stackrank/candidates-count/{job_role_name}": "Get candidate counts for job role"
        },
        "eligibility_criteria": {
            "feedback": "Must not be null",
            "isSelectedForNextRound": "Must be 'yes'", 
            "rating_out_of_10": "Must not be null"
        }
    }
