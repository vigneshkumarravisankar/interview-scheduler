"""
Core stackranking functions and utilities
"""
import math
import logging
from typing import Dict, Any, List
from datetime import datetime
from app.database.firebase_db import db as firebase_db

logger = logging.getLogger(__name__)


def _is_candidate_eligible_for_stackrank(feedback_array: List[Dict[str, Any]]) -> bool:
    """
    Check if candidate is eligible for stackranking based on feedback criteria
    
    Args:
        feedback_array: List of feedback dictionaries
        
    Returns:
        bool: True if candidate is eligible, False otherwise
    """
    if not feedback_array:
        return False
    
    for feedback in feedback_array:
        # Check if feedback exists, rating exists, and is selected for next round
        if (feedback.get('feedback') and 
            feedback.get('rating_out_of_10') is not None and 
            feedback.get('isSelectedForNextRound') == 'yes'):
            continue
        else:
            # If any round doesn't meet criteria, candidate is not eligible
            return False
    
    return True


def stackrank_candidates_by_job_role(
    job_role_name: str, 
    top_percentage: float = 1.0,
    compensation_offered: str = "",
    joining_date: str = ""
) -> Dict[str, Any]:
    """
    Direct function to stackrank candidates by job role name
    
    Args:
        job_role_name: Job role name (case insensitive)
        top_percentage: Percentage of top candidates to select (default: 1.0)
        compensation_offered: Compensation to offer (optional)
        joining_date: Joining date for selected candidates (YYYY-MM-DD format)
    
    Returns:
        Dictionary containing the stackranking results
    """
    try:
        logger.info(f"Starting direct stackranking process for {job_role_name}")
        
        # Step 1: Find job_id from jobs collection using job_role_name (case insensitive)
        logger.info(f"Searching for job with role name: {job_role_name}")
        
        # Query jobs collection to find matching job_id
        from app.services.job_service import JobService
        job_posting = JobService.get_job_posting_by_role_name(job_role_name)
        
        if not job_posting:
            logger.error(f"No job found with role name: {job_role_name}")
            return {
                "success": False,
                "error": f"No job found with role name: {job_role_name}",
                "eligible_candidates": 0,
                "selected_candidates": 0,
                "candidates": []
            }
        
        job_id = job_posting.job_id
        logger.info(f"Found job_id: {job_id} for role: {job_role_name}")
        
        # Step 2: Get candidates from interview_candidates collection using job_id
        candidates = firebase_db.collection('interview_candidates').where('job_id', '==', job_id).stream()
        
        eligible_candidates = []
        
        for doc in candidates:
            candidate_data = doc.to_dict()
            candidate_data['id'] = doc.id
            
            feedback_array = candidate_data.get('feedback', [])
            
            # Check eligibility criteria: feedback != null, isSelectedForNextRound == 'yes', rating_out_of_10 != null
            if _is_candidate_eligible_for_stackrank(feedback_array):
                # Add job_role_name to candidate data for reference
                candidate_data['job_role_name'] = job_role_name
                eligible_candidates.append(candidate_data)
        
        logger.info(f"Found {len(eligible_candidates)} eligible candidates for job_id: {job_id} (role: {job_role_name})")
        
        if not eligible_candidates:
            return {
                "success": False,
                "error": f"No eligible candidates found for stackranking in {job_role_name} role. Criteria: Candidates must have completed all interview rounds with feedback, ratings, and selection status.",
                "eligible_candidates": 0,
                "selected_candidates": 0,
                "candidates": []
            }
        
        # Step 3: Calculate total scores
        scored_candidates = []
        for candidate in eligible_candidates:
            feedback_array = candidate.get('feedback', [])
            total_score = 0
            
            for feedback in feedback_array:
                rating = feedback.get('rating_out_of_10', 0)
                if rating:
                    total_score += rating
            
            candidate['total_score'] = total_score
            scored_candidates.append(candidate)
        
        # Step 4: Sort by total score (highest first)
        scored_candidates.sort(key=lambda x: x['total_score'], reverse=True)
        
        # Step 5: Select top percentage
        num_to_select = max(1, math.ceil(len(scored_candidates) * (top_percentage / 100)))
        top_candidates = scored_candidates[:num_to_select]
        
        # Step 6: Move to final_candidates collection
        final_candidates = []
        
        for candidate in top_candidates:
            final_candidate = {
                "candidate_name": candidate.get('candidate_name', ''),
                "job_id": candidate.get('job_id', ''),
                "candidate_id": candidate.get('id', ''),
                "job_role": job_role_name,
                "compensation_offered": compensation_offered,
                "email": candidate.get('candidate_email', ''),
                "total_score": candidate.get('total_score', 0),
                "status": "selected",
                "created_at": datetime.now().isoformat(),
                "joining_date": joining_date if joining_date else "",
                "interview_feedback": candidate.get('feedback', [])  # Include original feedback for reference
            }
            
            # Add to Firebase
            try:
                doc_ref = firebase_db.collection('final_candidates').add(final_candidate)
                final_candidate['final_candidate_id'] = doc_ref[1].id
                final_candidates.append(final_candidate)
                logger.info(f"Added {candidate.get('candidate_name')} to final_candidates collection")
            except Exception as e:
                logger.error(f"Error adding candidate to final_candidates: {e}")
        
        # Prepare response
        return {
            "success": True,
            "job_role": job_role_name,
            "job_id": job_id,
            "eligible_candidates": len(scored_candidates),
            "selected_candidates": len(top_candidates),
            "top_percentage": top_percentage,
            "compensation_offered": compensation_offered,
            "joining_date": joining_date,
            "candidates": [
                {
                    "candidate_name": candidate.get('candidate_name', ''),
                    "candidate_email": candidate.get('candidate_email', ''),
                    "total_score": candidate.get('total_score', 0),
                    "feedback_rounds": len(candidate.get('feedback', [])),
                    "average_score": candidate.get('total_score', 0) / len(candidate.get('feedback', [])) if candidate.get('feedback') else 0
                }
                for candidate in top_candidates
            ]
        }
        
    except Exception as e:
        logger.error(f"Error in direct stackranking process: {e}")
        return {
            "success": False,
            "error": f"Error in stackranking process: {str(e)}",
            "eligible_candidates": 0,
            "selected_candidates": 0,
            "candidates": []
        }
