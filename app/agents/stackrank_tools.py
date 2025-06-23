"""
CrewAI tools for stackrank operations
"""
import os
import logging
from typing import Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from app.utils.email_service import send_offer_letter_email
from app.database.firebase_db import db as firebase_db
from .stackrank_core import stackrank_candidates_by_job_role

logger = logging.getLogger(__name__)


class StackrankCandidatesTool(BaseTool):
    name: str = "StackrankCandidates"
    description: str = "Stackrank candidates based on interview scores and select top performers for offers"
    
    # Define schema for the tool
    class InputSchema(BaseModel):
        job_role_name: str = Field(description="Job role name to stackrank candidates for")
        top_percentage: float = Field(description="Percentage of top candidates to select (e.g., 1 for top 1%)", default=1.0)
        compensation_offered: str = Field(description="Compensation to offer (optional)", default="")
        joining_date: str = Field(description="Joining date for selected candidates (YYYY-MM-DD format)", default="")
    
    # Set the argument schema
    args_schema = InputSchema
    
    def _run(
        self, 
        job_role_name: str, 
        top_percentage: float = 1.0,
        compensation_offered: str = "",
        joining_date: str = ""
    ) -> str:
        """
        Stackrank candidates for a specific job role and select top performers
        
        Args:
            job_role_name: Job role name
            top_percentage: Percentage of top candidates to select
            compensation_offered: Compensation to offer
            joining_date: Joining date
        
        Returns:
            String with stackranking results
        """
        try:
            logger.info(f"Starting stackranking process for {job_role_name}")
            
            # Call the core stackranking function
            result = stackrank_candidates_by_job_role(
                job_role_name=job_role_name,
                top_percentage=top_percentage,
                compensation_offered=compensation_offered,
                joining_date=joining_date
            )
            
            if not result['success']:
                return f"❌ {result.get('error', 'Unknown error occurred')}"
            
            # Prepare success response
            response = f"""✅ Stackranking completed for {job_role_name}!

📊 Stackranking Summary:
- Total Eligible Candidates: {result['eligible_candidates']}
- Top {top_percentage}% Selected: {result['selected_candidates']} candidates
- Selection Criteria: Highest cumulative interview scores

🏆 Selected Candidates:"""

            for i, candidate in enumerate(result['candidates'], 1):
                response += f"""
{i}. {candidate['candidate_name']}
   📧 Email: {candidate.get('candidate_email', 'N/A')}
   🎯 Total Score: {candidate['total_score']}/40 (avg: {candidate.get('average_score', 0):.1f})
   📊 Rounds: {candidate.get('feedback_rounds', 0)} interview rounds"""

            response += f"\n\n💾 All selected candidates have been added to the final_candidates collection with status 'selected'."
            
            if joining_date:
                response += f"\n📅 Joining Date: {joining_date}"
            if compensation_offered:
                response += f"\n💰 Compensation: {compensation_offered}"
            
            return response
            
        except Exception as e:
            logger.error(f"Error in stackranking process: {e}")
            return f"❌ Error in stackranking process: {str(e)}"


class SendOfferLettersTool(BaseTool):
    name: str = "SendOfferLetters"
    description: str = "Send offer letters to selected candidates in final_candidates collection"
    
    # Define schema for the tool
    class InputSchema(BaseModel):
        job_role_name: str = Field(description="Job role name to send offers for")
        joining_date: str = Field(description="Joining date for the role (YYYY-MM-DD format)")
        compensation_offered: str = Field(description="Compensation amount to offer", default="")
    
    # Set the argument schema
    args_schema = InputSchema
    
    def _run(
        self, 
        job_role_name: str, 
        joining_date: str,
        compensation_offered: str = ""
    ) -> str:
        """
        Send offer letters to selected candidates
        
        Args:
            job_role_name: Job role name
            joining_date: Joining date
            compensation_offered: Compensation amount
        
        Returns:
            String with offer sending results
        """
        try:
            logger.info(f"Sending offer letters for {job_role_name}")
            
            # Get selected candidates from final_candidates collection
            selected_candidates = self._get_selected_candidates(job_role_name)
            
            if not selected_candidates:
                return f"❌ No selected candidates found for {job_role_name} role in final_candidates collection."
            
            successful_offers = []
            failed_offers = []
            
            for candidate in selected_candidates:
                try:
                    # Send offer letter email
                    email_success = self._send_offer_email(
                        candidate, 
                        job_role_name, 
                        joining_date, 
                        compensation_offered
                    )
                    
                    if email_success:
                        # Update candidate status to 'offered'
                        self._update_candidate_status(candidate['final_candidate_id'], 'offered')
                        successful_offers.append(candidate)
                    else:
                        failed_offers.append(candidate)
                        
                except Exception as e:
                    logger.error(f"Error sending offer to {candidate.get('candidate_name')}: {e}")
                    failed_offers.append(candidate)
            
            # Prepare response
            response = f"""📧 Offer Letter Distribution Complete!

🎯 Job Role: {job_role_name}
📅 Joining Date: {joining_date}
💰 Compensation: {compensation_offered if compensation_offered else 'As per company policy'}

✅ Successfully Sent ({len(successful_offers)} offers):"""

            for candidate in successful_offers:
                response += f"""
📧 {candidate['candidate_name']} ({candidate['email']})
   Score: {candidate['total_score']}/40"""

            if failed_offers:
                response += f"\n\n❌ Failed to Send ({len(failed_offers)} offers):"
                for candidate in failed_offers:
                    response += f"\n📧 {candidate['candidate_name']} ({candidate['email']})"

            response += f"\n\n💾 Candidate statuses updated from 'selected' to 'offered' in final_candidates collection."
            
            return response
            
        except Exception as e:
            logger.error(f"Error sending offer letters: {e}")
            return f"❌ Error sending offer letters: {str(e)}"
    
    def _get_selected_candidates(self, job_role_name: str) -> list:
        """Get selected candidates from final_candidates collection"""
        try:
            candidates = firebase_db.collection('final_candidates').where('job_role', '==', job_role_name).where('status', '==', 'selected').stream()
            
            selected_candidates = []
            for doc in candidates:
                candidate_data = doc.to_dict()
                candidate_data['final_candidate_id'] = doc.id
                selected_candidates.append(candidate_data)
            
            return selected_candidates
            
        except Exception as e:
            logger.error(f"Error getting selected candidates: {e}")
            return []
    
    def _send_offer_email(
        self, 
        candidate: Dict[str, Any], 
        job_role_name: str, 
        joining_date: str, 
        compensation_offered: str
    ) -> bool:
        """Send offer letter email to candidate"""
        try:
            # Use the email service to send offer letter
            return send_offer_letter_email(
                candidate_name=candidate['candidate_name'],
                candidate_email=candidate['email'],
                job_role=job_role_name,
                joining_date=joining_date,
                compensation=compensation_offered
            )
        except Exception as e:
            logger.error(f"Error sending offer email: {e}")
            return False
    
    def _update_candidate_status(self, candidate_id: str, status: str) -> bool:
        """Update candidate status in final_candidates collection"""
        try:
            firebase_db.collection('final_candidates').document(candidate_id).update({
                'status': status,
                'offer_sent_at': datetime.now().isoformat()
            })
            return True
        except Exception as e:
            logger.error(f"Error updating candidate status: {e}")
            return False


class GetStackrankResultsTool(BaseTool):
    name: str = "GetStackrankResults"
    description: str = "Get stackranking results and final candidate status for a job role"
    
    # Define schema for the tool
    class InputSchema(BaseModel):
        job_role_name: str = Field(description="Job role name to get results for")
    
    # Set the argument schema
    args_schema = InputSchema
    
    def _run(self, job_role_name: str) -> str:
        """
        Get stackranking results for a job role
        
        Args:
            job_role_name: Job role name
        
        Returns:
            String with stackranking results
        """
        try:
            # Get final candidates for the job role
            final_candidates = firebase_db.collection('final_candidates').where('job_role', '==', job_role_name).stream()
            
            candidates_list = []
            for doc in final_candidates:
                candidate_data = doc.to_dict()
                candidate_data['id'] = doc.id
                candidates_list.append(candidate_data)
            
            if not candidates_list:
                return f"❌ No stackranking results found for {job_role_name} role."
            
            # Sort by total score
            candidates_list.sort(key=lambda x: x.get('total_score', 0), reverse=True)
            
            response = f"📊 Stackranking Results for {job_role_name}:\n\n"
            
            selected_count = len([c for c in candidates_list if c.get('status') == 'selected'])
            offered_count = len([c for c in candidates_list if c.get('status') == 'offered'])
            
            response += f"📈 Summary:\n"
            response += f"- Total Final Candidates: {len(candidates_list)}\n"
            response += f"- Selected: {selected_count}\n"
            response += f"- Offers Sent: {offered_count}\n\n"
            
            response += f"🏆 Ranked Candidates:\n"
            
            for i, candidate in enumerate(candidates_list, 1):
                status_icon = "✅" if candidate.get('status') == 'offered' else "🔄"
                response += f"{i}. {status_icon} {candidate.get('candidate_name')}\n"
                response += f"   📧 {candidate.get('email')}\n"
                response += f"   🎯 Score: {candidate.get('total_score', 0)}/40\n"
                response += f"   📊 Status: {candidate.get('status', 'unknown')}\n"
                if candidate.get('compensation_offered'):
                    response += f"   💰 Offer: {candidate.get('compensation_offered')}\n"
                if candidate.get('joining_date'):
                    response += f"   📅 Joining: {candidate.get('joining_date')}\n"
                response += "\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting stackrank results: {e}")
            return f"❌ Error getting stackrank results: {str(e)}"
