from typing import Optional
from pydantic import BaseModel, Field
import uuid


class JobPostingBase(BaseModel):
    """Base model for job posting"""
    job_role_name: str = Field(..., description="Name of the job role")
    job_description: str = Field(..., description="Description of the job")
    years_of_experience_needed: str = Field(..., description="Years of experience needed for the job")
    status: str = Field("active", description="Status of the job (active/closed)")
    location: str = Field("in office", description="Location of the job (remote/in office/city name)")


class JobPostingCreate(JobPostingBase):
    """Model for creating a job posting"""
    
    def generate_job_id(self):
        """Generate a unique job ID"""
        return str(uuid.uuid4())


class JobPostingResponse(JobPostingBase):
    """Model for job posting response"""
    id: str = Field(..., description="Document ID in Firebase")
    job_id: str = Field(..., description="ID of the job posting (same as id)")

    class Config:
        from_attributes = True


class JobPostingUpdate(BaseModel):
    """Model for updating a job posting"""
    job_role_name: Optional[str] = Field(None, description="Name of the job role")
    job_description: Optional[str] = Field(None, description="Description of the job")
    years_of_experience_needed: Optional[str] = Field(None, description="Years of experience needed for the job")
    status: Optional[str] = Field(None, description="Status of the job (open/closed)")
    location: Optional[str] = Field(None, description="Location of the job (remote/city name)")

    class Config:
        from_attributes = True
