from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, EmailStr


class PreviousCompany(BaseModel):
    """Schema for previous company information"""
    name: str = Field(..., description="Name of the previous company")
    years: str = Field(..., description="Years of experience at this company")
    job_responsibilities: str = Field(..., description="Key job responsibilities at this company")


class CandidateCreate(BaseModel):
    """Schema for creating a new candidate entry"""
    name: str = Field(..., description="Full name of the candidate")
    job_id: str = Field(..., description="ID of the job the candidate is applying for")
    email: EmailStr = Field(..., description="Email address of the candidate")
    phone_no: str = Field(..., description="Contact phone number of the candidate")
    resume_url: str = Field(..., description="URL to the candidate's resume in Google Cloud Storage")
    total_experience_in_years: str = Field(..., description="Total professional experience in years")
    technical_skills: str = Field(..., description="Technical skills listed by the candidate")
    previous_companies: List[PreviousCompany] = Field([], description="List of previous companies worked at")
    ai_fit_score: str = Field(..., description="AI-generated score of candidate fit for the job")


class CandidateResponse(CandidateCreate):
    """Schema for candidate response, including ID"""
    id: str = Field(..., description="Unique identifier for the candidate")


class CandidateUpdate(BaseModel):
    """Schema for updating a candidate entry"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_no: Optional[str] = None
    resume_url: Optional[str] = None
    total_experience_in_years: Optional[str] = None
    technical_skills: Optional[str] = None
    previous_companies: Optional[List[PreviousCompany]] = None
    ai_fit_score: Optional[str] = None
