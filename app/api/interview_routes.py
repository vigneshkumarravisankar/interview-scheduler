"""
API routes for interview scheduling and management
"""
from fastapi import APIRouter, HTTPException, Path, Query
from fastapi import status as http_status
from typing import List, Dict, Any, Optional

from app.services.interview_service import InterviewService
from app.services.job_service import JobService
from app.services.interview_tracking_service import InterviewTrackingService
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
    
    You can optionally specify which interviewers to use for each round by providing 
    their IDs in the specific_interviewers field.
    """
    # Check if job exists
    job_data = JobService.get_job_posting(request.job_id)
    if not job_data:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {request.job_id} not found"
        )
    
    # Shortlist candidates
    shortlisted, created_records = InterviewService.shortlist_candidates(
        request.job_id, 
        request.number_of_candidates,
        request.no_of_interviews,
        request.specific_interviewers
    )
    
    if not shortlisted:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"No candidates found for job {request.job_id}"
        )
    
    # Convert job_data (JobPostingResponse) to a dictionary
    job_data_dict = {
        "job_id": job_data.job_id,
        "job_role_name": job_data.job_role_name,
        "job_description": job_data.job_description,
        "years_of_experience_needed": job_data.years_of_experience_needed
    }
    
    # Schedule initial interviews (only first round)
    scheduled = InterviewService.schedule_interviews(created_records, job_data_dict)
    
    # Initialize tracking status for each candidate
    for candidate in created_records:
        InterviewTrackingService.update_interview_tracking_status(candidate.get('id'))
    
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
            status_code=http_status.HTTP_404_NOT_FOUND,
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
            status_code=http_status.HTTP_404_NOT_FOUND,
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
    
    This endpoint updates the feedback for a specific round of an interview and
    automatically updates tracking status. For round 0:
    
    - If completedRounds becomes 1, status is set to "completed"
    - If gmeet_link exists and completedRounds is 1, status is set to "scheduled"
    - If feedback is positive (isSelectedForNextRound="yes"), the next round's Google Meet
      link and scheduled time are generated automatically
    
    After calling this endpoint, check the "next_steps" field in the response to know what
    API to call next based on the updated status.
    """
    # Get the interview candidate
    candidate = InterviewService.get_interview_candidate(interview_id)
    if not candidate:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Interview candidate with ID {interview_id} not found"
        )
    
    # Check if feedback array exists and is not empty
    feedback_array = candidate.get("feedback", [])
    if not feedback_array:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"No feedback rounds found for interview candidate {interview_id}"
        )
    
    # Check if round index is valid
    if round_index < 0 or round_index >= len(feedback_array):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid round index {round_index}. Valid range: 0-{len(feedback_array) - 1}"
        )
    
    # Update the feedback using new feedback submission method
    result = InterviewTrackingService.submit_interview_feedback(
        candidate_id=interview_id,
        round_index=round_index,
        feedback=feedback.feedback,
        rating=feedback.rating_out_of_10,
        selected_for_next=(feedback.isSelectedForNextRound == "yes")
    )
    
    if not result:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update feedback for interview candidate {interview_id}"
        )
    
    # Get the updated candidate and ensure the initialization of the feedback array
    InterviewTrackingService.initialize_feedback_array(interview_id)
    updated_candidate = InterviewService.get_interview_candidate(interview_id)
    
    # Determine next steps based on current status and completed rounds
    interview_status = updated_candidate.get("status", "unknown")
    completed_rounds = updated_candidate.get("completedRounds", 0)
    feedback_list = updated_candidate.get("feedback", [])
    next_steps = []
    next_api_call = None
    
    if interview_status == "selected" or interview_status == "completed":
        next_steps = ["Candidate has completed the interview process", 
                      "Consider the candidate for final selection"]
        next_api_call = f"POST /final-selections/job/{updated_candidate.get('job_id')}/select with compensation_offered"
    
    elif interview_status == "rejected":
        next_steps = ["Candidate was rejected", 
                      "No further action needed for this candidate"]
        next_api_call = None
    
    elif interview_status == "scheduled" and completed_rounds >= 1:
        # The feedback was good and next interview is scheduled
        if len(feedback_list) > completed_rounds and feedback_list[completed_rounds].get("meet_link"):
            next_round_info = feedback_list[completed_rounds]
            next_steps = [
                f"Candidate is scheduled for round {completed_rounds + 1} interview",
                f"Google Meet link: {next_round_info.get('meet_link')}",
                f"Scheduled time: {next_round_info.get('scheduled_time', 'TBD')}"
            ]
            next_api_call = f"GET /interviews/{interview_id} to check interview details"
    
    elif interview_status == "in_progress":
        next_steps = ["Candidate is in the interview process", 
                      "Wait for feedback from the current round"]
        next_api_call = f"GET /interviews/{interview_id} to check interview status"
        
    else:  # Default case
        next_steps = ["Continue with the interview process"]
        next_api_call = f"GET /interviews/{interview_id} to check interview status"
    
    # Check if the next round has a meet link generated (indicating it was scheduled)
    next_round_scheduled = False
    next_round_link = None
    next_round_time = None
    
    if round_index + 1 < len(feedback_list):
        next_round = feedback_list[round_index + 1]
        if next_round.get("meet_link"):
            next_round_scheduled = True
            next_round_link = next_round.get("meet_link")
            next_round_time = next_round.get("scheduled_time")
    
    return {
        "interview_candidate": updated_candidate,
        "feedback_updated": True,
        "completedRounds": completed_rounds,
        "status": interview_status,
        "next_round_scheduled": next_round_scheduled,
        "next_round_link": next_round_link,
        "next_round_time": next_round_time,
        "next_steps": next_steps,
        "next_api_call": next_api_call
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
        # Update tracking status after scheduling
        InterviewTrackingService.update_interview_tracking_status(interview_id)
        updated_candidate = InterviewService.get_interview_candidate(interview_id)
        return {
            "status": "success", 
            "message": "Next interview round scheduled successfully",
            "completedRounds": updated_candidate.get("completedRounds", 0),
            "status": updated_candidate.get("status", "unknown")
        }
    else:
        return {"status": "error", "message": "Unable to schedule next round. Check logs for details."}


@router.post("/{interview_id}/initialize-feedback", response_model=Dict[str, Any])
async def initialize_interview_feedback(
    interview_id: str,
    num_rounds: int = Query(2, description="Number of interview rounds to initialize")
):
    """
    Initialize the feedback structure for an interview candidate
    
    This endpoint ensures that the candidate has a properly structured feedback array
    with the specified number of rounds, each with Google Meet links and scheduled times.
    
    Use this endpoint if you encounter issues with feedback submission due to
    missing or malformed feedback structures.
    """
    # Get the interview candidate
    candidate = InterviewService.get_interview_candidate(interview_id)
    if not candidate:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Interview candidate with ID {interview_id} not found"
        )
    
    # Initialize the feedback array
    result = InterviewTrackingService.initialize_feedback_array(interview_id, num_rounds)
    
    if not result:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize feedback array for candidate {interview_id}"
        )
    
    # Get the updated candidate
    updated_candidate = InterviewService.get_interview_candidate(interview_id)
    
    return {
        "status": "success",
        "message": f"Feedback array initialized with {num_rounds} rounds",
        "interview_candidate": updated_candidate
    }


@router.get("/interviewers", response_model=List[Dict[str, Any]])
async def get_all_interviewers():
    """
    Get all available interviewers
    
    This endpoint returns a list of all interviewers that can be assigned to interview rounds.
    """
    interviewers = InterviewService.get_all_interviewers()
    if not interviewers:
        return []
    return interviewers


@router.post("/update-tracking")
async def update_all_tracking_status():
    """
    Update tracking status for all interview candidates
    
    This endpoint updates the completedRounds and status fields for all interview candidates
    based on their feedback data.
    
    Returns:
        Dictionary with counts of updated and failed records
    """
    result = InterviewTrackingService.bulk_update_tracking_status()
    return result


@router.get("/job/{job_id}/statistics")
async def get_interview_statistics_by_job(job_id: str):
    """
    Get statistics about interview candidates for a job
    
    Returns counts of candidates in each status category:
    - scheduled: Initial state, no interviews completed yet
    - in_progress: Some rounds completed, more pending
    - rejected: Failed in one of the rounds
    - passed: Passed a round but not all rounds
    - selected: Completed all rounds and selected
    - completed: Completed all rounds but not explicitly selected
    - total: Total number of candidates
    """
    # First ensure all candidates have updated tracking status
    candidates = InterviewService.get_interview_candidates_by_job_id(job_id)
    
    # Update tracking status for all candidates in this job
    for candidate in candidates:
        InterviewTrackingService.update_interview_tracking_status(candidate.get('id'))
    
    # Get fresh statistics
    stats = InterviewService.get_tracking_statistics_by_job(job_id)
    return stats
