"""
Firebase Context Tool for Agents
This module provides tools for agents to query Firebase database context
"""
import logging
from typing import Dict, Any, List, Optional
from crewai.tools import BaseTool
from app.database.chroma_db import FirestoreDB, ChromaVectorDB
from app.services.interview_core_service import InterviewCoreService
from app.services.job_service import JobService
from app.services.candidate_service import CandidateService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GetInterviewCandidatesTool(BaseTool):
    name: str = "GetInterviewCandidates"
    description: str = "Get interview candidates from the database to obtain valid IDs"
    
    def _run(self, job_id: str = None, candidate_name: str = None, limit: int = 5) -> str:
        """
        Get interview candidates from the database, optionally filtered by job ID or candidate name
        
        Args:
            job_id: Optional job ID to filter by
            candidate_name: Optional candidate name to filter by (partial match)
            limit: Maximum number of results to return
            
        Returns:
            String with interview candidate information including IDs
        """
        try:
            results = []
            
            # If job_id is provided, use it to filter
            if job_id:
                candidates = InterviewCoreService.get_interview_candidates_by_job_id(job_id)
                if candidates:
                    results.extend(candidates)
            
            # If no job_id or no results with job_id, get all candidates
            if not results:
                # Get all interview candidates from the database
                all_candidates = FirestoreDB.get_all_documents("interview_candidates")
                results = all_candidates
            
            # If candidate_name is provided, filter by name (case insensitive partial match)
            if candidate_name and results:
                candidate_name = candidate_name.lower()
                results = [c for c in results if c.get('candidate_name', '').lower().find(candidate_name) >= 0]
            
            # Limit results
            results = results[:limit]
            
            if not results:
                return "No interview candidates found matching your criteria."
            
            # Format the results
            response = f"Found {len(results)} interview candidate(s):\n\n"
            
            for i, candidate in enumerate(results):
                # Extract key information
                candidate_id = candidate.get('id') or candidate.get('candidate_id', 'Unknown')
                name = candidate.get('candidate_name', 'Unknown')
                email = candidate.get('candidate_email', 'Unknown')
                job_id = candidate.get('job_id', 'Unknown')
                job_role = candidate.get('job_role', 'Unknown')
                status = candidate.get('status', 'Unknown')
                
                # Get feedback rounds
                feedback = candidate.get('feedback', [])
                num_rounds = len(feedback)
                
                response += f"Interview Record {i+1}:\n"
                response += f"ID: {candidate_id}\n"
                response += f"Candidate: {name} ({email})\n"
                response += f"Job: {job_role} (ID: {job_id})\n"
                response += f"Status: {status}\n"
                response += f"Interview Rounds: {num_rounds}\n"
                
                # Add feedback round details
                if feedback:
                    response += "Round Details:\n"
                    for j, round_feedback in enumerate(feedback):
                        round_num = j + 1
                        interviewer = round_feedback.get('interviewer_name', 'Unknown')
                        round_type = round_feedback.get('round_type', f"Round {round_num}")
                        scheduled_time = round_feedback.get('scheduled_time', 'Not scheduled')
                        
                        response += f"  Round {round_num} ({round_type}) with {interviewer}: {scheduled_time}\n"
                
                response += "\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting interview candidates: {e}")
            return f"Error retrieving interview candidates: {str(e)}"

class GetJobsTool(BaseTool):
    name: str = "GetJobs"
    description: str = "Get job postings from the database to obtain valid job IDs"
    
    def _run(self, job_role_name: str = None, limit: int = 5) -> str:
        """
        Get job postings from the database, optionally filtered by job role name
        
        Args:
            job_role_name: Optional job role name to filter by (partial match)
            limit: Maximum number of results to return
            
        Returns:
            String with job posting information including IDs
        """
        try:
            # Get all jobs from the database
            all_jobs = JobService.get_all_job_postings()
            
            # If job_role_name is provided, filter by name (case insensitive partial match)
            if job_role_name:
                job_role_name = job_role_name.lower()
                results = [j for j in all_jobs if hasattr(j, 'job_role_name') and 
                           j.job_role_name.lower().find(job_role_name) >= 0]
            else:
                results = all_jobs
            
            # Limit results
            results = results[:limit]
            
            if not results:
                return "No job postings found matching your criteria."
            
            # Format the results
            response = f"Found {len(results)} job posting(s):\n\n"
            
            for i, job in enumerate(results):
                # Extract key information
                job_id = job.job_id if hasattr(job, 'job_id') else job.id if hasattr(job, 'id') else 'Unknown'
                role_name = job.job_role_name if hasattr(job, 'job_role_name') else 'Unknown'
                status = job.status if hasattr(job, 'status') else 'Unknown'
                location = job.location if hasattr(job, 'location') else 'Unknown'
                
                response += f"Job {i+1}:\n"
                response += f"ID: {job_id}\n"
                response += f"Role: {role_name}\n"
                response += f"Status: {status}\n"
                response += f"Location: {location}\n\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting job postings: {e}")
            return f"Error retrieving job postings: {str(e)}"

class GetCandidatesTool(BaseTool):
    name: str = "GetCandidates"
    description: str = "Get candidate profiles from the database to obtain valid candidate IDs"
    
    def _run(self, job_id: str = None, candidate_name: str = None, limit: int = 5) -> str:
        """
        Get candidate profiles from the database, optionally filtered by job ID or candidate name
        
        Args:
            job_id: Optional job ID to filter by
            candidate_name: Optional candidate name to filter by (partial match)
            limit: Maximum number of results to return
            
        Returns:
            String with candidate information including IDs
        """
        try:
            results = []
            
            # If job_id is provided, use it to filter
            if job_id:
                candidates = CandidateService.get_candidates_by_job_id(job_id)
                if candidates:
                    results.extend(candidates)
            
            # If no job_id or no results with job_id, get all candidates
            if not results:
                # Get all candidates from the database
                all_candidates = FirestoreDB.get_all_documents("candidates_data")
                results = all_candidates
            
            # If candidate_name is provided, filter by name (case insensitive partial match)
            if candidate_name and results:
                candidate_name = candidate_name.lower()
                results = [c for c in results if c.get('name', '').lower().find(candidate_name) >= 0]
            
            # Limit results
            results = results[:limit]
            
            if not results:
                return "No candidates found matching your criteria."
            
            # Format the results
            response = f"Found {len(results)} candidate(s):\n\n"
            
            for i, candidate in enumerate(results):
                # Extract key information
                candidate_id = candidate.get('id') or 'Unknown'
                name = candidate.get('name', 'Unknown')
                email = candidate.get('email', 'Unknown')
                job_id = candidate.get('job_id', 'Unknown')
                fit_score = candidate.get('ai_fit_score', 'Unknown')
                
                response += f"Candidate {i+1}:\n"
                response += f"ID: {candidate_id}\n"
                response += f"Name: {name}\n"
                response += f"Email: {email}\n"
                response += f"Job ID: {job_id}\n"
                response += f"AI Fit Score: {fit_score}\n\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting candidates: {e}")
            return f"Error retrieving candidates: {str(e)}"
