from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, File, UploadFile, Form, Body
from pydantic import BaseModel
from app.services.candidate_service import CandidateService
import os
import uuid
from datetime import datetime

# Create router
router = APIRouter(
    prefix="/resume",
    tags=["resume"],
    responses={404: {"description": "Not found"}},
)


class ResumeProcessRequest(BaseModel):
    job_id: str
    candidate_ids: Optional[List[str]] = None
    process_all: bool = False


class ProcessedResumeResult(BaseModel):
    job_id: str
    processed_count: int
    candidates: List[Dict[str, Any]]
    timestamp: str


@router.post("/process", response_model=ProcessedResumeResult)
async def process_resumes(request: ResumeProcessRequest):
    """
    Process resumes for a specific job.
    This must be done before shortlisting candidates for interviews.
    
    The system will:
    1. Analyze the job description to identify key requirements
    2. Process candidate resumes to extract skills, experience, and qualifications
    3. Calculate an AI fit score based on the match between job requirements and candidate qualifications
    4. Store processed candidate data for the shortlisting phase
    """
    try:
        # Process the resumes for the job
        candidates = CandidateService.process_resumes_for_job(request.job_id)
        
        if not candidates:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No candidates found for job {request.job_id} or processing failed",
            )
        
        # Format the response
        candidate_list = [candidate.dict() for candidate in candidates]
        
        return {
            "job_id": request.job_id,
            "processed_count": len(candidate_list),
            "candidates": candidate_list,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing resumes: {str(e)}",
        )


@router.post("/upload/{job_id}")
async def upload_resume(
    job_id: str,
    file: UploadFile = File(...),
    candidate_name: Optional[str] = Form(None),
    candidate_email: Optional[str] = Form(None),
):
    """
    Upload a resume for a specific job and process it.
    
    The file can be in PDF, DOCX, or TXT format.
    """
    try:
        # Check file type
        allowed_extensions = ['.pdf', '.docx', '.doc', '.txt']
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type {file_ext} not supported. Please upload a PDF, DOCX, or TXT file.",
            )
        
        # Generate a unique filename
        unique_filename = f"{str(uuid.uuid4())}{file_ext}"
        
        # Save the file to a temporary location
        file_path = f"tmp/{unique_filename}"
        os.makedirs("tmp", exist_ok=True)
        
        # Write the file
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
        
        # Process the resume
        candidate_id = CandidateService.upload_resume(
            job_id=job_id,
            file_path=file_path,
            candidate_name=candidate_name,
            candidate_email=candidate_email
        )
        
        # Clean up the file
        os.remove(file_path)
        
        return {
            "job_id": job_id,
            "candidate_id": candidate_id,
            "file_name": file.filename,
            "status": "Resume uploaded and processed successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading resume: {str(e)}",
        )


@router.get("/candidates/{job_id}", response_model=List[Dict[str, Any]])
async def get_candidates_for_job(job_id: str):
    """
    Get all processed candidates for a specific job
    """
    try:
        candidates = CandidateService.get_candidates_for_job(job_id)
        
        if not candidates:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No candidates found for job {job_id}",
            )
        
        # Convert to dict for response
        candidate_list = [candidate.dict() for candidate in candidates]
        
        return candidate_list
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting candidates: {str(e)}",
        )
