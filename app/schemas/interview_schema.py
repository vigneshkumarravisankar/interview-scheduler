"""
Schemas for interview scheduling and management
"""
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional, Union, Literal


class InterviewFeedback(BaseModel):
    """Schema for interview feedback"""
    isSelectedForNextRound: Optional[str] = Field(None, description="Whether the candidate is selected for the next round")
    feedback: Optional[str] = Field(None, description="Feedback from the interviewer")
    rating_out_of_10: Optional[int] = Field(None, description="Rating out of 10", ge=1, le=10)
    
    @validator('isSelectedForNextRound')
    def validate_selection(cls, v):
        if v is not None and v not in ["yes", "no", "maybe"]:
            raise ValueError('isSelectedForNextRound must be one of: "yes", "no", "maybe"')
        return v


class InterviewerBase(BaseModel):
    """Base schema for interviewer information"""
    interviewer_email: str
    interviewer_name: str
    

class InterviewFeedbackResponse(InterviewerBase):
    """Schema for feedback response"""
    isSelectedForNextRound: Optional[str] = None
    feedback: Optional[str] = None
    rating_out_of_10: Optional[int] = None
    scheduled_event: Optional[Dict[str, Any]] = None
    meet_link: Optional[str] = None
    interviewer_response: Optional[str] = None
    candidate_response: Optional[str] = None


class InterviewCandidateCreate(BaseModel):
    """Schema for creating a new interview candidate"""
    job_id: str = Field(..., description="ID of the job")
    candidate_id: str = Field(..., description="ID of the candidate")
    no_of_interviews: int = Field(default=2, description="Number of interviews to schedule")
    feedback: List[Dict[str, Any]] = Field(default_factory=list, description="Feedback from interviewers for each round")
    completedRounds: int = Field(default=0, description="Number of completed interview rounds")
    status: str = Field(
        default="scheduled", 
        description="Current status of the candidate in the interview process"
    )

    @validator('status')
    def validate_status(cls, v):
        valid_statuses = ["scheduled", "in_progress", "rejected", "passed", "selected", "completed"]
        if v not in valid_statuses:
            raise ValueError(f"status must be one of: {', '.join(valid_statuses)}")
        return v


class InterviewCandidateResponse(InterviewCandidateCreate):
    """Schema for interview candidate response"""
    id: str = Field(..., description="ID of the interview candidate record")
    feedback: List[InterviewFeedbackResponse] = []


class ShortlistRequest(BaseModel):
    """Schema for shortlisting candidates"""
    job_id: str = Field(..., description="ID of the job")
    number_of_candidates: int = Field(default=3, description="Number of candidates to shortlist", ge=1)
    no_of_interviews: int = Field(default=2, description="Number of interview rounds to schedule", ge=1, le=4)
    specific_interviewers: Optional[List[str]] = Field(
        default=None, 
        description="Optional list of specific interviewer IDs to assign for each round. If provided, must have at least as many IDs as no_of_interviews"
    )

    @validator('specific_interviewers')
    def validate_interviewers(cls, v, values):
        if v is not None:
            no_of_interviews = values.get('no_of_interviews', 2)
            if len(v) < no_of_interviews:
                raise ValueError(f'If specific_interviewers is provided, it must contain at least {no_of_interviews} interviewer IDs (one per interview round)')
        return v


class InterviewStatusUpdate(BaseModel):
    """Schema for updating interview status"""
    completedRounds: Optional[int] = Field(None, description="Number of completed interview rounds")
    status: Optional[str] = Field(None, description="Current status of the candidate in the interview process")

    @validator('status')
    def validate_status(cls, v):
        if v is not None:
            valid_statuses = ["scheduled", "in_progress", "rejected", "passed", "selected", "completed"]
            if v not in valid_statuses:
                raise ValueError(f"status must be one of: {', '.join(valid_statuses)}")
        return v
