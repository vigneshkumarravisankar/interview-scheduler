"""
Service for tracking and updating interview status and completed rounds
"""
import random
import string
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from app.database.firebase_db import FirestoreDB
from app.services.interview_core_service import InterviewCoreService


class InterviewTrackingService:
    """Service for tracking interview progress and status updates"""
    
    @staticmethod
    def generate_gmeet_link() -> str:
        """
        Generate a placeholder Google Meet link
        
        In a real implementation, this would integrate with the Google Calendar API
        to create a real meeting and return the link.
        
        Returns:
            A placeholder Google Meet link
        """
        # Generate a random meeting ID (10 chars)
        meeting_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        return f"https://meet.google.com/{meeting_id}-{random.randint(100, 999)}-{random.randint(100, 999)}"
    
    @staticmethod
    def format_scheduled_time(scheduled_datetime: Optional[datetime] = None) -> str:
        """
        Format a datetime object to a nice time string, or generate a placeholder time
        
        Args:
            scheduled_datetime: Optional datetime object
            
        Returns:
            A formatted time string like "2PM"
        """
        if not scheduled_datetime:
            # Generate a random time 1-3 days from now
            days_ahead = random.randint(1, 3)
            hours = random.randint(9, 16)  # 9 AM to 4 PM
            scheduled_datetime = datetime.now() + timedelta(days=days_ahead)
            scheduled_datetime = scheduled_datetime.replace(hour=hours, minute=0, second=0, microsecond=0)
            
        # Format the time as "2PM" or "10AM"
        hour = scheduled_datetime.hour
        if hour == 12:
            return "12PM"
        elif hour > 12:
            return f"{hour-12}PM"
        elif hour == 0:
            return "12AM"
        else:
            return f"{hour}AM"

    @staticmethod
    def update_interview_tracking_status(candidate_id: str) -> bool:
        """
        Update the completedRounds and status fields based on feedback data
        
        Args:
            candidate_id: ID of the interview candidate
            
        Returns:
            True if the update was successful, False otherwise
        """
        try:
            # Get the candidate record
            candidate = InterviewCoreService.get_interview_candidate(candidate_id)
            if not candidate:
                print(f"Cannot update tracking status: Candidate {candidate_id} not found")
                return False
                
            feedback_list = candidate.get('feedback', [])
            
            # Initialize default values
            completed_rounds = 0
            status = 'scheduled'  # Default status
            
            # Check if all feedback rounds have gmeet_link
            update_data = {}
            
            # Count completed rounds based on non-empty feedback
            for idx, round_feedback in enumerate(feedback_list):
                # Ensure each round has a meet link
                if not round_feedback.get('meet_link'):
                    feedback_list[idx]['meet_link'] = InterviewTrackingService.generate_gmeet_link()
                    update_data['feedback'] = feedback_list
                
                # Ensure each round has a scheduled time
                if not round_feedback.get('scheduled_time'):
                    feedback_list[idx]['scheduled_time'] = InterviewTrackingService.format_scheduled_time()
                    update_data['feedback'] = feedback_list
                
                # Count completed rounds
                if round_feedback and (
                    round_feedback.get('feedback') or 
                    round_feedback.get('isSelectedForNextRound') is not None or
                    round_feedback.get('rating_out_of_10') is not None
                ):
                    completed_rounds = idx + 1
                    
                    # Update status based on isSelectedForNextRound value
                    selected = round_feedback.get('isSelectedForNextRound')
                    if selected is True or selected == "yes":
                        status = 'passed' if idx < len(feedback_list) - 1 else 'selected'
                    elif selected is False or selected == "no":
                        status = 'rejected'
                    else:
                        status = 'in_progress'
            
            # Special case: if completed_rounds is 1, set status to "completed"
            if completed_rounds == 1:
                status = 'completed'
                
            # Special case: if any round has a gmeet_link and completed_rounds is 1, set status to "scheduled"
            has_meet_link = any(round_feedback.get('meet_link') for round_feedback in feedback_list)
            if has_meet_link and completed_rounds == 1:
                status = 'scheduled'
            
            # Add status and completedRounds to update data
            update_data['completedRounds'] = completed_rounds
            update_data['status'] = status
            
            # Update the candidate record
            InterviewCoreService.update_interview_candidate(candidate_id, update_data)
            
            print(f"Updated candidate {candidate_id} tracking status to: completedRounds={completed_rounds}, status={status}")
            return True
            
        except Exception as e:
            print(f"Error updating interview tracking status: {e}")
            return False
    
    @staticmethod
    def initialize_feedback_array(candidate_id: str, num_rounds: int = 2) -> bool:
        """
        Initialize the feedback array for a candidate
        
        This will ensure that all feedback objects in the array have the necessary fields
        including meet_link and scheduled_time.
        
        Args:
            candidate_id: ID of the interview candidate
            num_rounds: Number of rounds to initialize (default: 2)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get the candidate record
            candidate = InterviewCoreService.get_interview_candidate(candidate_id)
            if not candidate:
                print(f"Cannot initialize feedback: Candidate {candidate_id} not found")
                return False
            
            feedback_list = candidate.get('feedback', [])
            
            # If feedback list is empty, create it with empty objects
            if not feedback_list:
                feedback_list = []
                for i in range(num_rounds):
                    # Calculate dates for the scheduled event
                    days_ahead = 1 + i * 2  # Schedule rounds 2 days apart
                    interview_date = datetime.now() + timedelta(days=days_ahead)
                    start_time = interview_date.replace(hour=16, minute=0, second=0, microsecond=0)
                    end_time = interview_date.replace(hour=17, minute=0, second=0, microsecond=0)
                    
                    # Format dates in ISO format with timezone
                    start_iso = start_time.strftime("%Y-%m-%dT%H:%M:%S+05:30")
                    end_iso = end_time.strftime("%Y-%m-%dT%H:%M:%S+05:30")
                    
                    # Generate unique ID for the event
                    event_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=22))
                    
                    # Generate meet link
                    meet_link = InterviewTrackingService.generate_gmeet_link()
                    
                    feedback_list.append({
                        'interviewer_id': '',
                        'interviewer_name': f"Interviewer {i+1}",
                        'interviewer_email': "interviewer@example.com",
                        'department': 'Engineering',
                        'feedback': None,
                        'isSelectedForNextRound': None,
                        'rating_out_of_10': None,
                        'meet_link': meet_link,
                        'scheduled_time': InterviewTrackingService.format_scheduled_time(start_time),
                        'scheduled_event': {
                            'end': {
                                'dateTime': end_iso,
                                'timeZone': "Asia/Kolkata"
                            },
                            'start': {
                                'dateTime': start_iso,
                                'timeZone': "Asia/Kolkata"
                            },
                            'htmlLink': f"https://www.google.com/calendar/event?eid={event_id}",
                            'id': event_id
                        }
                    })
                
                # Update the candidate with the new feedback list
                InterviewCoreService.update_interview_candidate(
                    candidate_id,
                    {'feedback': feedback_list}
                )
                print(f"Initialized feedback array for candidate {candidate_id} with {num_rounds} rounds")
            
            # Ensure each existing feedback item has meet_link and scheduled_time
            else:
                updated = False
                for i in range(len(feedback_list)):
                    if not feedback_list[i].get('meet_link'):
                        feedback_list[i]['meet_link'] = InterviewTrackingService.generate_gmeet_link()
                        updated = True
                    
                    if not feedback_list[i].get('scheduled_time'):
                        feedback_list[i]['scheduled_time'] = InterviewTrackingService.format_scheduled_time()
                        updated = True
                
                # Update the candidate if changes were made
                if updated:
                    InterviewCoreService.update_interview_candidate(
                        candidate_id,
                        {'feedback': feedback_list}
                    )
                    print(f"Updated feedback array for candidate {candidate_id} with missing fields")
            
            return True
        
        except Exception as e:
            print(f"Error initializing feedback array: {e}")
            return False
    
    @staticmethod
    def submit_interview_feedback(
        candidate_id: str, 
        round_index: int, 
        feedback: str, 
        rating: int, 
        selected_for_next: bool
    ) -> bool:
        """
        Submit feedback for an interview round and update tracking status
        
        Args:
            candidate_id: ID of the interview candidate
            round_index: Index of the interview round (0-based)
            feedback: Feedback text
            rating: Rating out of 10
            selected_for_next: Whether the candidate is selected for the next round
            
        Returns:
            True if feedback was submitted successfully, False otherwise
        """
        try:
            # Get the candidate record
            candidate = InterviewCoreService.get_interview_candidate(candidate_id)
            if not candidate:
                print(f"Cannot submit feedback: Candidate {candidate_id} not found")
                return False
                
            feedback_list = candidate.get('feedback', [])
            
            # Ensure the feedback list is long enough
            if len(feedback_list) <= round_index:
                print(f"Cannot submit feedback: Round index {round_index} out of range")
                return False
                
            # Ensure the round has a meet link
            if not feedback_list[round_index].get('meet_link'):
                feedback_list[round_index]['meet_link'] = InterviewTrackingService.generate_gmeet_link()
                
            # Ensure the round has a scheduled time
            if not feedback_list[round_index].get('scheduled_time'):
                feedback_list[round_index]['scheduled_time'] = InterviewTrackingService.format_scheduled_time()
                
            # Update feedback for the specified round
            feedback_list[round_index]['feedback'] = feedback
            feedback_list[round_index]['rating_out_of_10'] = rating
            feedback_list[round_index]['isSelectedForNextRound'] = selected_for_next
            
            # Update the feedback list
            InterviewCoreService.update_interview_candidate(
                candidate_id,
                {'feedback': feedback_list}
            )
            
            # Update tracking status
            InterviewTrackingService.update_interview_tracking_status(candidate_id)
            
            # Special case: if this is round 0 and the candidate is selected for next round
            # and feedback and rating are provided, schedule the next round automatically
            next_round_scheduled = False
            if (round_index == 0 and selected_for_next and 
                feedback and rating is not None and 
                round_index + 1 < len(feedback_list)):
                
                # Generate Google Meet link for next round if not exists
                if not feedback_list[round_index + 1].get('meet_link'):
                    feedback_list[round_index + 1]['meet_link'] = InterviewTrackingService.generate_gmeet_link()
                
                # Generate scheduled time for next round if not exists
                if not feedback_list[round_index + 1].get('scheduled_time'):
                    # Schedule 2 days later than current round
                    feedback_list[round_index + 1]['scheduled_time'] = InterviewTrackingService.format_scheduled_time()
                
                # Update the feedback list with next round's meet link and scheduled time
                InterviewCoreService.update_interview_candidate(
                    candidate_id,
                    {'feedback': feedback_list}
                )
                
                print(f"Generated Google Meet link for next round: {feedback_list[round_index + 1].get('meet_link')}")
                next_round_scheduled = True
            
            print(f"Submitted feedback for candidate {candidate_id}, round {round_index}")
            return True
            
        except Exception as e:
            print(f"Error submitting interview feedback: {e}")
            return False
    
    @staticmethod
    def bulk_update_tracking_status() -> Dict[str, Any]:
        """
        Update tracking status for all interview candidates
        
        Returns:
            Dictionary with counts of updated and failed records
        """
        try:
            candidates = InterviewCoreService.get_all_interview_candidates()
            
            success_count = 0
            failure_count = 0
            
            for candidate in candidates:
                if InterviewTrackingService.update_interview_tracking_status(candidate.get('id')):
                    success_count += 1
                else:
                    failure_count += 1
                    
            return {
                'total': len(candidates),
                'updated': success_count,
                'failed': failure_count
            }
            
        except Exception as e:
            print(f"Error in bulk update tracking status: {e}")
            return {
                'error': str(e),
                'updated': 0,
                'failed': 0
            }
