"""
Interview rescheduling functionality
"""
import datetime
from typing import Dict, Any
from app.services.candidate_service import CandidateService
from app.utils.calendar_service import CalendarService
from app.utils.email_notification import send_interview_notification
from app.services.interview_core_service import InterviewCoreService


class InterviewRescheduleService:
    """Service for handling interview rescheduling"""
    
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
        try:
            # Get interview candidate
            interview_candidate = InterviewCoreService.get_interview_candidate(candidate_id)
            if not interview_candidate:
                print(f"Interview candidate with ID {candidate_id} not found")
                return False
            
            # Check if round index is valid
            feedback_list = interview_candidate.get("feedback", [])
            if round_idx < 0 or round_idx >= len(feedback_list):
                print(f"Invalid round index {round_idx}")
                return False
            
            # Get round data
            round_data = feedback_list[round_idx]
            
            # Check if there's an existing event to cancel
            scheduled_event = round_data.get("scheduled_event")
            if not scheduled_event:
                print(f"No scheduled event found for candidate {candidate_id}, round {round_idx + 1}")
                return False
            
            # Get interviewer info
            interviewer_name = round_data.get("interviewer_name")
            interviewer_email = round_data.get("interviewer_email")
            
            # Skip if interviewer info is missing
            if not interviewer_name or not interviewer_email:
                print(f"Missing interviewer info for round {round_idx + 1}")
                return False
            
            # Get candidate data
            original_candidate_id = interview_candidate.get("candidate_id")
            candidate = CandidateService.get_candidate(original_candidate_id)
            if not candidate:
                print(f"Candidate with ID {original_candidate_id} not found")
                return False
            
            # Try to cancel the existing event
            try:
                event_id = scheduled_event.get("id")
                if event_id:
                    print(f"Attempting to cancel event {event_id}")
                    # Not handling result since we want to proceed with rescheduling anyway
                    CalendarService.delete_event(event_id)
            except Exception as cancel_error:
                print(f"Error canceling event: {cancel_error}")
                # Continue with rescheduling even if cancel fails
            
            # Create event title and description
            event_title = f"{job_data.get('job_role_name')} Interview - Round {round_idx + 1} - {candidate.get('name')} (Rescheduled)"
            
            # Include attendee info in description instead of using attendees parameter
            event_description = f"""
Interview for: {candidate.get('name')}
Position: {job_data.get('job_role_name')}
Round: {round_idx + 1}
Status: Rescheduled

Job Description:
{job_data.get('job_description')}

Candidate Information:
- Experience: {candidate.get('total_experience_in_years')} years
- Skills: {candidate.get('technical_skills')}

ATTENDEES (will be notified separately):
- Interviewer: {interviewer_name} ({interviewer_email})
- Candidate: {candidate.get('name')} ({candidate.get('email')})

NOTE: This interview was rescheduled due to a previous decline.
            """
            
            # Find an available time slot
            # Use tomorrow if specified, otherwise next available
            if tomorrow:
                # Schedule for tomorrow
                start_date = datetime.datetime.now() + datetime.timedelta(days=1)
            else:
                # Schedule for the day after tomorrow to give more time
                start_date = datetime.datetime.now() + datetime.timedelta(days=2)
                
            # Find a slot
            slot = CalendarService.find_available_slot(
                duration_minutes=60,
                start_date=start_date
            )
            
            if not slot:
                print(f"No available time slot found for rescheduling candidate {candidate_id}, round {round_idx + 1}")
                return False
            
            try:
                # Schedule the rescheduled event
                event = CalendarService.create_interview_event(
                    summary=event_title,
                    description=event_description,
                    start_time=slot.get("start"),
                    end_time=slot.get("end"),
                    attendees=None,  # Skip attendees to avoid 403 error
                    location=f"Google Meet (for {candidate.get('name')} and {interviewer_name}) - Rescheduled"
                )
                
                if not event:
                    print(f"Failed to create calendar event for rescheduled interview")
                    return False
                
                # Update the record
                event_id = event.get("id")
                meet_link = None
                
                # Reset response statuses
                if "interviewer_response" in round_data:
                    del round_data["interviewer_response"]
                if "candidate_response" in round_data:
                    del round_data["candidate_response"]
                
                # Store that this is a rescheduled event
                round_data["rescheduled"] = True
                
                # Store event details
                round_data["scheduled_event"] = {
                    "id": event_id,
                    "htmlLink": event.get("htmlLink"),
                    "start": event.get("start"),
                    "end": event.get("end")
                }
                
                # Extract Google Meet link using our various methods
                # 1. First check if we have a manually generated Meet link
                if 'manual_meet_link' in event:
                    meet_link = event['manual_meet_link']
                    print(f"Using manually generated Google Meet link: {meet_link}")
                # 2. Check if there's a conferenceData entry
                elif event.get("conferenceData") and event.get("conferenceData").get("entryPoints"):
                    meet_link = next((entry_point.get("uri") for entry_point in event.get("conferenceData").get("entryPoints") 
                                    if entry_point.get("entryPointType") == "video"), None)
                    if meet_link:
                        print(f"Found Google Meet link in conferenceData: {meet_link}")
                # 3. Check for hangoutLink
                elif event.get("hangoutLink"):
                    meet_link = event.get("hangoutLink")
                    print(f"Found Google Meet link in hangoutLink: {meet_link}")
                # 4. Check if location has a meet link
                elif event.get("location") and "meet.google.com" in event.get("location"):
                    # Try to extract from location
                    location = event.get("location")
                    if "https://meet.google.com" in location:
                        meet_link = location.split("https://meet.google.com")[1].strip()
                        meet_link = f"https://meet.google.com{meet_link}"
                        print(f"Extracted Google Meet link from location: {meet_link}")
                
                # Store the meet link if found
                if meet_link:
                    round_data["meet_link"] = meet_link
                else:
                    print("No Google Meet link could be extracted from the event")
                
                # Update the document
                InterviewCoreService.update_interview_candidate(
                    candidate_id,
                    {"feedback": feedback_list}
                )
                
                # Send email notifications
                try:
                    # Event start/end times
                    start_time = event.get("start", {}).get("dateTime", "")
                    end_time = event.get("end", {}).get("dateTime", "")
                    job_title = job_data.get("job_role_name", "")
                    
                    # Add rescheduled flag to email notifications
                    rescheduled_note = "This interview has been rescheduled due to a previous decline."
                    
                    # Send notifications
                    send_interview_notification(
                        recipient_email=interviewer_email,
                        start_time=start_time,
                        end_time=end_time,
                        meet_link=meet_link,
                        event_id=event_id,
                        interviewer_name=interviewer_name,
                        candidate_name=candidate.get("name"),
                        job_title=job_title,
                        additional_note=rescheduled_note,
                        interviewer_email=interviewer_email  # Pass interviewer_email
                    )
                    
                    send_interview_notification(
                        recipient_email=candidate.get("email"),
                        start_time=start_time,
                        end_time=end_time,
                        meet_link=meet_link,
                        event_id=event_id,
                        interviewer_name=interviewer_name,
                        candidate_name=candidate.get("name"),
                        job_title=job_title,
                        additional_note=rescheduled_note,
                        interviewer_email=interviewer_email  # Pass interviewer_email
                    )
                    
                    print(f"Email notifications sent for rescheduled interview")
                except Exception as email_error:
                    print(f"Error sending email notifications: {email_error}")
                    # Continue even if emails fail
                
                return True
            except Exception as e:
                print(f"Error rescheduling interview: {e}")
                return False
        except Exception as e:
            print(f"Error rescheduling interview: {e}")
            return False
