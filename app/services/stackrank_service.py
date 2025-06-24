"""
Stackranking Service - Direct access to stackranking functionality
"""
import logging
from typing import Dict, Any, List, Optional
from app.agents.stackrank_core import stackrank_candidates_by_job_role

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StackrankService:
    """Service for handling stackranking operations"""
    
    @staticmethod
    def stackrank_by_job_role(
        job_role_name: str,
        top_percentage: float = 1.0,
        compensation_offered: str = "",
        joining_date: str = ""
    ) -> Dict[str, Any]:
        """
        Stackrank candidates for a specific job role
        
        Args:
            job_role_name: Job role name (case insensitive)
            top_percentage: Percentage of top candidates to select (default: 1.0)
            compensation_offered: Compensation to offer (optional)
            joining_date: Joining date for selected candidates (YYYY-MM-DD format)
        
        Returns:
            Dictionary containing the stackranking results
        """
        try:
            logger.info(f"Stackranking service called for job role: {job_role_name}")
            
            # Call the core stackranking function
            result = stackrank_candidates_by_job_role(
                job_role_name=job_role_name,
                top_percentage=top_percentage,
                compensation_offered=compensation_offered,
                joining_date=joining_date
            )
            
            logger.info(f"Stackranking completed for {job_role_name}. Success: {result.get('success')}")
            return result
            
        except Exception as e:
            logger.error(f"Error in stackranking service: {e}")
            return {
                "success": False,
                "error": f"Service error: {str(e)}",
                "eligible_candidates": 0,
                "selected_candidates": 0,
                "candidates": []
            }
    
    @staticmethod
    def validate_job_role_exists(job_role_name: str) -> Dict[str, Any]:
        """
        Validate if a job role exists in the jobs collection
        
        Args:
            job_role_name: Job role name to validate
            
        Returns:
            Dictionary with validation results
        """
        try:
            from app.services.job_service import JobService
            
            job_posting = JobService.get_job_posting_by_role_name(job_role_name)
            
            if job_posting:
                return {
                    "exists": True,
                    "job_id": job_posting.job_id,
                    "job_role_name": job_posting.job_role_name,
                    "message": f"Job role '{job_role_name}' found with ID: {job_posting.job_id}"
                }
            else:
                return {
                    "exists": False,
                    "job_id": None,
                    "job_role_name": job_role_name,
                    "message": f"Job role '{job_role_name}' not found in jobs collection"
                }
                
        except Exception as e:
            logger.error(f"Error validating job role: {e}")
            return {
                "exists": False,
                "job_id": None,
                "job_role_name": job_role_name,
                "message": f"Error validating job role: {str(e)}"
            }
    
    @staticmethod
    def get_candidates_count_for_job_role(job_role_name: str) -> Dict[str, Any]:
        """
        Get count of candidates for a specific job role
        
        Args:
            job_role_name: Job role name
            
        Returns:
            Dictionary with candidate counts
        """
        try:
            from app.services.job_service import JobService
            from app.database.firebase_db import db as firebase_db
            from app.agents.stackrank_core import _is_candidate_eligible_for_stackrank
            
            # First, find the job
            job_posting = JobService.get_job_posting_by_role_name(job_role_name)
            
            if not job_posting:
                return {
                    "success": False,
                    "error": f"Job role '{job_role_name}' not found",
                    "total_candidates": 0,
                    "eligible_candidates": 0
                }
            
            job_id = job_posting.job_id
            
            # Get all candidates for this job_id
            candidates = firebase_db.collection('interview_candidates').where('job_id', '==', job_id).stream()
            
            total_candidates = 0
            eligible_candidates = 0
            
            for doc in candidates:
                total_candidates += 1
                candidate_data = doc.to_dict()
                feedback_array = candidate_data.get('feedback', [])
                
                if _is_candidate_eligible_for_stackrank(feedback_array):
                    eligible_candidates += 1
            
            return {
                "success": True,
                "job_role": job_role_name,
                "job_id": job_id,
                "total_candidates": total_candidates,
                "eligible_candidates": eligible_candidates,
                "ineligible_candidates": total_candidates - eligible_candidates
            }
            
        except Exception as e:
            logger.error(f"Error getting candidate count: {e}")
            return {
                "success": False,
                "error": f"Error getting candidate count: {str(e)}",
                "total_candidates": 0,
                "eligible_candidates": 0
            }
