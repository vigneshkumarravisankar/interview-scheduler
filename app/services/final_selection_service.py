"""
Final candidate selection and offer letter service
"""
import uuid
from typing import Dict, Any, List, Optional, Tuple
from fastapi import BackgroundTasks

from app.database.chroma_db import ChromaVectorDB
from app.services.interview_core_service import InterviewCoreService
from app.services.candidate_service import CandidateService
from app.services.job_service import JobService
from app.utils.email_service import EmailService
from app.schemas.final_candidate_schema import FinalCandidateCreate, FinalCandidateResponse


class FinalSelectionService:
    """Service for final candidate selection and offer letter generation"""
    
    COLLECTION_NAME = "final_candidates"
    
    @staticmethod
    def create_final_candidate(candidate_data: Dict[str, Any]) -> str:
        """
        Create a final candidate record in Firestore
        
        Args:
            candidate_data: Dictionary with final candidate information
        
        Returns:
            ID of the created document
        """
        try:
            # Generate a unique ID if not provided
            if 'id' not in candidate_data:
                candidate_data['id'] = str(uuid.uuid4())
            
            # Add the document to the collection
            doc_id = ChromaVectorDB.create_document(
                FinalSelectionService.COLLECTION_NAME,
                candidate_data
            )
            
            print(f"Final candidate record created with ID: {doc_id}")
            return doc_id
        except Exception as e:
            print(f"Error creating final candidate record: {e}")
            raise
    
    @staticmethod
    def get_final_candidate(candidate_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a final candidate by ID
        
        Args:
            candidate_id: ID of the final candidate
        
        Returns:
            Final candidate data or None if not found
        """
        return ChromaVectorDB.get_document(FinalSelectionService.COLLECTION_NAME, candidate_id)
    
    @staticmethod
    def get_all_final_candidates() -> List[Dict[str, Any]]:
        """
        Get all final candidates
        
        Returns:
            List of all final candidates
        """
        return ChromaVectorDB.get_all_documents(FinalSelectionService.COLLECTION_NAME)
    
    @staticmethod
    def get_final_candidates_by_job_id(job_id: str) -> List[Dict[str, Any]]:
        """
        Get final candidates for a specific job
        
        Args:
            job_id: ID of the job
        
        Returns:
            List of final candidates for the job
        """
        all_candidates = FinalSelectionService.get_all_final_candidates()
        return [c for c in all_candidates if c.get('job_id') == job_id]
    
    @staticmethod
    def calculate_candidate_score(feedback_list: List[Dict[str, Any]]) -> int:
        """
        Calculate total score for a candidate based on feedback
        
        Args:
            feedback_list: List of feedback dictionaries
        
        Returns:
            Total score
        """
        total_score = 0
        for feedback in feedback_list:
            rating = feedback.get('rating_out_of_10')
            if rating is not None:  # Only count ratings that are not None
                total_score += rating
        return total_score
    
    @staticmethod
    def stackrank_candidates(job_id: str) -> List[Dict[str, Any]]:
        """
        Stack rank candidates for a job based on interview feedback scores
        
        Args:
            job_id: ID of the job
        
        Returns:
            Sorted list of candidates with their scores
        """
        try:
            # Get all interview candidates for the job
            interview_candidates = InterviewCoreService.get_interview_candidates_by_job_id(job_id)
            
            if not interview_candidates:
                print(f"No interview candidates found for job {job_id}")
                return []
            
            # Calculate scores and filter out candidates with incomplete feedback
            ranked_candidates = []
            for candidate in interview_candidates:
                feedback_list = candidate.get('feedback', [])
                
                # Check if all rounds have ratings and selection decisions
                # Note: isSelectedForNextRound is a field in each feedback item in the feedback array
                all_rounds_completed = all(
                    feedback.get('rating_out_of_10') is not None and 
                    feedback.get('isSelectedForNextRound') is not None and
                    feedback.get('isSelectedForNextRound') != ""
                    for feedback in feedback_list
                )
                
                # Only consider candidates who have completed all interview rounds with ratings and decisions
                if all_rounds_completed:
                    total_score = FinalSelectionService.calculate_candidate_score(feedback_list)
                    ranked_candidates.append({
                        'candidate_id': candidate.get('candidate_id'),
                        'interview_candidate_id': candidate.get('id'),
                        'total_score': total_score,
                        'feedback': feedback_list
                    })
            
            # Sort by total score (descending)
            ranked_candidates.sort(key=lambda x: x.get('total_score', 0), reverse=True)
            
            # After stackranking, update the top candidate in the final_candidates collection
            if ranked_candidates:
                FinalSelectionService.update_top_candidate_in_firebase(job_id, ranked_candidates[0])
            
            return ranked_candidates
        except Exception as e:
            print(f"Error stack ranking candidates: {e}")
            return []
    
    @staticmethod
    def select_top_candidate(job_id: str) -> Optional[Dict[str, Any]]:
        """
        Select the top candidate for a job
        
        Args:
            job_id: ID of the job
        
        Returns:
            Top candidate data or None if no candidates available
        """
        print(f"Selecting top candidate for job {job_id}")
        ranked_candidates = FinalSelectionService.stackrank_candidates(job_id)
        
        if not ranked_candidates:
            print(f"No ranked candidates found for job {job_id}")
            return None
        
        # Select the top candidate
        top_candidate = ranked_candidates[0]
        print(f"Top candidate selected with interview_candidate_id: {top_candidate.get('interview_candidate_id')} and candidate_id: {top_candidate.get('candidate_id')}")
        
        # Get candidate details - first try with candidate_id
        candidate_id = top_candidate.get('candidate_id')
        print(f"Looking for candidate details with candidate_id: {candidate_id}")
        candidate = CandidateService.get_candidate(candidate_id)
        
        if not candidate and top_candidate.get('interview_candidate_id'):
            # If not found with candidate_id, try with interview_candidate_id
            print(f"Candidate not found with candidate_id, trying interview_candidate_id: {top_candidate.get('interview_candidate_id')}")
            interview_candidate = CandidateService.get_candidate(top_candidate.get('interview_candidate_id'))
            if interview_candidate:
                candidate = interview_candidate
                # Update the candidate_id reference
                top_candidate['candidate_id'] = top_candidate.get('interview_candidate_id')
                print(f"Found candidate using interview_candidate_id instead")
        
        if not candidate:
            print(f"ERROR: Could not find candidate {top_candidate.get('candidate_id')} or {top_candidate.get('interview_candidate_id')}")
            
            # Try to get any candidates for this job as a fallback
            candidates = CandidateService.get_candidates_by_job_id(job_id)
            if candidates:
                print(f"Using first available candidate for job {job_id} as fallback")
                candidate = candidates[0]
                top_candidate['candidate_id'] = candidate.get('id')
            else:
                print(f"No candidates found for job {job_id}. Cannot proceed.")
                return None
        
        print(f"Successfully found candidate: {candidate.get('name')}")
        return {
            'interview_data': top_candidate,
            'candidate_data': candidate
        }
    
    @staticmethod
    def update_top_candidate_in_firebase(job_id: str, top_candidate_data: Dict[str, Any]) -> Optional[str]:
        """
        Update the top candidate in the final_candidates collection based on stackranking
        
        Args:
            job_id: ID of the job
            top_candidate_data: Data for the top ranked candidate
            
        Returns:
            ID of the created final candidate document, or None if unsuccessful
        """
        try:
            # Get job data
            job_data = JobService.get_job_posting(job_id)
            if not job_data:
                print(f"Job with ID {job_id} not found")
                return None
            
            # Get candidate details
            candidate_id = top_candidate_data.get('candidate_id')
            candidate_data = CandidateService.get_candidate(candidate_id)
            
            if not candidate_data:
                print(f"Could not find candidate with ID {candidate_id}")
                return None
            
            # Check if the candidate already exists in final_candidates
            existing_offers = FinalSelectionService.get_final_candidates_by_job_id(job_id)
            for offer in existing_offers:
                if offer.get('candidate_id') == candidate_id:
                    print(f"Candidate {candidate_id} already exists in final_candidates for job {job_id}")
                    return offer.get('id')
            
            # Create final candidate record - leave compensation_offered blank as it will be added when sending the offer
            final_candidate_data = {
                'candidate_name': candidate_data.get('name'),
                'job_id': job_id,
                'candidate_id': candidate_id,
                'job_role': job_data.job_role_name,
                'compensation_offered': '',  # Will be updated when offer is sent
                'email': candidate_data.get('email'),
                'total_score': top_candidate_data.get('total_score'),
                'status': 'selected'  # Not yet offered
            }
            
            # Create record in Firestore
            doc_id = FinalSelectionService.create_final_candidate(final_candidate_data)
            print(f"Added top candidate {candidate_data.get('name')} to final_candidates with ID {doc_id}")
            
            return doc_id
        except Exception as e:
            print(f"Error updating top candidate in Firebase: {e}")
            return None
    
    @staticmethod
    def get_hr_interviewer_info(feedback_list: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Get the name and email of the HR interviewer from the last round of feedback
        
        Args:
            feedback_list: List of feedback items
            
        Returns:
            Dictionary with HR interviewer name and email
        """
        try:
            result = {
                "name": "HR Representative",
                "email": "hr@company.com"
            }
            
            # Check if we have any feedback
            if not feedback_list:
                return result
                
            # Get the last round feedback (assuming rounds are in order)
            last_round_feedback = feedback_list[-1]
            
            # Check if it has interviewer info
            if last_round_feedback:
                if "interviewer_name" in last_round_feedback:
                    result["name"] = last_round_feedback["interviewer_name"]
                if "interviewer_email" in last_round_feedback:
                    result["email"] = last_round_feedback["interviewer_email"]
                    
            # If we don't have complete info in last round, check all rounds
            if result["name"] == "HR Representative" or result["email"] == "hr@company.com":
                for feedback in reversed(feedback_list):
                    if feedback:
                        if "interviewer_name" in feedback and result["name"] == "HR Representative":
                            result["name"] = feedback["interviewer_name"]
                        if "interviewer_email" in feedback and result["email"] == "hr@company.com":
                            result["email"] = feedback["interviewer_email"]
            
            return result
        except Exception as e:
            print(f"Error getting HR interviewer info: {e}")
            return {"name": "HR Representative", "email": "hr@company.com"}
            
    @staticmethod
    def get_hr_interviewer_name(feedback_list: List[Dict[str, Any]]) -> str:
        """
        Get the name of the HR interviewer from the last round of feedback
        
        Args:
            feedback_list: List of feedback items
            
        Returns:
            Name of the HR interviewer or a default name
        """
        return FinalSelectionService.get_hr_interviewer_info(feedback_list)["name"]
    
    @staticmethod
    async def select_and_send_offer(
        job_id: str,
        compensation_offered: str,
        background_tasks: BackgroundTasks
    ) -> Tuple[bool, Optional[FinalCandidateResponse]]:
        """
        Select top candidate and send offer letter
        
        Args:
            job_id: ID of the job
            compensation_offered: Compensation to offer the candidate
            background_tasks: FastAPI background tasks for sending email
            
        Returns:
            Tuple of (success, final_candidate)
        """
        try:
            # Get job data
            job_data = JobService.get_job_posting(job_id)
            if not job_data:
                print(f"Job with ID {job_id} not found")
                return False, None
            
            # Select top candidate
            top_candidate_info = FinalSelectionService.select_top_candidate(job_id)
            if not top_candidate_info:
                print(f"No eligible candidates found for job {job_id}")
                return False, None
            
            interview_data = top_candidate_info.get('interview_data')
            candidate_data = top_candidate_info.get('candidate_data')
            
            # Get HR interviewer info from feedback
            hr_info = FinalSelectionService.get_hr_interviewer_info(interview_data.get('feedback', []))
            print(f"Using HR interviewer: {hr_info['name']} <{hr_info['email']}>")
            
            # Check for existing offer and update it with compensation
            existing_offers = FinalSelectionService.get_final_candidates_by_job_id(job_id)
            for offer in existing_offers:
                if offer.get('candidate_id') == candidate_data.get('id'):
                    print(f"Found existing offer for candidate {candidate_data.get('name')}, updating with compensation")
                    
                    # Update existing record with compensation and HR info
                    ChromaVectorDB.update_document(
                        FinalSelectionService.COLLECTION_NAME,
                        offer.get('id'),
                        {
                            'compensation_offered': compensation_offered,
                            'status': 'offered',
                            'hr_name': hr_info['name'],
                            'hr_email': hr_info['email']
                        }
                    )
                    
                    # Get the updated record
                    updated_offer = FinalSelectionService.get_final_candidate(offer.get('id'))
                    final_candidate = FinalCandidateResponse(**updated_offer)
                    
                    # Send offer letter
                    await EmailService.send_offer_letter(
                        candidate=final_candidate,
                        job_title=job_data.job_role_name,
                        background_tasks=background_tasks,
                        hr_name=hr_info['name'],
                        hr_email=hr_info['email']
                    )
                    
                    return True, final_candidate
            
            # If no existing record, create a new one
            print(f"No existing offer found for candidate {candidate_data.get('name')}, creating new offer")
            final_candidate_data = {
                'candidate_name': candidate_data.get('name'),
                'job_id': job_id,
                'candidate_id': candidate_data.get('id'),
                'job_role': job_data.job_role_name,
                'compensation_offered': compensation_offered,
                'email': candidate_data.get('email'),
                'status': 'offered',
                'hr_name': hr_info['name'],
                'hr_email': hr_info['email']
            }
            
            # Create record in Firestore
            doc_id = FinalSelectionService.create_final_candidate(final_candidate_data)
            
            # Add the ID to the data
            final_candidate_data['id'] = doc_id
            
            # Create response object
            final_candidate = FinalCandidateResponse(**final_candidate_data)
            
            # Send offer letter
            await EmailService.send_offer_letter(
                candidate=final_candidate,
                job_title=job_data.job_role_name,
                background_tasks=background_tasks,
                hr_name=hr_info['name'],
                hr_email=hr_info['email']
            )
            
            return True, final_candidate
        except Exception as e:
            print(f"Error selecting and sending offer: {e}")
            return False, None
