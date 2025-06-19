"""
API routes for interview scheduling and management
"""
from fastapi import APIRouter, HTTPException, status, Path, Query
from typing import List, Dict, Any, Optional

from app.services.interview_service import InterviewService
from app.services.job_service import JobService
from app.schemas.interview_schema import (
    InterviewCandidateCreate, 
    InterviewCandidateResponse,
    InterviewFeedback,
    ShortlistRequest
)

router = APIRouter(
    prefix="/interviews",
    tags=["interviews"],
    responses={404: {"description": "Not found"}},
)


@router.post("/shortlist", response_model=Dict[str, Any])
async def shortlist_candidates(request: ShortlistRequest):
    """
    Shortlist candidates for a job and schedule interviews
    
    This endpoint:
    1. Gets the top N candidates for a job based on AI fit score
    2. Creates interview candidate records
    3. Schedules first round interviews
    
    Future rounds will be scheduled after each round is completed with positive feedback.
    """
    # Check if job exists
    job_data = JobService.get_job_posting(request.job_id)
    if not job_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {request.job_id} not found"
        )
    
    # Shortlist candidates
    shortlisted, created_records = InterviewService.shortlist_candidates(
        request.job_id, 
        request.number_of_candidates,
        request.no_of_interviews
    )
    
    if not shortlisted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No candidates found for job {request.job_id}"
        )
    
    # Schedule initial interviews (only first round)
    scheduled = InterviewService.schedule_interviews(created_records, job_data)
    
    # Return results
    return {
        "job_id": request.job_id,
        "shortlisted_count": len(shortlisted),
        "candidates": shortlisted,
        "interview_records": created_records,
        "scheduled_events": scheduled
    }


@router.get("/job/{job_id}", response_model=List[Dict[str, Any]])
async def get_interview_candidates_for_job(job_id: str):
    """
    Get all interview candidates for a job
    """
    candidates = InterviewService.get_interview_candidates_by_job_id(job_id)
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No interview candidates found for job {job_id}"
        )
    return candidates


@router.get("/{interview_id}", response_model=Dict[str, Any])
async def get_interview_candidate(interview_id: str):
    """
    Get a specific interview candidate by ID
    """
    candidate = InterviewService.get_interview_candidate(interview_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview candidate with ID {interview_id} not found"
        )
    return candidate


@router.put("/{interview_id}/feedback", response_model=Dict[str, Any])
async def update_interview_feedback(
    interview_id: str, 
    feedback: InterviewFeedback,
    round_index: int = Query(0, description="Index of the interview round (0-based)")
):
    """
    Update feedback for a specific interview round
    
    This endpoint updates the feedback for a specific round of an interview.
    If the feedback indicates the candidate should proceed to the next round (isSelectedForNextRound="yes"),
    and all feedback fields are provided, the next round will be scheduled automatically.
    """
    # Get the interview candidate
    candidate = InterviewService.get_interview_candidate(interview_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview candidate with ID {interview_id} not found"
        )
    
    # Check if round index is valid
    if round_index < 0 or round_index >= len(candidate.get("feedback", [])):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid round index {round_index}. Valid range: 0-{len(candidate.get('feedback', [])) - 1}"
        )
    
    # Update the feedback
    feedback_list = candidate.get("feedback", [])
    
    # Update specific fields
    round_data = feedback_list[round_index]
    if feedback.isSelectedForNextRound is not None:
        round_data["isSelectedForNextRound"] = feedback.isSelectedForNextRound
    if feedback.feedback is not None:
        round_data["feedback"] = feedback.feedback
    if feedback.rating_out_of_10 is not None:
        round_data["rating_out_of_10"] = feedback.rating_out_of_10
    
    # Update the candidate
    InterviewService.update_interview_candidate(
        interview_id,
        {"feedback": feedback_list}
    )
    
    # Check if we should schedule the next round
    schedule_next = (
        feedback.isSelectedForNextRound == "yes" and 
        feedback.feedback and 
        feedback.rating_out_of_10
    )
    
    next_round_scheduled = False
    if schedule_next and round_index < candidate.get("no_of_interviews", 0) - 1:
        next_round_scheduled = InterviewService.schedule_next_round(interview_id)
    
    # Return the updated candidate with scheduling info
    updated_candidate = InterviewService.get_interview_candidate(interview_id)
    return {
        "interview_candidate": updated_candidate,
        "feedback_updated": True,
        "next_round_scheduled": next_round_scheduled
    }


@router.post("/{interview_id}/schedule-next-round")
async def schedule_next_interview_round(interview_id: str):
    """
    Schedule the next round of interviews for a candidate
    
    This endpoint checks if the previous round is completed with positive feedback,
    and schedules the next round if conditions are met.
    """
    result = InterviewService.schedule_next_round(interview_id)
    
    if result:
        return {"status": "success", "message": "Next interview round scheduled successfully"}
    else:
        return {"status": "error", "message": "Unable to schedule next round. Check logs for details."}
