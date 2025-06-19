import uuid
from typing import Dict, Any, List, Optional
from app.database.firebase_db import FirestoreDB

# Use FirestoreDB directly
DB = FirestoreDB
from app.schemas.job_schema import JobPostingCreate, JobPostingResponse


class JobService:
    """Service for handling job posting operations"""
    
    COLLECTION_NAME = "jobs"
    
    @staticmethod
    def create_job_posting(job_posting: JobPostingCreate) -> JobPostingResponse:
        """
        Create a new job posting
        
        Args:
            job_posting: JobPostingCreate schema
        
        Returns:
            JobPostingResponse: The created job posting
        """
        try:
            # Generate a unique ID
            job_id = str(uuid.uuid4())
            
            # Create a new document
            job_data = job_posting.dict()
            job_data["job_id"] = job_id
            
            # Add the document to the collection using FirestoreDB
            doc_id = FirestoreDB.create_document(JobService.COLLECTION_NAME, job_data)
            
            # Update job_id with the document ID
            job_data["job_id"] = doc_id
            
            return JobPostingResponse(**job_data)
        except Exception as e:
            print(f"Error creating job posting: {e}")
            raise
    
    @staticmethod
    def get_job_posting(job_id: str) -> Optional[JobPostingResponse]:
        """
        Get a job posting by ID
        
        Args:
            job_id: ID of the job posting
            
        Returns:
            JobPostingResponse or None if not found
        """
        try:
            # Handle empty job_id to prevent Firebase errors
            if not job_id or job_id.strip() == "":
                print("Warning: Empty job_id provided")
                return None

            # Get the document from Firestore
            doc = FirestoreDB.get_document(JobService.COLLECTION_NAME, job_id)
            
            # If document exists and has all required fields, create JobPostingResponse
            if doc:
                # Check for required fields
                required_fields = ["job_role_name", "job_description", "years_of_experience_needed"]
                missing_fields = [field for field in required_fields if field not in doc]
                
                if missing_fields:
                    print(f"Warning: Missing required fields in job document: {missing_fields}")
                    # Add default values for missing fields
                    for field in missing_fields:
                        if field == "job_role_name":
                            doc["job_role_name"] = f"Job {job_id}"
                        elif field == "job_description":
                            doc["job_description"] = "No description provided"
                        elif field == "years_of_experience_needed":
                            doc["years_of_experience_needed"] = "Not specified"
                
                # Ensure job_id is included
                if "job_id" not in doc:
                    doc["job_id"] = job_id
                    
                return JobPostingResponse(**doc)
            return None
        except Exception as e:
            print(f"Error getting job posting: {e}")
            # Return None instead of raising exception to prevent API errors
            return None
    
    @staticmethod
    def get_all_job_postings() -> List[JobPostingResponse]:
        """
        Get all job postings
        
        Returns:
            List[JobPostingResponse]: List of all job postings
        """
        # Get all documents from the collection
        docs = FirestoreDB.get_all_documents(JobService.COLLECTION_NAME)
        
        return [JobPostingResponse(**doc) for doc in docs]
    
    @staticmethod
    def update_job_posting(job_id: str, job_data: Dict[str, Any]) -> Optional[JobPostingResponse]:
        """
        Update a job posting
        
        Args:
            job_id: ID of the job posting
            job_data: Data to update
            
        Returns:
            JobPostingResponse: Updated job posting or None if not found
        """
        # Remove None values
        job_data = {k: v for k, v in job_data.items() if v is not None}
        
        # Update the document
        FirestoreDB.update_document(JobService.COLLECTION_NAME, job_id, job_data)
        
        # Get the updated document
        updated_doc = FirestoreDB.get_document(JobService.COLLECTION_NAME, job_id)
        
        if updated_doc:
            return JobPostingResponse(**updated_doc)
        return None
    
    @staticmethod
    def delete_job_posting(job_id: str) -> bool:
        """
        Delete a job posting
        
        Args:
            job_id: ID of the job posting
            
        Returns:
            bool: True if deleted, False if not found
        """
        # Check if the document exists
        doc = FirestoreDB.get_document(JobService.COLLECTION_NAME, job_id)
        
        if doc:
            # Delete the document
            FirestoreDB.delete_document(JobService.COLLECTION_NAME, job_id)
            return True
        return False
