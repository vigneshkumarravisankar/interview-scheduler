"""
Candidate data schemas
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class PreviousCompany(BaseModel):
    """Model for previous company experience"""
    name: str = Field("", description="Name of the company")
    job_responsibilities: str = Field("", description="Job responsibilities at the company")
    years: str = Field("", description="Years of experience at the company")

class CandidateCreate(BaseModel):
    """Model for creating a candidate record"""
    name: str = Field(..., description="Name of the candidate")
    email: str = Field(..., description="Email of the candidate")
    phone_no: str = Field("", description="Phone number of the candidate")
    job_id: str = Field(..., description="Job ID the candidate is applying for")
    job_role_name: str = Field(..., description="Job role name")
    job_description: str = Field(..., description="Job description")
    years_of_experience_needed: str = Field(..., description="Years of experience needed for the job")
    total_experience_in_years: str = Field("", description="Total experience of the candidate in years")
    technical_skills: str = Field("", description="Technical skills of the candidate")
    previous_companies: List[PreviousCompany] = Field(default_factory=list, description="Previous companies the candidate worked at")
    resume_url: str = Field(..., description="URL to the candidate's resume")
    ai_fit_score: str = Field("0", description="AI-calculated fit score (0-100)")
    interview_time: Optional[str] = Field(None, description="Scheduled interview time")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Record creation timestamp")
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Record update timestamp")

class CandidateResponse(CandidateCreate):
    """Model for candidate response"""
    id: str = Field(..., description="ID of the candidate record")

    class Config:
        from_attributes = True

class CandidateUpdate(BaseModel):
    """Model for updating candidate record"""
    name: Optional[str] = Field(None, description="Name of the candidate")
    email: Optional[str] = Field(None, description="Email of the candidate")
    phone_no: Optional[str] = Field(None, description="Phone number of the candidate")
    total_experience_in_years: Optional[str] = Field(None, description="Total experience of the candidate in years")
    technical_skills: Optional[str] = Field(None, description="Technical skills of the candidate")
    previous_companies: Optional[List[PreviousCompany]] = Field(None, description="Previous companies the candidate worked at")
    ai_fit_score: Optional[str] = Field(None, description="AI-calculated fit score (0-100)")
    interview_time: Optional[str] = Field(None, description="Scheduled interview time")
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Record update timestamp")

    class Config:
        from_attributes = True
