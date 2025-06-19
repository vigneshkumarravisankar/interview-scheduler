"""
Schema for final selected candidates
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional


class FinalCandidateCreate(BaseModel):
    """Schema for creating a final selected candidate record"""
    candidate_name: str = Field(..., description="Name of the candidate")
    job_id: str = Field(..., description="ID of the job")
    candidate_id: str = Field(..., description="ID of the candidate")
    job_role: str = Field(..., description="Job role")
    compensation_offered: str = Field(..., description="Compensation offered")
    email: Optional[str] = Field(None, description="Email address of the candidate")
    total_score: Optional[int] = Field(None, description="Total interview score of the candidate")
    status: str = Field("selected", description="Status of the candidate (selected or offered)")


class FinalCandidateResponse(FinalCandidateCreate):
    """Schema for final candidate response"""
    id: str = Field(..., description="ID of the final candidate record")
