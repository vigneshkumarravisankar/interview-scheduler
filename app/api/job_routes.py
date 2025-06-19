from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from app.schemas.job_schema import JobPostingCreate, JobPostingResponse, JobPostingUpdate
from app.services.job_service import JobService

# Create router
router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
    responses={404: {"description": "Not found"}},
)


@router.post("/", response_model=JobPostingResponse, status_code=status.HTTP_201_CREATED)
async def create_job_posting(job_posting: JobPostingCreate):
    """
    Create a new job posting
    """
    try:
        return JobService.create_job_posting(job_posting)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create job posting: {str(e)}",
        )


@router.get("/{job_id}", response_model=JobPostingResponse)
async def get_job_posting(job_id: str):
    """
    Get a job posting by ID
    """
    job_posting = JobService.get_job_posting(job_id)
    if not job_posting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job posting with ID {job_id} not found",
        )
    return job_posting


@router.get("/", response_model=List[JobPostingResponse])
async def get_all_job_postings():
    """
    Get all job postings
    """
    return JobService.get_all_job_postings()


@router.put("/{job_id}", response_model=JobPostingResponse)
async def update_job_posting(job_id: str, job_data: JobPostingUpdate):
    """
    Update a job posting
    """
    updated_job = JobService.update_job_posting(job_id, job_data.dict(exclude_unset=True))
    if not updated_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job posting with ID {job_id} not found",
        )
    return updated_job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_posting(job_id: str):
    """
    Delete a job posting
    """
    if not JobService.delete_job_posting(job_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job posting with ID {job_id} not found",
        )
    return None
