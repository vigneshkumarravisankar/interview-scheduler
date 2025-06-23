"""
Calendar Agent Tools for CrewAI Agents
This module provides tools for agents to interact with calendar services and integrate with Firebase DB
"""
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from app.utils.calendar_service import CalendarService, create_calendar_event
from app.services.interview_core_service import InterviewCoreService
from app.services.interview_schedule_service import InterviewScheduleService
from app.services.interview_reschedule_service import InterviewRescheduleService
from app.services.candidate_service import CandidateService
from app.services.job_service import JobService
from app.database.firebase_db import FirestoreDB
from app.utils.email_notification import send_interview_notification

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScheduleInterviewTool(BaseTool):
    name: str = "ScheduleInterview"
    description: str = "Schedule an interview for a candidate with an interviewer"
    
    class InputSchema(BaseModel):
        candidate_id: str = Field(description="ID of the candidate")
        job_id: str = Field(description="ID of the job")
        interviewer_name: str = Field(description="Name of the interviewer")
        interviewer_email: str = Field(description="Email of the interviewer")
        round_number: int = Field(description="Round number (1-based)", default=1)
        specific_time: Optional[str] = Field(description="Specific time for the interview (format: YYYY-MM-DD HH:MM)", default=None)
        round_type: Optional[str] = Field(description="Type of interview round (e.g., Technical, HR, System Design)", default=None)
    
    args_schema = InputSchema
    
    def _run(self, 
             candidate_id: str, 
             job_id: str, 
             interviewer_name: str, 
             interviewer_email: str, 
             round_number: int = 1, 
             specific_time: Optional[str] = None, 
             round_type: Optional[str] = None) -> str:
        """
        Schedule an interview for a candidate
        
        Args:
            candidate_id: ID of the candidate
            job_id: ID of the job
            interviewer_name: Name of the interviewer
            interviewer_email: Email of the interviewer
            round_number: Round number (1-based)
            specific_time: Optional specific time for the interview
            round_type: Optional type of interview round
        
        Returns:
            String with scheduling results
        """
        try:
            # Validate candidate and job
            candidate = CandidateService.get_candidate(candidate_id)
            if not candidate:
                return f"Error: Candidate with ID {candidate_id} not found"
            
            job = JobService.get_job_posting(job_id)
            if not job:
                return f"Error: Job with ID {job_id} not found"
            
            # Convert job to dict if it's a Pydantic model
            job_dict = job
            if hasattr(job, "dict"):
                job_dict = job.dict()
            elif hasattr(job, "job_id"):
                job_dict = {
                    "job_id": job.job_id,
                    "job_role_name": job.job_role_name,
                    "job_description": job.job_description,
                    "years_of_experience_needed": job.years_of_experience_needed,
                    "location": getattr(job, "location", "Remote"),
                    "status": getattr(job, "status", "active")
                }
            
            # Find or create interview candidate record
            interview_candidates = InterviewCoreService.get_interview_candidates_by_candidate_id(candidate_id)
            interview_candidate = None
            
            # Filter for this specific job
            for ic in interview_candidates:
                if ic.get("job_id") == job_id:
                    interview_candidate = ic
                    break
            
            # If no record exists for this candidate and job, create one
            if not interview_candidate:
                # Create a new interview candidate record
                interview_candidate = {
                    "candidate_id": candidate_id,
                    "candidate_name": candidate.get("name"),
                    "candidate_email": candidate.get("email"),
                    "job_id": job_id,
                    "job_role": job_dict.get("job_role_name"),
                    "status": "scheduled",
                    "no_of_interviews": 3,  # Default to 3 rounds
                    "feedback": []
                }
                
                # Initialize feedback array with basic structure for rounds
                for i in range(3):
                    feedback_round = {
                        "round_number": i + 1,
                        "interviewer_name": interviewer_name if i == 0 else "",
                        "interviewer_email": interviewer_email if i == 0 else "",
                        "round_type": round_type if i == 0 and round_type else f"Round {i + 1}",
                        "feedback": "",
                        "rating_out_of_10": 0,
                        "isSelectedForNextRound": ""
                    }
                    interview_candidate["feedback"].append(feedback_round)
                
                # Create the record
                interview_candidate_id = InterviewCoreService.create_interview_candidate(interview_candidate)
                interview_candidate["id"] = interview_candidate_id
                
                logger.info(f"Created new interview candidate record: {interview_candidate_id}")
            else:
                logger.info(f"Found existing interview candidate record: {interview_candidate.get('id')}")
            
            # Adjust round number to 0-based index
            round_idx = round_number - 1
            
            # Make sure the round exists in the feedback array
            feedback_list = interview_candidate.get("feedback", [])
            if round_idx >= len(feedback_list):
                # Add more rounds if needed
                for i in range(len(feedback_list), round_idx + 1):
                    feedback_round = {
                        "round_number": i + 1,
                        "interviewer_name": interviewer_name if i == round_idx else "",
                        "interviewer_email": interviewer_email if i == round_idx else "",
                        "round_type": round_type if i == round_idx and round_type else f"Round {i + 1}",
                        "feedback": "",
                        "rating_out_of_10": 0,
                        "isSelectedForNextRound": ""
                    }
                    feedback_list.append(feedback_round)
            
            # Update round info
            feedback_list[round_idx]["interviewer_name"] = interviewer_name
            feedback_list[round_idx]["interviewer_email"] = interviewer_email
            if round_type:
                feedback_list[round_idx]["round_type"] = round_type
            
            # Update the record
            InterviewCoreService.update_interview_candidate(
                interview_candidate.get("id"),
                {"feedback": feedback_list}
            )
            
            # Create event title and description
            event_title = f"{job_dict.get('job_role_name')} Interview - Round {round_number} - {candidate.get('name')}"
            
            event_description = f"""
Interview for: {candidate.get('name')}
Position: {job_dict.get('job_role_name')}
Round: {round_number}

Job Description:
{job_dict.get('job_description')}

Candidate Information:
- Experience: {candidate.get('total_experience_in_years', 'N/A')} years
- Skills: {candidate.get('technical_skills', 'N/A')}

ATTENDEES:
- Interviewer: {interviewer_name} ({interviewer_email})
- Candidate: {candidate.get('name')} ({candidate.get('email')})
            """
            
            # Determine interview time slot
            if specific_time:
                # Parse specific time
                try:
                    slot_start = datetime.strptime(specific_time, "%Y-%m-%d %H:%M")
                    # Default to 1 hour interviews
                    slot_end = slot_start + timedelta(hours=1)
                    slot = {"start": slot_start, "end": slot_end}
                except ValueError:
                    return f"Error: Invalid time format. Please use YYYY-MM-DD HH:MM format."
            else:
                # Find next available slot
                start_date = datetime.now() + timedelta(days=1)
                slot = CalendarService.find_available_slot(
                    duration_minutes=60,
                    start_date=start_date
                )
                
                if not slot:
                    return f"No available time slot found. Please try specifying a time manually."
            
            # Create the calendar event
            attendees = [
                {"email": interviewer_email, "name": interviewer_name},
                {"email": candidate.get("email"), "name": candidate.get("name")}
            ]
            
            try:
                event = CalendarService.create_interview_event(
                    summary=event_title,
                    description=event_description,
                    start_time=slot.get("start"),
                    end_time=slot.get("end"),
                    attendees=attendees,
                    location=f"Google Meet (for {candidate.get('name')} and {interviewer_name})"
                )
                
                if not event:
                    return f"Failed to create calendar event"
                
                # Extract event details
                event_id = event.get("id")
                meet_link = None
                
                # Extract Google Meet link using various methods
                if 'manual_meet_link' in event:
                    meet_link = event['manual_meet_link']
                elif event.get("hangoutLink"):
                    meet_link = event.get("hangoutLink")
                elif event.get("location") and "meet.google.com" in event.get("location"):
                    location = event.get("location")
                    if "https://meet.google.com" in location:
                        meet_link = location.split("https://meet.google.com")[1].strip()
                        meet_link = f"https://meet.google.com{meet_link}"
                
                # Update the interview round with event details
                feedback_list[round_idx]["scheduled_event"] = {
                    "id": event_id,
                    "htmlLink": event.get("htmlLink"),
                    "start": event.get("start"),
                    "end": event.get("end")
                }
                
                # Store the meet link
                if meet_link:
                    feedback_list[round_idx]["meet_link"] = meet_link
                
                # Format datetime for display
                start_time = event.get("start", {}).get("dateTime", "")
                if start_time:
                    try:
                        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                        formatted_date = start_dt.strftime("%A, %B %d, %Y")
                        formatted_time = start_dt.strftime("%I:%M %p")
                    except:
                        formatted_date = "Invalid date"
                        formatted_time = "Invalid time"
                else:
                    formatted_date = "Unknown date"
                    formatted_time = "Unknown time"
                
                # Update the interview candidate record
                InterviewCoreService.update_interview_candidate(
                    interview_candidate.get("id"),
                    {"feedback": feedback_list}
                )
                
                # Send email notifications
                try:
                    send_interview_notification(
                        recipient_email=interviewer_email,
                        interviewer_name=interviewer_name,
                        candidate_name=candidate.get("name"),
                        job_title=job_dict.get("job_role_name"),
                        start_time=slot.get("start").isoformat() if isinstance(slot.get("start"), datetime) else slot.get("start"),
                        interview_date=formatted_date,
                        meet_link=meet_link,
                        round_number=round_number,
                        round_type=round_type if round_type else f"Round {round_number}",
                        interviewer_email=interviewer_email
                    )
                    
                    send_interview_notification(
                        recipient_email=candidate.get("email"),
                        interviewer_name=interviewer_name,
                        candidate_name=candidate.get("name"),
                        job_title=job_dict.get("job_role_name"),
                        start_time=slot.get("start").isoformat() if isinstance(slot.get("start"), datetime) else slot.get("start"),
                        interview_date=formatted_date,
                        meet_link=meet_link,
                        round_number=round_number,
                        round_type=round_type if round_type else f"Round {round_number}",
                        interviewer_email=interviewer_email
                    )
                except Exception as email_error:
                    logger.error(f"Error sending email notifications: {email_error}")
                
                # Return success message with details
                response = f"""
Successfully scheduled interview:

Candidate: {candidate.get("name")}
Position: {job_dict.get("job_role_name")}
Round: {round_number} {f"({round_type})" if round_type else ""}
Interviewer: {interviewer_name}
Date: {formatted_date}
Time: {formatted_time}
Google Meet: {meet_link if meet_link else "Link not available"}

Calendar event created and email notifications have been sent to both parties.
"""
                return response
            except Exception as e:
                logger.error(f"Error creating calendar event: {e}")
                return f"Error scheduling interview: {str(e)}"
        except Exception as e:
            logger.error(f"Error scheduling interview: {e}")
            return f"Error: {str(e)}"


class RescheduleInterviewTool(BaseTool):
    name: str = "RescheduleInterview"
    description: str = "Reschedule an existing interview to a new time"
    
    class InputSchema(BaseModel):
        interview_id: str = Field(description="ID of the interview record to reschedule")
        round_index: int = Field(description="Index of the round to reschedule (0-based)")
        new_time: str = Field(description="New time for the interview (format: 'YYYY-MM-DD HH:MM')")
        reason: str = Field(description="Reason for rescheduling", default="Scheduling conflict")
    
    args_schema = InputSchema
    
    def _run(self, interview_id: str, round_index: int, new_time: str, reason: str = "Scheduling conflict") -> str:
        """
        Reschedule an interview at a different time
        
        Args:
            interview_id: ID of the interview record to reschedule
            round_index: Index of the round to reschedule (0-based)
            new_time: New time for the interview (format: 'YYYY-MM-DD HH:MM')
            reason: Reason for rescheduling
        
        Returns:
            String with rescheduling results
        """
        try:
            # Validate the interview ID
            if not interview_id:
                # Try to find recent interviews in the database
                recent_interviews = FirestoreDB.get_all_documents("interview_candidates", limit=3)
                if recent_interviews:
                    suggestions = "\n\nAvailable interview records:\n"
                    for i, interview in enumerate(recent_interviews):
                        candidate_name = interview.get("candidate_name", "Unknown")
                        job_role = interview.get("job_role", "Unknown Position")
                        interview_id = interview.get("id", "Unknown")
                        suggestions += f"{i+1}. {candidate_name} for {job_role} (ID: {interview_id})\n"
                    return f"Error: Missing interview ID. Please provide a valid interview ID.{suggestions}"
                else:
                    return "Error: Missing interview ID. Please provide a valid interview ID."
            
            # Get the interview record
            interview_record = InterviewCoreService.get_interview_candidate(interview_id)
            
            if not interview_record:
                return f"Error: Interview record with ID {interview_id} not found."
                
            # Verify the round index is valid
            feedback_array = interview_record.get('feedback', [])
            if round_index < 0 or round_index >= len(feedback_array):
                return f"Error: Invalid round index {round_index}. Valid range: 0-{len(feedback_array)-1}"
            
            # Parse the new time
            try:
                new_datetime = datetime.strptime(new_time, "%Y-%m-%d %H:%M")
            except ValueError:
                return f"Error: Invalid time format. Please use the format 'YYYY-MM-DD HH:MM'"
            
            # Get job data
            job_id = interview_record.get("job_id", "")
            job_data = JobService.get_job_posting(job_id)
            
            if not job_data:
                # Create a minimal job data structure if job not found
                job_data_dict = {
                    "job_id": job_id,
                    "job_role_name": interview_record.get("job_role", "Unknown Position"),
                    "job_description": "Job description not available",
                }
            else:
                # Convert to dict if needed
                if hasattr(job_data, "dict"):
                    job_data_dict = job_data.dict()
                elif hasattr(job_data, "job_id"):
                    job_data_dict = {
                        "job_id": job_data.job_id,
                        "job_role_name": job_data.job_role_name,
                        "job_description": job_data.job_description,
                        "years_of_experience_needed": getattr(job_data, "years_of_experience_needed", "Not specified"),
                        "location": getattr(job_data, "location", "Remote"),
                        "status": getattr(job_data, "status", "active")
                    }
                else:
                    job_data_dict = {
                        "job_id": job_data.get("job_id", job_id),
                        "job_role_name": job_data.get("job_role_name", interview_record.get("job_role", "Unknown Position")),
                        "job_description": job_data.get("job_description", "No description available"),
                    }
            
            # Get the current round details
            round_details = feedback_array[round_index]
            
            # Check if there's an existing event to cancel
            old_event = round_details.get("scheduled_event", {})
            old_event_id = old_event.get("id")
            
            if old_event_id:
                # Delete the old event
                try:
                    CalendarService.delete_event(old_event_id)
                    logger.info(f"Deleted old calendar event: {old_event_id}")
                except Exception as del_error:
                    logger.error(f"Error deleting old calendar event: {del_error}")
            
            # Get interviewer and candidate details
            interviewer_name = round_details.get('interviewer_name', 'Unknown Interviewer')
            interviewer_email = round_details.get('interviewer_email', '')
            candidate_name = interview_record.get('candidate_name', 'Unknown Candidate')
            candidate_email = interview_record.get('candidate_email', '')
            round_type = round_details.get('round_type', f"Round {round_index+1}")
            
            # Create event summary and description
            event_title = f"{job_data_dict.get('job_role_name')} Interview - Round {round_index + 1} ({round_type}) - {candidate_name} (Rescheduled)"
            
            event_description = f"""
RESCHEDULED INTERVIEW for {candidate_name} ({candidate_email})
Position: {job_data_dict.get('job_role_name')}
Round: {round_index+1} - {round_type}
Interviewer: {interviewer_name} ({interviewer_email})

Reason for rescheduling: {reason}

Job Description:
{job_data_dict.get('job_description')}

Please join using the Google Meet link at the scheduled time.
"""

            # Create a new calendar event
            start_time = new_datetime
            end_time = new_datetime + timedelta(hours=1)  # 1 hour interview
            
            attendees = []
            if interviewer_email:
                attendees.append({"email": interviewer_email})
            if candidate_email:
                attendees.append({"email": candidate_email})
            
            calendar_event = create_calendar_event(
                summary=event_title,
                description=event_description,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
                attendees=attendees
            )
            
            if not calendar_event:
                return "Error: Failed to create calendar event for the rescheduled interview."
            
            # Extract event details
            event_id = calendar_event.get('id', '')
            meet_link = None
            
            # Extract Google Meet link using various methods
            if 'manual_meet_link' in calendar_event:
                meet_link = calendar_event['manual_meet_link']
            elif calendar_event.get("hangoutLink"):
                meet_link = calendar_event.get("hangoutLink")
            elif calendar_event.get("location") and "meet.google.com" in calendar_event.get("location"):
                location = calendar_event.get("location")
                if "https://meet.google.com" in location:
                    meet_link = location.split("https://meet.google.com")[1].strip()
                    meet_link = f"https://meet.google.com{meet_link}"
            
            # Update round details in Firebase
            formatted_time = start_time.strftime("%I:%M %p").lstrip('0')  # e.g., "10 AM"
            interview_date = start_time.strftime("%A, %B %d, %Y")  # e.g., "Monday, January 1, 2024"
            
            # Update the round details
            round_details['scheduled_time'] = formatted_time
            round_details['meet_link'] = meet_link if meet_link else "Link not available"
            round_details['rescheduled'] = True
            round_details['reschedule_reason'] = reason
            
            round_details['scheduled_event'] = {
                "id": event_id,
                "htmlLink": calendar_event.get('htmlLink', ''),
                "start": {
                    "dateTime": start_time.isoformat(),
                    "timeZone": "Asia/Kolkata"
                },
                "end": {
                    "dateTime": end_time.isoformat(),
                    "timeZone": "Asia/Kolkata"
                }
            }
            
            # Update the feedback array
            feedback_array[round_index] = round_details
            
            # Update the database
            InterviewCoreService.update_interview_candidate(
                interview_id,
                {"feedback": feedback_array}
            )
            
            # Send email notifications
            try:
                send_interview_notification(
                    candidate_name=candidate_name,
                    recipient_email=candidate_email,
                    interviewer_name=interviewer_name,
                    interviewer_email=interviewer_email,
                    job_title=job_data_dict.get('job_role_name'),
                    start_time=formatted_time,
                    interview_date=interview_date,
                    meet_link=meet_link if meet_link else "Link not available",
                    round_number=round_index+1,
                    round_type=round_type,
                    is_rescheduled=True,
                    reschedule_reason=reason
                )
                
                send_interview_notification(
                    candidate_name=candidate_name,
                    recipient_email=interviewer_email,
                    interviewer_name=interviewer_name,
                    interviewer_email=interviewer_email,
                    job_title=job_data_dict.get('job_role_name'),
                    start_time=formatted_time,
                    interview_date=interview_date,
                    meet_link=meet_link if meet_link else "Link not available",
                    round_number=round_index+1,
                    round_type=round_type,
                    is_rescheduled=True,
                    reschedule_reason=reason
                )
                
                email_status = "Email notifications sent to both parties."
            except Exception as email_error:
                logger.error(f"Error sending email notifications: {email_error}")
                email_status = "Failed to send email notifications."
            
            # Return success message
            return f"""
Successfully rescheduled the interview for {candidate_name} with {interviewer_name}.

New Interview Details:
- Date: {interview_date}
- Time: {formatted_time}
- Position: {job_data_dict.get('job_role_name')}
- Round: {round_index+1} ({round_type})
- Meet Link: {meet_link if meet_link else "Not available"}

{email_status}
"""
            
        except Exception as e:
            logger.error(f"Error rescheduling interview: {e}")
            return f"Error rescheduling interview: {str(e)}"


class GetCalendarAvailabilityTool(BaseTool):
    name: str = "GetCalendarAvailability"
    description: str = "Find available time slots in the calendar for scheduling"
    
    class InputSchema(BaseModel):
        start_date: str = Field(description="Start date to check availability (format: YYYY-MM-DD)", default=None)
        end_date: str = Field(description="End date to check availability (format: YYYY-MM-DD)", default=None)
        duration_minutes: int = Field(description="Duration needed for the meeting in minutes", default=60)
        working_hours_start: int = Field(description="Start hour for working hours (24-hour format)", default=9)
        working_hours_end: int = Field(description="End hour for working hours (24-hour format)", default=17)
    
    args_schema = InputSchema
    
    def _run(self, start_date: Optional[str] = None, end_date: Optional[str] = None, 
             duration_minutes: int = 60, working_hours_start: int = 9, working_hours_end: int = 17) -> str:
        """
        Find available time slots in the calendar
        
        Args:
            start_date: Start date to check availability (format: YYYY-MM-DD)
            end_date: End date to check availability (format: YYYY-MM-DD)
            duration_minutes: Duration needed for the meeting in minutes
            working_hours_start: Start hour for working hours (24-hour format)
            working_hours_end: End hour for working hours (24-hour format)
        
        Returns:
            String with available time slots
        """
        try:
            # Parse dates or use defaults
            if start_date:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
            else:
                start_dt = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
            
            if end_date:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            else:
                end_dt = start_dt + timedelta(days=7)
            
            working_hours = {
                'start': working_hours_start,
                'end': working_hours_end
            }
            
            # Get events in the date range
            events = CalendarService.get_events(time_min=start_dt, time_max=end_dt)
            
            # Convert events to busy slots
            busy_slots = []
            for event in events:
                start = event.get('start', {}).get('dateTime')
                end = event.get('end', {}).get('dateTime')
                
                if start and end:
                    start_dt_event = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    end_dt_event = datetime.fromisoformat(end.replace('Z', '+00:00'))
                    
                    # Remove timezone info for easier comparison
                    start_dt_event = start_dt_event.replace(tzinfo=None)
                    end_dt_event = end_dt_event.replace(tzinfo=None)
                    
                    busy_slots.append((start_dt_event, end_dt_event))
            
            # Find available slots
            available_slots = []
            current_date = start_dt
            
            while current_date.date() <= end_dt.date():
                # Skip weekends
                if current_date.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
                    current_date += timedelta(days=1)
                    continue
                
                # Working hours for the day
                day_start = current_date.replace(hour=working_hours['start'], minute=0)
                day_end = current_date.replace(hour=working_hours['end'], minute=0)
                
                slot_start = day_start
                
                while slot_start < day_end:
                    slot_end = slot_start + timedelta(minutes=duration_minutes)
                    
                    # Skip if slot extends beyond working hours
                    if slot_end > day_end:
                        break
                    
                    # Check if slot overlaps with any busy time
                    is_free = True
                    for busy_start, busy_end in busy_slots:
                        if slot_start < busy_end and slot_end > busy_start:
                            is_free = False
                            # Move to the end of this busy slot
                            slot_start = busy_end
                            break
                    
                    if is_free:
                        # Add to available slots
                        available_slots.append((slot_start, slot_end))
                        # Move to next slot (30-minute increments)
                        slot_start += timedelta(minutes=30)
                    # If not free, the slot_start has already been updated in the loop
                
                # Move to next day
                current_date += timedelta(days=1)
            
            # Format the results
            if not available_slots:
                return "No available time slots found in the specified date range."
            
            result = f"Found {len(available_slots)} available time slots:\n\n"
            
            # Group by date for cleaner output
            slots_by_date = {}
            for start, end in available_slots:
                date_str = start.strftime("%Y-%m-%d")
                if date_str not in slots_by_date:
                    slots_by_date[date_str] = []
                slots_by_date[date_str].append((start, end))
            
            for date_str, slots in slots_by_date.items():
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                formatted_date = date_obj.strftime("%A, %B %d, %Y")
                result += f"{formatted_date}:\n"
                
                # Sort slots chronologically
                slots.sort(key=lambda x: x[0])
                
                # Format each time slot
                for start, end in slots:
                    start_time = start.strftime("%I:%M %p").lstrip('0')
                    end_time = end.strftime("%I:%M %p").lstrip('0')
                    result += f"  • {start_time} - {end_time}\n"
                
                result += "\n"
            
            return result
            
        except Exception as e:
            logger.error(f"Error finding available calendar slots: {e}")
            return f"Error: {str(e)}"
