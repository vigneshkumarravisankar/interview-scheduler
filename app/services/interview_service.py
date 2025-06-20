"""
Main service for handling interview scheduling and candidate shortlisting
This file acts as a facade for the specialized service modules
"""
from typing import Dict, Any, List, Optional, Tuple

from app.services.interview_core_service import InterviewCoreService
from app.services.interview_schedule_service import InterviewScheduleService
from app.services.interview_reschedule_service import InterviewRescheduleService
from app.services.interview_shortlist_service import InterviewShortlistService
from app.services.interview_tracking_service import InterviewTrackingService


class InterviewService:
    """
    Main service for handling interview scheduling and candidate shortlisting
    Delegates to specialized service modules
    """
    
    # Collection names - maintained here for backward compatibility
    COLLECTION_NAME = InterviewCoreService.COLLECTION_NAME
    INTERVIEWERS_COLLECTION = InterviewCoreService.INTERVIEWERS_COLLECTION
    html_link = ""
    
    
    @staticmethod
    def create_interview_candidate(candidate_data: Dict[str, Any]) -> str:
        """
        Create a new interview candidate document in Firestore
        
        Args:
            candidate_data: Dictionary with interview candidate information
        
        Returns:
            ID of the created document
        """
        return InterviewCoreService.create_interview_candidate(candidate_data)
    
    @staticmethod
    def get_interview_candidate(candidate_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an interview candidate by ID
        
        Args:
            candidate_id: ID of the interview candidate
        
        Returns:
            Interview candidate data or None if not found
        """
        return InterviewCoreService.get_interview_candidate(candidate_id)
    
    @staticmethod
    def get_all_interview_candidates() -> List[Dict[str, Any]]:
        """
        Get all interview candidates
        
        Returns:
            List of all interview candidates
        """
        return InterviewCoreService.get_all_interview_candidates()
    
    @staticmethod
    def get_interview_candidates_by_job_id(job_id: str) -> List[Dict[str, Any]]:
        """
        Get interview candidates for a specific job
        
        Args:
            job_id: ID of the job
        
        Returns:
            List of interview candidates for the job
        """
        return InterviewCoreService.get_interview_candidates_by_job_id(job_id)
    
    @staticmethod
    def update_interview_candidate(candidate_id: str, data: Dict[str, Any]) -> None:
        """
        Update an interview candidate
        
        Args:
            candidate_id: ID of the interview candidate
            data: New data to update
        """
        InterviewCoreService.update_interview_candidate(candidate_id, data)
    
    @staticmethod
    def delete_interview_candidate(candidate_id: str) -> None:
        """
        Delete an interview candidate
        
        Args:
            candidate_id: ID of the interview candidate
        """
        InterviewCoreService.delete_interview_candidate(candidate_id)
    
    @staticmethod
    def get_all_interviewers() -> List[Dict[str, Any]]:
        """
        Get all interviewers from the interviewers collection
        
        Returns:
            List of all interviewers
        """
        return InterviewCoreService.get_all_interviewers()
    
    @staticmethod
    def assign_interviewers(no_of_interviews: int, specific_interviewers: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Assign interviewers for each interview round
        
        Args:
            no_of_interviews: Number of interview rounds
            specific_interviewers: Optional list of interviewer IDs to use
        
        Returns:
            List of interviewer assignments, one per round
        """
        return InterviewCoreService.assign_interviewers(no_of_interviews, specific_interviewers)
    
    @staticmethod
    def shortlist_candidates(
        job_id: str, 
        number_of_candidates: int = 3, 
        no_of_interviews: int = 2,
        specific_interviewers: Optional[List[str]] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Shortlist candidates for a job based on their AI fit scores
        
        Args:
            job_id: ID of the job
            number_of_candidates: Number of candidates to shortlist
            no_of_interviews: Number of interview rounds to schedule
            specific_interviewers: Optional list of interviewer IDs to assign for each round
        
        Returns:
            Tuple of (shortlisted candidates, created interview candidate records)
        """
        return InterviewShortlistService.shortlist_candidates(
            job_id, 
            number_of_candidates, 
            no_of_interviews,
            specific_interviewers
        )
    
    @staticmethod
    def schedule_interviews(
        interview_candidates: List[Dict[str, Any]], 
        job_data: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Schedule interviews for the shortlisted candidates
        
        Args:
            interview_candidates: List of interview candidate records
            job_data: Job data
        
        Returns:
            Dictionary mapping candidate IDs to lists of scheduled interview events
        """
        return InterviewScheduleService.schedule_interviews(
            interview_candidates, 
            job_data
        )
            
    @staticmethod
    def reschedule_interview(
        candidate_id: str, 
        round_idx: int, 
        job_data: Dict[str, Any],
        tomorrow: bool = True
    ) -> bool:
        """
        Reschedule an interview for a candidate when they decline
        
        Args:
            candidate_id: ID of the interview candidate record
            round_idx: Index of the interview round to reschedule
            job_data: Job data dictionary
            tomorrow: If True, schedule for tomorrow; otherwise for the next available slot
        
        Returns:
            True if successfully rescheduled, False otherwise
        """
        return InterviewRescheduleService.reschedule_interview(
            candidate_id, 
            round_idx, 
            job_data, 
            tomorrow
        )
    
    @staticmethod
    def schedule_next_round(interview_candidate_id: str) -> bool:
        """
        Schedule the next round of interviews for a candidate after they pass a round
        
        Args:
            interview_candidate_id: ID of the interview candidate
        
        Returns:
            True if successfully scheduled, False otherwise
        """
        return InterviewScheduleService.schedule_next_round(interview_candidate_id)
    
    @staticmethod
    def initialize_feedback_array(interview_id: str, num_rounds: int = 2) -> bool:
        """
        Initialize the feedback array structure for an interview candidate
        
        Args:
            interview_id: ID of the interview candidate record
            num_rounds: Number of interview rounds to initialize
            
        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            # Get the interview candidate record
            interview_candidate = InterviewCoreService.get_interview_candidate(interview_id)
            if not interview_candidate:
                print(f"Interview candidate with ID {interview_id} not found")
                return False
            
            # Get candidate details from candidates_data collection
            from app.database.firebase_db import FirestoreDB
            candidate_id = interview_candidate.get("candidate_id", "")
            if not candidate_id:
                print(f"No candidate ID found in interview record {interview_id}")
                return False
            
            # Get candidate data (name and email)
            candidate = FirestoreDB.get_document("candidates_data", candidate_id)
            if not candidate:
                print(f"Candidate with ID {candidate_id} not found in candidates_data collection")
                
                # Use details from interview_candidate as fallback
                candidate_name = interview_candidate.get("candidate_name", "Unknown Candidate")
                candidate_email = interview_candidate.get("candidate_email", "unknown@example.com")
            else:
                candidate_name = candidate.get("name", "Unknown Candidate")
                candidate_email = candidate.get("email", "unknown@example.com")
            
            # Get job details
            job_id = interview_candidate.get("job_id", "")
            job = FirestoreDB.get_document("jobs", job_id) if job_id else {}
            job_role = job.get("job_role_name", interview_candidate.get("job_role", "Unknown Position"))
            
            # Determine round types
            round_types = []
            if num_rounds == 1:
                round_types = ["Technical"]
            elif num_rounds == 2:
                round_types = ["Manager", "HR"]
            else:
                # For 3 or more rounds, first n-2 are technical, then manager, then HR
                technical_rounds = ["Technical"] * (num_rounds - 2)
                round_types = technical_rounds + ["Manager", "HR"]
            
            # Get interviewers
            interviewers = InterviewCoreService.assign_interviewers(num_rounds)
            
            # Create feedback array
            import random
            import string
            from datetime import datetime, timedelta
            
            feedback_array = []
            
            for i in range(num_rounds):
                # Get round type and appropriate interviewer
                round_type = round_types[i] if i < len(round_types) else "Technical"
                
                # Get interviewer based on round type if possible
                if i < len(interviewers):
                    interviewer = interviewers[i]
                else:
                    # Default interviewer data
                    interviewer = {
                        "interviewer_id": "",
                        "interviewer_email": f"{round_type.lower()}_interviewer@example.com",
                        "interviewer_name": f"{round_type} Interviewer",
                        "department": "Engineering" if round_type == "Technical" else 
                                      "Management" if round_type == "Manager" else "Human Resources"
                    }
                
                # Schedule only first round initially
                # Additional rounds will be scheduled when previous rounds are passed
                if i == 0:
                    # First interview is 1 day ahead
                    interview_date = datetime.now() + timedelta(days=1)
                    # Set interview time (10 AM + i hours)
                    start_time = interview_date.replace(hour=10 + (i % 7), minute=0, second=0, microsecond=0)
                    end_time = start_time + timedelta(hours=1)
                    
                    # Format dates in ISO format with timezone
                    start_iso = start_time.strftime("%Y-%m-%dT%H:%M:%S+05:30")
                    end_iso = end_time.strftime("%Y-%m-%dT%H:%M:%S+05:30")
                    
                    # Generate event ID and Meet link
                    event_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=22))
                    meet_code = ''.join(random.choices(string.ascii_lowercase, k=3)) + '-' + \
                               ''.join(random.choices(string.ascii_lowercase, k=4)) + '-' + \
                               ''.join(random.choices(string.ascii_lowercase, k=3))
                    meet_link = f"https://meet.google.com/{meet_code}"
                    
                    # Create calendar event for the first round
                    try:
                        from app.utils.calendar_service import create_calendar_event
                        from app.utils.email_notification import send_interview_notification
                        
                        # Create event details
                        summary = f"Interview: {candidate_name} - {job_role} - Round {i+1} ({round_type})"
                        description = f"""
                        Interview for: {candidate_name} ({candidate_email})
                        Position: {job_role}
                        Round: {i+1} of {num_rounds} - {round_type}
                        
                        Notes for interviewer:
                        - Please review the candidate's resume before the interview
                        - Ask questions related to their experience and skills
                        - Submit feedback after the interview through the portal
                        """
                        
                        # Create calendar event
                        calendar_result = create_calendar_event(
                            summary=summary,
                            description=description,
                            start_time=start_iso,
                            end_time=end_iso,
                            location=meet_link,
                            attendees=[
                                {"email": interviewer.get("interviewer_email", "")},
                                {"email": candidate_email}
                            ]
                        )
                        
                        if calendar_result:
                            print(f"Created calendar event for interview: {calendar_result.get('id')}")
                            event_id = calendar_result.get('id', event_id)
                            meet_link = calendar_result.get('hangoutLink', meet_link)
                            html_link = calendar_result.get('htmlLink', f"https://calendar.google.com/calendar/event?eid={event_id}")
                            
                            # Send email notification
                            hour_12 = start_time.hour if start_time.hour <= 12 else start_time.hour - 12
                            am_pm = 'AM' if start_time.hour < 12 else 'PM'
                            formatted_time = f"{hour_12}{am_pm}"
                            
                            send_interview_notification(
                                candidate_name=candidate_name,
                                recipient_email=candidate_email,
                                interviewer_name=interviewer.get("interviewer_name", ""),
                                interviewer_email=interviewer.get("interviewer_email", ""),
                                job_title=job_role,
                                start_time=formatted_time,
                                interview_date=start_time.strftime("%A, %B %d, %Y"),
                                meet_link=meet_link,
                                round_number=i+1,
                                round_type=round_type
                            )
                        else:
                            print("Failed to create calendar event")
                            html_link = f"https://calendar.google.com/calendar/event?eid={event_id}"
                            
                    except Exception as e:
                        print(f"Error creating calendar event: {e}")
                        html_link = f"https://calendar.google.com/calendar/event?eid={event_id}"
                        
                    scheduled_event = {
                        "end": {
                            "dateTime": end_iso,
                            "timeZone": "Asia/Kolkata"
                        },
                        "start": {
                            "dateTime": start_iso,
                            "timeZone": "Asia/Kolkata"
                        },
                        "htmlLink": html_link,
                        "id": event_id
                    }
                    
                    # Format time for display
                    hour_12 = start_time.hour if start_time.hour <= 12 else start_time.hour - 12
                    am_pm = 'AM' if start_time.hour < 12 else 'PM'
                    formatted_time = f"08:00 pm"
                else:
                    # No scheduled event for future rounds yet
                    scheduled_event = {}
                    meet_link = ""
                    formatted_time = ""
                
                # Create the feedback object
                feedback_object = {
                    "feedback": "",
                    "interviewer_id": interviewer.get("interviewer_id", ""),
                    "interviewer_name": interviewer.get("interviewer_name", f"{round_type} Interviewer"),
                    "interviewer_email": interviewer.get("interviewer_email", "interviewer@example.com"),
                    "department": interviewer.get("department", "Engineering"),
                    "isSelectedForNextRound": "",
                    "rating_out_of_10": "",
                    "meet_link": meet_link,
                    "scheduled_time": formatted_time,
                    "round_type": round_type,
                    "round_number": i + 1,
                    "scheduled_event": scheduled_event
                }
                
                feedback_array.append(feedback_object)
            
            # Update the interview candidate with the feedback array and other fields
            InterviewCoreService.update_interview_candidate(interview_id, {
                "feedback": feedback_array,
                "completedRounds": 0,
                "nextRoundIndex": 0,  # First interview is next
                "no_of_interviews": num_rounds,
                "status": "scheduled",
                "current_round_scheduled": True,  # First round is scheduled
                "candidate_name": candidate_name,
                "candidate_email": candidate_email,
                "job_role": job_role
            })
            
            print(f"Successfully initialized feedback array for interview {interview_id}")
            return True
        
        except Exception as e:
            print(f"Error initializing feedback array: {e}")
            return False
    
    @staticmethod
    def update_tracking_status(candidate_id: str) -> bool:
        """
        Update the completedRounds and status fields for an interview candidate
        
        Args:
            candidate_id: ID of the interview candidate
        
        Returns:
            True if the update was successful, False otherwise
        """
        return InterviewTrackingService.update_interview_tracking_status(candidate_id)
    
    @staticmethod
    def submit_feedback(
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
        return InterviewTrackingService.submit_interview_feedback(
            candidate_id, round_index, feedback, rating, selected_for_next
        )
    
    @staticmethod
    def bulk_update_tracking_status() -> Dict[str, Any]:
        """
        Update tracking status for all interview candidates
        
        Returns:
            Dictionary with counts of updated and failed records
        """
        return InterviewTrackingService.bulk_update_tracking_status()
    
    @staticmethod
    def get_tracking_statistics_by_job(job_id: str) -> Dict[str, int]:
        """
        Get statistics about interview candidates for a job by their tracking status
        
        Args:
            job_id: ID of the job
            
        Returns:
            Dictionary with counts of candidates in each status
        """
        candidates = InterviewService.get_interview_candidates_by_job_id(job_id)
        
        # Initialize statistics
        stats = {
            "total": len(candidates),
            "scheduled": 0,
            "in_progress": 0,
            "rejected": 0,
            "passed": 0,
            "selected": 0,
            "completed": 0
        }
        
        # Count candidates by status
        for candidate in candidates:
            status = candidate.get("status", "scheduled")
            if status in stats:
                stats[status] += 1
        
        return stats
