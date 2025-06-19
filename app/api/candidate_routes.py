from fastapi import APIRouter, HTTPException, status, Query, Path
from typing import List, Dict, Any, Optional
from pydantic import UUID4

from app.services.candidate_service import CandidateService, extract_resume_data
from app.services.job_service import JobService
from app.schemas.candidate_schema import CandidateCreate, CandidateResponse, CandidateUpdate

router = APIRouter(
    prefix="/candidates",
    tags=["candidates"],
    responses={404: {"description": "Not found"}},
)


@router.get("/", response_model=List[CandidateResponse])
async def get_all_candidates(
    job_id: Optional[str] = Query(None, description="Filter candidates by job ID")
):
    """
    Get all candidates, optionally filtered by job ID
    """
    try:
        if job_id:
            candidates = CandidateService.get_candidates_by_job_id(job_id)
        else:
            candidates = CandidateService.get_all_candidates()
        
        return candidates
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get candidates: {str(e)}"
        )


@router.get("/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(
    candidate_id: str = Path(..., description="ID of the candidate to get")
):
    """
    Get a single candidate by ID
    """
    candidate = CandidateService.get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate with ID {candidate_id} not found"
        )
    return candidate


@router.put("/{candidate_id}", response_model=CandidateResponse)
async def update_candidate(
    update_data: CandidateUpdate,
    candidate_id: str = Path(..., description="ID of the candidate to update")
):
    """
    Update a candidate
    """
    # Check if candidate exists
    candidate = CandidateService.get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate with ID {candidate_id} not found"
        )
    
    try:
        # Convert to dict and remove None values
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        
        # Update candidate
        CandidateService.update_candidate(candidate_id, update_dict)
        
        # Get updated candidate
        updated = CandidateService.get_candidate(candidate_id)
        
        return updated
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update candidate: {str(e)}"
        )


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate(
    candidate_id: str = Path(..., description="ID of the candidate to delete")
):
    """
    Delete a candidate
    """
    # Check if candidate exists
    candidate = CandidateService.get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate with ID {candidate_id} not found"
        )
    
    try:
        CandidateService.delete_candidate(candidate_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete candidate: {str(e)}"
        )


@router.post("/process/{job_id}", response_model=List[CandidateResponse])
async def process_resumes_for_job(
    job_id: str = Path(..., description="ID of the job to process resumes for")
):
    """
    Process all resumes for a specific job
    
    This endpoint:
    1. Fetches resumes from Google Cloud Storage
    2. Extracts text using pdfplumber
    3. Analyzes resumes with LLM
    4. Calculates candidate fit scores
    5. Stores results in Firestore
    """
    # Check if job exists
    job = JobService.get_job_posting(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found"
        )
    
    try:
        # Extract resume data
        job_data = job.dict() if hasattr(job, 'dict') else job
        candidates = extract_resume_data(job_id, job_data)
        
        if not candidates:
            return []
        
        return candidates
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process resumes: {str(e)}"
        )


@router.post("/", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
async def create_candidate(candidate: CandidateCreate):
    """
    Create a new candidate manually
    """
    try:
        # Convert to dict
        candidate_dict = candidate.dict()
        
        # Create candidate
        candidate_id = CandidateService.create_candidate(candidate_dict)
        
        # Add ID to the response
        candidate_dict["id"] = candidate_id
        
        return candidate_dict
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create candidate: {str(e)}"
        )


@router.get("/job/{job_id}/top", response_model=List[CandidateResponse])
async def get_top_candidates(
    job_id: str = Path(..., description="ID of the job"),
    limit: int = Query(5, description="Number of top candidates to return")
):
    """
    Get top candidates for a job by AI fit score
    """
    try:
        # Get candidates for job
        candidates = CandidateService.get_candidates_by_job_id(job_id)
        
        # Sort by AI fit score (descending)
        sorted_candidates = sorted(
            candidates,
            key=lambda c: int(c.get("ai_fit_score", 0)),
            reverse=True
        )
        
        # Return top N candidates
        return sorted_candidates[:limit]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get top candidates: {str(e)}"
        )


@router.get("/job/{job_id}", response_model=Dict[str, Any])
async def get_candidates_with_job_details(
    job_id: str = Path(..., description="ID of the job")
):
    """
    Get all candidates for a specific job with job role name included
    
    Returns:
        Dictionary with job details and list of candidates
    """
    try:
        # Get job details
        job = JobService.get_job_posting(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job with ID {job_id} not found"
            )
        
        # Get candidates for job
        candidates = CandidateService.get_candidates_by_job_id(job_id)
        
        # Return both job details and candidates
        return {
            "job_id": job_id,
            "job_role_name": job.job_role_name,
            "job_description": job.job_description,
            "years_of_experience_needed": job.years_of_experience_needed,
            "candidates": candidates,
            "candidate_count": len(candidates)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get candidates with job details: {str(e)}"
        )
