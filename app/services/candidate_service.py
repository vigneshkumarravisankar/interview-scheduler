"""
Service for handling candidate operations
"""
import os
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import json

# Import necessary modules
from app.database.firebase_db import FirestoreDB
from app.schemas.candidate_schema import CandidateCreate, CandidateResponse, CandidateUpdate, PreviousCompany
from app.utils.gcloud_storage import list_resumes_for_job, download_resume, delete_temp_file, get_resume_url
from app.utils.resume_parser import extract_text_from_pdf, extract_candidate_data_with_llm, calculate_fit_score
from app.services.job_service import JobService

# Function that candidate_routes.py is trying to import
def extract_resume_data(job_id: str, job_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Process all resumes for a specific job ID
    
    Args:
        job_id: ID of the job to process resumes for
        job_data: Data about the job
        
    Returns:
        List of processed candidate records
    """
    # Use the existing CandidateService method that we've already implemented
    return CandidateService.process_resumes_for_job(job_id)

class CandidateService:
    """Service for handling candidate operations"""
    
    COLLECTION_NAME = "candidates_data"
    
    @staticmethod
    def create_candidate(candidate_data: CandidateCreate) -> CandidateResponse:
        """
        Create a new candidate record
        
        Args:
            candidate_data: CandidateCreate schema
        
        Returns:
            CandidateResponse: The created candidate record
        """
        try:
            # Generate a unique ID
            candidate_id = str(uuid.uuid4())
            
            # Create a new document
            data = candidate_data.dict()
            
            # Set timestamps
            current_time = datetime.now().isoformat()
            data["created_at"] = current_time
            data["updated_at"] = current_time
            
            # Add the document to the collection using FirestoreDB
            FirestoreDB.create_document_with_id(CandidateService.COLLECTION_NAME, candidate_id, data)
            
            # Add ID field
            data["id"] = candidate_id
            
            return CandidateResponse(**data)
        except Exception as e:
            print(f"Error creating candidate record: {e}")
            raise
    
    @staticmethod
    def get_candidate(candidate_id: str) -> Optional[CandidateResponse]:
        """
        Get a candidate record by ID
        
        Args:
            candidate_id: ID of the candidate record
            
        Returns:
            CandidateResponse or None if not found
        """
        try:
            doc = FirestoreDB.get_document(CandidateService.COLLECTION_NAME, candidate_id)
            
            if doc:
                return CandidateResponse(**doc)
            return None
        except Exception as e:
            print(f"Error getting candidate record: {e}")
            return None
    
    @staticmethod
    def get_candidates_for_job(job_id: str) -> List[CandidateResponse]:
        """
        Get all candidates for a specific job ID
        
        Args:
            job_id: ID of the job
            
        Returns:
            List of candidate records for the job
        """
        try:
            # Query by job_id field
            conditions = [("job_id", "==", job_id)]
            docs = FirestoreDB.execute_complex_query(CandidateService.COLLECTION_NAME, conditions)
            
            return [CandidateResponse(**doc) for doc in docs]
        except Exception as e:
            print(f"Error getting candidates for job {job_id}: {e}")
            return []
    
    @staticmethod
    def get_candidates_by_job_id(job_id: str) -> List[CandidateResponse]:
        """
        Get all candidates for a specific job ID (alias for get_candidates_for_job)
        
        Args:
            job_id: ID of the job
            
        Returns:
            List of candidate records for the job
        """
        # This is an alias for get_candidates_for_job to maintain API compatibility
        return CandidateService.get_candidates_for_job(job_id)
    
    @staticmethod
    def get_all_candidates() -> List[CandidateResponse]:
        """
        Get all candidates
        
        Returns:
            List of all candidate records
        """
        try:
            # Get all documents from the collection
            docs = FirestoreDB.get_all_documents(CandidateService.COLLECTION_NAME)
            
            return [CandidateResponse(**doc) for doc in docs]
        except Exception as e:
            print(f"Error getting all candidates: {e}")
            return []
    
    @staticmethod
    def update_candidate(candidate_id: str, candidate_data: Dict[str, Any]) -> Optional[CandidateResponse]:
        """
        Update a candidate record
        
        Args:
            candidate_id: ID of the candidate record
            candidate_data: Data to update
            
        Returns:
            Updated CandidateResponse or None if not found
        """
        try:
            # Remove None values
            data = {k: v for k, v in candidate_data.items() if v is not None}
            
            # Set update timestamp
            data["updated_at"] = datetime.now().isoformat()
            
            # Update the document
            FirestoreDB.update_document(CandidateService.COLLECTION_NAME, candidate_id, data)
            
            # Get the updated document
            updated_doc = FirestoreDB.get_document(CandidateService.COLLECTION_NAME, candidate_id)
            
            if updated_doc:
                return CandidateResponse(**updated_doc)
            return None
        except Exception as e:
            print(f"Error updating candidate record: {e}")
            return None
    
    @staticmethod
    def delete_candidate(candidate_id: str) -> bool:
        """
        Delete a candidate record
        
        Args:
            candidate_id: ID of the candidate record
            
        Returns:
            True if deleted, False if not found
        """
        try:
            doc = FirestoreDB.get_document(CandidateService.COLLECTION_NAME, candidate_id)
            
            if doc:
                FirestoreDB.delete_document(CandidateService.COLLECTION_NAME, candidate_id)
                return True
            return False
        except Exception as e:
            print(f"Error deleting candidate record: {e}")
            return False
    
    @staticmethod
    def process_resumes_for_job(job_id: str) -> List[CandidateResponse]:
        """
        Process all resumes for a specific job ID
        
        Args:
            job_id: ID of the job to process resumes for
            
        Returns:
            List of processed candidate records
        """
        try:
            # First, get the job details
            job_data = JobService.get_job_posting(job_id)
            
            if not job_data:
                print(f"Job not found: {job_id}")
                return []
            
            # Get all resumes for the job
            resumes = list_resumes_for_job(job_id)
            
            if not resumes:
                print(f"No resumes found for job: {job_id}")
                return []
            
            print(f"Processing {len(resumes)} resumes for job {job_id}")
            
            processed_candidates = []
            
            for resume in resumes:
                resume_name = resume.get('name', '')
                resume_url = resume.get('url', '')
                
                # Skip if already processed
                existing_candidates = FirestoreDB.execute_complex_query(
                    CandidateService.COLLECTION_NAME, 
                    [("job_id", "==", job_id), ("resume_url", "==", resume_url)]
                )
                
                if existing_candidates:
                    print(f"Resume already processed: {resume_name}")
                    processed_candidates.append(CandidateResponse(**existing_candidates[0]))
                    continue
                
                # Download and process the resume
                temp_file_path = download_resume(resume_name)
                
                if not temp_file_path:
                    print(f"Failed to download resume: {resume_name}")
                    continue
                
                try:
                    # Extract text from PDF
                    resume_text = extract_text_from_pdf(temp_file_path)
                    
                    # Extract candidate data using LLM, which now returns our exact JSON format
                    candidate_data = extract_candidate_data_with_llm(
                        resume_text, 
                        job_data.dict()
                    )
                    
                    # Calculate fit score
                    fit_score = calculate_fit_score(candidate_data, job_data.dict())
                    
                    # Update the candidate data with information that the LLM doesn't provide
                    candidate_data["resume_url"] = resume_url
                    candidate_data["ai_fit_score"] = str(fit_score)
                    
                    # Set timestamps
                    current_time = datetime.now().isoformat()
                    candidate_data["created_at"] = current_time
                    candidate_data["updated_at"] = current_time
                    
                    # Ensure we have required fields
                    if not candidate_data.get("name"):
                        candidate_data["name"] = "Unknown Candidate"
                    
                    if not candidate_data.get("email"):
                        candidate_data["email"] = f"candidate_{uuid.uuid4().hex[:8]}@example.com"
                    
                    # Convert previous_companies to proper Pydantic objects
                    previous_companies = []
                    for company in candidate_data.get('previous_companies', []):
                        if isinstance(company, dict) and company.get('name'):
                            previous_companies.append(PreviousCompany(
                                name=company.get('name', ''),
                                job_responsibilities=company.get('job_responsibilities', ''),
                                years=company.get('years', '')
                            ))
                    
                    # Create the candidate record using our schema
                    candidate_record = CandidateCreate(
                        name=candidate_data.get('name', 'Unknown'),
                        email=candidate_data.get('email'),
                        phone_no=candidate_data.get('phone_no', ''),
                        job_id=job_id,
                        job_role_name=job_data.job_role_name,
                        job_description=job_data.job_description,
                        years_of_experience_needed=job_data.years_of_experience_needed,
                        total_experience_in_years=candidate_data.get('total_experience_in_years', ''),
                        technical_skills=candidate_data.get('technical_skills', ''),
                        previous_companies=previous_companies,
                        resume_url=resume_url,
                        ai_fit_score=str(fit_score)
                    )
                    
                    # Save to database
                    result = CandidateService.create_candidate(candidate_record)
                    processed_candidates.append(result)
                    
                    print(f"Successfully processed resume: {resume_name}, Fit score: {fit_score}")
                    
                finally:
                    # Clean up temporary file
                    delete_temp_file(temp_file_path)
            
            return processed_candidates
            
        except Exception as e:
            print(f"Error processing resumes for job {job_id}: {e}")
            return []
