"""
API routes for final candidate selection and offer letter generation
"""
from fastapi import APIRouter, HTTPException, status, Path, Query, BackgroundTasks
from typing import List, Dict, Any, Optional

from app.services.final_selection_service import FinalSelectionService
from app.services.job_service import JobService
from app.schemas.final_candidate_schema import FinalCandidateResponse


router = APIRouter(
    prefix="/final-selection",
    tags=["final selection"],
    responses={404: {"description": "Not found"}},
)


@router.get("/stackrank/{job_id}", response_model=List[Dict[str, Any]])
async def stackrank_candidates(job_id: str):
    """
    Stack rank candidates for a job based on interview feedback scores
    
    This endpoint:
    1. Gets all interview candidates for the job
    2. Filters candidates with complete feedback
    3. Calculates total scores for each candidate
    4. Sorts candidates by total score (descending)
    
    Only candidates who have received ratings in all interview rounds will be considered.
    """
    # Check if job exists
    job_data = JobService.get_job_posting(job_id)
    if not job_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found"
        )
    
    # Stack rank candidates
    ranked_candidates = FinalSelectionService.stackrank_candidates(job_id)
    
    if not ranked_candidates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No eligible candidates found for job {job_id}"
        )
    
    return ranked_candidates


@router.get("/top-candidate/{job_id}", response_model=Dict[str, Any])
async def get_top_candidate(job_id: str):
    """
    Get the top candidate for a job
    
    This endpoint:
    1. Stack ranks candidates for the job
    2. Returns the top candidate with their interview data and candidate details
    
    Returns HTTP 404 if no eligible candidates are found.
    """
    # Check if job exists
    job_data = JobService.get_job_posting(job_id)
    if not job_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found"
        )
    
    # Get top candidate
    top_candidate = FinalSelectionService.select_top_candidate(job_id)
    
    if not top_candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No eligible candidates found for job {job_id}"
        )
    
    return top_candidate


@router.post("/send-offer/{job_id}", response_model=FinalCandidateResponse)
async def send_offer_letter(
    background_tasks: BackgroundTasks,
    job_id: str,
    compensation_offered: str = Query(..., description="Compensation to offer the candidate (e.g., '$100,000 per year')")
):
    """
    Select the top candidate and send an offer letter
    
    This endpoint:
    1. Stack ranks candidates for the job
    2. Selects the top candidate
    3. Creates a final candidate record or updates existing one with compensation
    4. Sends an offer letter to the candidate by email
    
    The offer letter is sent in HTML format and includes the candidate's name, job title,
    and compensation offered.
    
    Returns HTTP 404 if no eligible candidates are found.
    
    Note: When running stackrank, the top candidate is automatically added to the final_candidates
    collection with a status of 'selected'. This endpoint updates that record with compensation
    and changes the status to 'offered'.
    """
    try:
        print(f"Processing offer letter request for job {job_id} with compensation {compensation_offered}")
        
        # Check if job exists
        job_data = JobService.get_job_posting(job_id)
        if not job_data:
            print(f"Job with ID {job_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job with ID {job_id} not found"
            )
        
        # First try to stackrank to make sure we have candidates
        ranked_candidates = FinalSelectionService.stackrank_candidates(job_id)
        if not ranked_candidates:
            print(f"ERROR: No ranked candidates found for job {job_id}. Check that interviews have been conducted and feedback provided.")
            # Return more helpful error message
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No ranked candidates found for job {job_id}. Make sure that all interviews have been conducted and feedback provided (including ratings and isSelectedForNextRound values)."
            )
        
        print(f"Found {len(ranked_candidates)} ranked candidates. Proceeding with top candidate.")
        
        # Select top candidate and send offer
        success, final_candidate = await FinalSelectionService.select_and_send_offer(
            job_id=job_id,
            compensation_offered=compensation_offered,
            background_tasks=background_tasks
        )
        
        if not success or not final_candidate:
            print(f"ERROR: Failed to select candidate or send offer letter for job {job_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Failed to select candidate or send offer letter for job {job_id}. See server logs for details."
            )
        
        print(f"Successfully sent offer to candidate {final_candidate.candidate_name}")
        return final_candidate
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error in send_offer_letter: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the offer: {str(e)}"
        )


@router.get("/offers/{job_id}", response_model=List[FinalCandidateResponse])
async def get_offers_for_job(job_id: str):
    """
    Get all offers sent for a job
    
    This endpoint returns a list of all final candidates for the specified job
    who have received offer letters.
    """
    # Check if job exists
    job_data = JobService.get_job_posting(job_id)
    if not job_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found"
        )
    
    # Get final candidates for the job
    offers = FinalSelectionService.get_final_candidates_by_job_id(job_id)
    
    return [FinalCandidateResponse(**offer) for offer in offers]


@router.get("/offer/{candidate_id}", response_model=FinalCandidateResponse)
async def get_offer_for_candidate(candidate_id: str):
    """
    Get offer details for a specific candidate
    
    This endpoint returns the offer details for a specific candidate.
    """
    # Get final candidate
    offer = FinalSelectionService.get_final_candidate(candidate_id)
    
    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Offer for candidate with ID {candidate_id} not found"
        )
    
    return FinalCandidateResponse(**offer)
