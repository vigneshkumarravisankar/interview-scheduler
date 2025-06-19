"""
Interview scheduling functionality
"""
import datetime
from typing import Dict, Any, List
from app.services.candidate_service import CandidateService
from app.utils.calendar_service import CalendarService
from app.utils.email_notification import send_interview_notification
from app.services.interview_core_service import InterviewCoreService


class InterviewScheduleService:
    """Service for interview scheduling functionality"""
    
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
        try:
            # Get all candidates data to include in invitations
            all_candidates = {c.get("id"): c for c in CandidateService.get_all_candidates()}
            
            # Results dictionary: candidate_id -> list of scheduled events
            scheduled_events = {}
            
            # Schedule interviews for each candidate
            for interview_candidate in interview_candidates:
                candidate_id = interview_candidate.get("candidate_id")
                candidate = all_candidates.get(candidate_id)
                
                if not candidate:
                    print(f"Candidate data not found for ID: {candidate_id}")
                    continue
                
                # List to store events for this candidate
                events = []
                
                # Schedule each interview round
                for round_idx, feedback in enumerate(interview_candidate.get("feedback", [])):
                    interviewer_name = feedback.get("interviewer_name")
                    interviewer_email = feedback.get("interviewer_email")
                    
                    # Skip if interviewer info is missing
                    if not interviewer_name or not interviewer_email:
                        print(f"Missing interviewer info for round {round_idx + 1}")
                        continue
                    
                    # Only schedule the first round initially
                    # Later rounds will be scheduled only after previous rounds are completed successfully
                    if round_idx > 0:
                        # Skip for now, will be scheduled after first round feedback
                        print(f"Skipping scheduling for round {round_idx + 1} until previous round is completed")
                        continue
                    
                    # Create event title and description
                    event_title = f"{job_data.get('job_role_name')} Interview - Round {round_idx + 1} - {candidate.get('name')}"
                    
                    # Include attendee info in description instead of using attendees parameter
                    # This works around the "Service accounts cannot invite attendees" limitation
                    event_description = f"""
Interview for: {candidate.get('name')}
Position: {job_data.get('job_role_name')}
Round: {round_idx + 1}

Job Description:
{job_data.get('job_description')}

Candidate Information:
- Experience: {candidate.get('total_experience_in_years')} years
- Skills: {candidate.get('technical_skills')}

ATTENDEES (will be notified separately):
- Interviewer: {interviewer_name} ({interviewer_email})
- Candidate: {candidate.get('name')} ({candidate.get('email')})

NOTE: Due to service account limitations, calendar invitations are not automatically sent.
In a production environment, you would need Domain-Wide Delegation of Authority configured.
                    """
                    
                    # Find an available time slot (default to 1 hour duration, in working hours)
                    # Try to schedule interviews starting tomorrow
                    start_date = datetime.datetime.now() + datetime.timedelta(days=1)
                    slot = CalendarService.find_available_slot(
                        duration_minutes=60,
                        start_date=start_date
                    )
                    
                    if not slot:
                        print(f"No available time slot found for candidate {candidate_id}, round {round_idx + 1}")
                        continue
                    
                    try:
                        # Schedule event in calendar without attendees parameter
                        event = CalendarService.create_interview_event(
                            summary=event_title,
                            description=event_description,
                            start_time=slot.get("start"),
                            end_time=slot.get("end"),
                            attendees=None,  # Skip attendees to avoid 403 error
                            location=f"Google Meet (for {candidate.get('name')} and {interviewer_name})"
                        )
                        
                        # Add attendee info to the event object manually for the response
                        # (this won't be sent to the calendar but will be in our response)
                        if event:
                            event['manual_attendees'] = [
                                {"email": interviewer_email, "name": interviewer_name},
                                {"email": candidate.get("email"), "name": candidate.get("name")}
                            ]
                            events.append(event)
                            print(f"Interview scheduled for candidate {candidate_id}, round {round_idx + 1}")
                            
                            # Update the interview_candidate document with the event info
                            round_data = interview_candidate.get("feedback")[round_idx]
                            event_id = event.get("id")
                            meet_link = None
                            
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
                                interview_candidate.get("id"),
                                {"feedback": interview_candidate.get("feedback")}
                            )
                            
                            # Send email notifications with accept/decline links
                            try:
                                # Event start/end times in ISO format
                                start_time = event.get("start", {}).get("dateTime", "")
                                end_time = event.get("end", {}).get("dateTime", "")
                                job_title = job_data.get("job_role_name", "")
                                
                                # Add note about the initial interview
                                additional_note = f"This is the initial interview for the {job_title} position."
                                
                                # Send to interviewer
                                send_interview_notification(
                                    recipient_email=interviewer_email,
                                    start_time=start_time,
                                    end_time=end_time,
                                    meet_link=meet_link,
                                    event_id=event_id,
                                    interviewer_name=interviewer_name,
                                    candidate_name=candidate.get("name"),
                                    job_title=job_title,
                                    additional_note=additional_note,
                                    interviewer_email=interviewer_email  # Pass interviewer_email
                                )
                                
                                # Send to candidate
                                send_interview_notification(
                                    recipient_email=candidate.get("email"),
                                    start_time=start_time,
                                    end_time=end_time,
                                    meet_link=meet_link,
                                    event_id=event_id,
                                    interviewer_name=interviewer_name,
                                    candidate_name=candidate.get("name"),
                                    job_title=job_title,
                                    additional_note=additional_note,
                                    interviewer_email=interviewer_email  # Pass interviewer_email
                                )
                                
                                print(f"Email notifications sent for interview round {round_idx + 1}")
                            except Exception as email_error:
                                print(f"Error sending email notifications: {email_error}")
                                # Continue with the process even if email sending fails
                    except Exception as event_error:
                        print(f"Error creating event: {event_error}")
                        continue
                
                # Store all events for this candidate
                if events:
                    scheduled_events[candidate_id] = events
            
            return scheduled_events
        except Exception as e:
            print(f"Error scheduling interviews: {e}")
            return {}
            
    @staticmethod
    def schedule_next_round(interview_candidate_id: str) -> bool:
        """
        Schedule the next round of interviews for a candidate after they pass a round
        
        Args:
            interview_candidate_id: ID of the interview candidate
        
        Returns:
            True if successfully scheduled, False otherwise
        """
        try:
            # Get candidate record
            candidate_record = InterviewCoreService.get_interview_candidate(interview_candidate_id)
            if not candidate_record:
                print(f"Interview candidate with ID {interview_candidate_id} not found")
                return False
            
            # Get job record
            from app.services.job_service import JobService
            job_id = candidate_record.get("job_id")
            job_data = JobService.get_job_posting(job_id)
            if not job_data:
                print(f"Job with ID {job_id} not found")
                return False
            
            # Convert job_data (JobPostingResponse) to a dictionary - handle both Pydantic models and dictionaries
            if hasattr(job_data, "job_id"):
                # It's a Pydantic model
                job_data_dict = {
                    "job_id": job_data.job_id,
                    "job_role_name": job_data.job_role_name,
                    "job_description": job_data.job_description,
                    "years_of_experience_needed": job_data.years_of_experience_needed
                }
            else:
                # It's already a dictionary or similar
                job_data_dict = {
                    "job_id": job_data.get("job_id", ""),
                    "job_role_name": job_data.get("job_role_name", "Unknown Position"),
                    "job_description": job_data.get("job_description", "No description available"),
                    "years_of_experience_needed": job_data.get("years_of_experience_needed", "Not specified")
                }
                
            # Get feedback from all rounds
            feedback_list = candidate_record.get("feedback", [])
            
            # Find the last completed round
            last_completed_round = -1
            for idx, feedback in enumerate(feedback_list):
                if feedback.get("isSelectedForNextRound") == "yes" and feedback.get("feedback") and feedback.get("rating_out_of_10"):
                    last_completed_round = idx
                elif "scheduled_event" in feedback and idx > last_completed_round + 1:
                    # If this round is already scheduled but not completed, no need to schedule more
                    return False
            
            # Next round to schedule
            next_round_idx = last_completed_round + 1
            
            # Check if we've reached the end of rounds
            if next_round_idx >= len(feedback_list) or next_round_idx >= candidate_record.get("no_of_interviews", 0):
                print(f"All rounds completed for candidate {interview_candidate_id}")
                return False
            
            # Get candidate data
            candidate_id = candidate_record.get("candidate_id")
            candidate = CandidateService.get_candidate(candidate_id)
            if not candidate:
                print(f"Candidate with ID {candidate_id} not found")
                return False
            
            # Get next round's interviewer
            feedback = feedback_list[next_round_idx]
            interviewer_name = feedback.get("interviewer_name")
            interviewer_email = feedback.get("interviewer_email")
            
            # Skip if interviewer info is missing
            if not interviewer_name or not interviewer_email:
                print(f"Missing interviewer info for round {next_round_idx + 1}")
                return False
            
            # Create event title and description
            event_title = f"{job_data_dict['job_role_name']} Interview - Round {next_round_idx + 1} - {candidate.get('name')}"
            
            event_description = f"""
Interview for: {candidate.get('name')}
Position: {job_data_dict['job_role_name']}
Round: {next_round_idx + 1}

Job Description:
{job_data_dict['job_description']}

Candidate Information:
- Experience: {candidate.get('total_experience_in_years')} years
- Skills: {candidate.get('technical_skills')}

ATTENDEES (will be notified separately):
- Interviewer: {interviewer_name} ({interviewer_email})
- Candidate: {candidate.get('name')} ({candidate.get('email')})

Previous Round Feedback:
{feedback_list[last_completed_round].get('feedback')}
Rating: {feedback_list[last_completed_round].get('rating_out_of_10')}/10
            """
            
            # Find next available slot (try for tomorrow)
            start_date = datetime.datetime.now() + datetime.timedelta(days=1)
            slot = CalendarService.find_available_slot(
                duration_minutes=60,
                start_date=start_date
            )
            
            if not slot:
                print(f"No available time slot found for candidate {candidate_id}, round {next_round_idx + 1}")
                return False
            
            # Schedule the event
            event = CalendarService.create_interview_event(
                summary=event_title,
                description=event_description,
                start_time=slot.get("start"),
                end_time=slot.get("end"),
                attendees=None,
                location=f"Google Meet (for {candidate.get('name')} and {interviewer_name})"
            )
            
            if not event:
                print(f"Failed to create calendar event for round {next_round_idx + 1}")
                return False
            
            # Update the record
            event_id = event.get("id")
            meet_link = None
            
            # Store event details
            feedback["scheduled_event"] = {
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
                feedback["meet_link"] = meet_link
            else:
                print("No Google Meet link could be extracted from the event")
            
            # Update the document
            InterviewCoreService.update_interview_candidate(
                interview_candidate_id,
                {"feedback": feedback_list}
            )
            
            # Send email notifications
            try:
                # Event start/end times
                start_time = event.get("start", {}).get("dateTime", "")
                end_time = event.get("end", {}).get("dateTime", "")
                job_title = job_data_dict.get("job_role_name", "")
                
                # Add note about next round
                additional_note = f"Congratulations! You have been selected for Round {next_round_idx + 1} of the interview process."
                
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
                    additional_note=f"This is Round {next_round_idx + 1} interview. The candidate passed the previous round.",
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
                    additional_note=additional_note,
                    interviewer_email=interviewer_email  # Pass interviewer_email
                )
                
                print(f"Email notifications sent for next round interview")
                return True
            except Exception as email_error:
                print(f"Error sending email notifications: {email_error}")
                # Continue even if emails fail
                return True
                
        except Exception as e:
            print(f"Error scheduling next round: {e}")
            return False
