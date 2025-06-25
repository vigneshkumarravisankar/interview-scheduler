"""
Specialized CrewAI Agents for Interview Process

This module contains specialized agents for:
1. Candidate Shortlisting - Selects top N candidates based on AI fit scores
2. Interview Scheduling - Manages the scheduling process including calendar, meet, and email

These agents are designed to work both independently and together as part of a crew.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json
import random
import string
import uuid

# CrewAI imports
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool

# Use direct OpenAI for LLM instead of deprecated LangChain
import openai

# Service imports
from app.services.candidate_service import CandidateService
from app.services.job_service import JobService
from app.services.interview_core_service import InterviewCoreService
from app.database.chroma_db import FirestoreDB, ChromaVectorDB
from app.utils.calendar_service import create_calendar_event
from app.utils.email_notification import send_interview_notification

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize LLM model for CrewAI
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY not found in environment. Using default key.")
    # Default key from project setup
    OPENAI_API_KEY = "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"

# Create a simple LLM wrapper to avoid compatibility issues
class SimpleLLM:
    def __init__(self, api_key, model="gpt-4o", temperature=0.2):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature

# Initialize simple LLM
llm = SimpleLLM(api_key=OPENAI_API_KEY)

#-----------------------
# Shortlisting Agent Tools
#-----------------------

@tool("FindJobByRole")
def find_job_by_role(role_name: str) -> str:
    """Find a job by its role name in the jobs collection"""
    try:
        # Validate role name is not empty
        if not role_name or role_name.strip() == "":
            return "ERROR: You must provide a specific job role name. Empty role names are not allowed."
        
        # Query the jobs collection for a job with this role name
        print(f"Executing FindJobByRole tool with role_name='{role_name}'")
        jobs = FirestoreDB.execute_query("jobs", "job_role_name", "==", role_name)
        
        if not jobs or len(jobs) == 0:
            return f"No jobs found with role name '{role_name}'. Please provide a valid role name that exists in the system."
        
        result = f"Found {len(jobs)} jobs matching role '{role_name}':\n\n"
        
        for i, job in enumerate(jobs):
            # Format job info
            result += f"Job {i+1}:\n"
            result += f"ID: {job.get('id', job.get('job_id', 'Unknown'))}\n"
            result += f"Role: {job.get('job_role_name', 'Unknown')}\n"
            result += f"Description: {job.get('job_description', 'No description')[:100]}...\n"
            result += f"Experience Required: {job.get('years_of_experience_needed', 'Unknown')}\n\n"
        
        return result
    except Exception as e:
        return f"Error finding jobs: {str(e)}"

@tool("GetCandidates")
def get_candidates(job_id: str) -> str:
    """Get all candidates for a specific job"""
    try:
        # First verify the job exists
        job = JobService.get_job_posting(job_id)
        if not job:
            return f"Job with ID {job_id} not found in jobs collection"
            
        # Then get candidates
        candidates = CandidateService.get_candidates_by_job_id(job_id)
        
        if not candidates:
            return f"No candidates found for job {job_id}"
        
        result = f"Found {len(candidates)} candidates for job {job_id}:\n\n"
        
        for i, candidate in enumerate(candidates):
            # Format candidate info
            result += f"Candidate {i+1}:\n"
            result += f"Name: {candidate.name}\n"
            result += f"Email: {candidate.email}\n"
            result += f"Experience: {candidate.total_experience_in_years} years\n"
            result += f"Skills: {candidate.technical_skills}\n"
            result += f"AI Fit Score: {candidate.ai_fit_score}\n\n"
        
        return result
    except Exception as e:
        return f"Error getting candidates: {str(e)}"

@tool("ShortlistCandidatesByRole")
def shortlist_candidates_by_role(role_name: str, number_of_candidates: int = 2) -> str:
    """Find a job by role name, then shortlist top candidates based on AI fit score"""
    try:
        # Validate role name is not empty
        if not role_name or role_name.strip() == "":
            return "ERROR: You must provide a specific job role name. Empty role names are not allowed."
            
        # First find the job by role name
        print(f"Searching for jobs with exact role name: '{role_name}'")
        jobs = FirestoreDB.execute_query("jobs", "job_role_name", "==", role_name)
        
        if not jobs or len(jobs) == 0:
            return f"No jobs found with role name '{role_name}'. Please provide an exact job role name that exists in the system."
        
        # Take the first matching job
        job = jobs[0]
        job_id = job.get('id', job.get('job_id'))
        
        if not job_id:
            return f"Error: Found job but couldn't determine job_id"
        
        # Now shortlist candidates for this job
        return _shortlist_candidates_helper(job_id, number_of_candidates)
    except Exception as e:
        return f"Error in shortlisting by role: {str(e)}"

@tool("ShortlistCandidates")
def shortlist_candidates(job_id: str, number_of_candidates: int = 2) -> str:
    """Shortlist top N candidates for a job based on AI fit score"""
    try:
        return _shortlist_candidates_helper(job_id, number_of_candidates)
    except Exception as e:
        return f"Error shortlisting candidates: {str(e)}"

def _shortlist_candidates_helper(job_id: str, number_of_candidates: int = 2) -> str:
    """Helper function to shortlist candidates for a job ID"""
    try:
        # Verify the job exists
        job = JobService.get_job_posting(job_id)
        if not job:
            return f"Job with ID {job_id} not found in jobs collection"
            
        # Get candidates for this job
        candidates = CandidateService.get_candidates_by_job_id(job_id)
        
        if not candidates:
            return f"No candidates found for job {job_id}"
        
        # Sort candidates by AI fit score (descending)
        try:
            sorted_candidates = sorted(
                candidates,
                key=lambda c: int(c.ai_fit_score),
                reverse=True
            )
        except (ValueError, TypeError) as e:
            return f"Error sorting candidates: {str(e)}"
        
        # Take top N
        shortlisted = sorted_candidates[:min(number_of_candidates, len(sorted_candidates))]
        
        result = f"Shortlisted {len(shortlisted)} candidates out of {len(candidates)} for job {job_id}:\n\n"
        
        for i, candidate in enumerate(shortlisted):
            # Format candidate info
            result += f"Candidate {i+1}:\n"
            result += f"Name: {candidate.name}\n"
            result += f"Email: {candidate.email}\n"
            result += f"Experience: {candidate.total_experience_in_years} years\n"
            result += f"Skills: {candidate.technical_skills}\n"
            result += f"AI Fit Score: {candidate.ai_fit_score}\n\n"
        
        # Create interview candidate records directly in interview_candidates collection
        for candidate in shortlisted:
            # Create feedback array based on standard round types (modified per user requirement)
            feedback_array = []
            
            # Create the interview candidate record
            interview_candidate = {
                "job_id": job_id,
                "candidate_id": candidate.id,
                "candidate_name": candidate.name,
                "candidate_email": candidate.email,
                "job_role": job.job_role_name,
                "no_of_interviews": 2,  # Default to 2 rounds
                "feedback": feedback_array,
                "completedRounds": 0,
                "nextRoundIndex": 0,
                "status": "shortlisted",
                "last_updated": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat(),
                "current_round_scheduled": False
            }
            
            # Save to database
            doc_id = InterviewCoreService.create_interview_candidate(interview_candidate)
            result += f"Created interview record with ID: {doc_id}\n"
        
        return result
    except Exception as e:
        return f"Error shortlisting candidates: {str(e)}"

@tool("GetJobDetails")
def get_job_details(job_id: str) -> str:
    """Get job details for a specific job ID"""
    try:
        job = JobService.get_job_posting(job_id)
        
        if not job:
            return f"Job with ID {job_id} not found"
        
        result = f"Job details for {job_id}:\n\n"
        result += f"Role: {job.job_role_name}\n"
        result += f"Description: {job.job_description}\n"
        result += f"Experience Required: {job.years_of_experience_needed} years\n"
        
        return result
    except Exception as e:
        return f"Error getting job details: {str(e)}"

#-----------------------
# Scheduling Agent Tools
#-----------------------
# Import advanced calendar tools
from app.utils.calendar_service import CalendarService, create_calendar_event
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
import random
import string

@tool("ScheduleInterview")
def schedule_interview(job_id: str, candidate_id: str, interview_date: str = None, number_of_rounds: int = 2) -> str:
    """Schedule an interview for a shortlisted candidate with automatic calendar availability checking"""
    
    def generate_time_slots(start_time_str, end_time_str, slot_duration_minutes=30):
        """Generate time slots within a time range"""
        if isinstance(start_time_str, str):
            start_dt = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        else:
            start_dt = start_time_str
            
        if isinstance(end_time_str, str):
            end_dt = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
        else:
            end_dt = end_time_str
            
        slots = []
        current = start_dt
        while current + timedelta(minutes=slot_duration_minutes) <= end_dt:
            slot_start = current
            slot_end = current + timedelta(minutes=slot_duration_minutes)
            slots.append((slot_start, slot_end))
            current += timedelta(minutes=slot_duration_minutes)
            
        return slots
    
    def get_busy_slots(email, start_time, end_time):
        """Get busy time slots for an email address"""
        try:
            # Using CalendarService to find busy slots
            service = CalendarService.get_calendar_service()
            
            # Format times for API
            if isinstance(start_time, datetime):
                start_time = start_time.isoformat()
            if isinstance(end_time, datetime):
                end_time = end_time.isoformat()
                
            events = CalendarService.get_events(
                time_min=datetime.fromisoformat(start_time.replace('Z', '+00:00')),
                time_max=datetime.fromisoformat(end_time.replace('Z', '+00:00')),
                max_results=100
            )
            
            busy_slots = []
            for event in events:
                start = event['start'].get('dateTime')
                end = event['end'].get('dateTime')
                
                if start and end:
                    busy_slots.append({
                        'start': start,
                        'end': end
                    })
                    
            print(f"📛 Found {len(busy_slots)} busy slots for {email}")
            return busy_slots
        except Exception as e:
            print(f"Error getting busy slots: {e}")
            return []
    
    def compute_bitmasks(busy_times_list, time_slots):
        """Compute availability bitmasks based on busy times"""
        bitmasks = []
        
        for busy_times in busy_times_list:
            bitmask = []
            for slot_start, slot_end in time_slots:
                # Slot times are already datetime objects
                
                is_busy = False
                for busy in busy_times:
                    # Parse busy times if they're strings
                    if isinstance(busy["start"], str):
                        busy_start = datetime.fromisoformat(busy["start"].replace('Z', '+00:00'))
                    else:
                        busy_start = busy["start"]
                        
                    if isinstance(busy["end"], str):
                        busy_end = datetime.fromisoformat(busy["end"].replace('Z', '+00:00'))
                    else:
                        busy_end = busy["end"]

                    # Check overlap
                    if slot_start < busy_end and slot_end > busy_start:
                        is_busy = True
                        break

                bitmask.append(0 if is_busy else 1)
            bitmasks.append(bitmask)
            
        return bitmasks
    
    def secure_bitmask_intersection(bitmasks):
        """Find common available slots using bitmask intersection"""
        length = len(bitmasks[0])
        intersection = [1] * length
        for mask in bitmasks:
            for i in range(length):
                intersection[i] = intersection[i] & mask[i]
        return intersection
    
    try:
            # Get candidate details
            candidate = CandidateService.get_candidate(candidate_id)
            if not candidate:
                return f"Candidate with ID {candidate_id} not found"
            
            # Get job details
            job = JobService.get_job_posting(job_id)
            if not job:
                return f"Job with ID {job_id} not found"
            
            # Parse or set default interview date
            try:
                if interview_date:
                    interview_date_dt = datetime.strptime(interview_date, "%Y-%m-%d")
                else:
                    # Default to tomorrow
                    interview_date_dt = datetime.now() + timedelta(days=1)
                    interview_date = interview_date_dt.strftime("%Y-%m-%d")
            except ValueError:
                return f"Invalid date format. Please use YYYY-MM-DD format."
            
            # Determine round types based on number_of_rounds
            round_types = []
            if number_of_rounds == 1:
                round_types = ["Technical"]
            elif number_of_rounds == 2:
                round_types = ["Technical", "HR"]
            elif number_of_rounds == 3:
                round_types = ["Technical", "Manager", "HR"]
            else:
                # For more rounds, add more technical rounds
                round_types = ["Technical"] * (number_of_rounds - 2) + ["Manager", "HR"]
            
            # Get interviewer assignments
            interviewer_assignments = InterviewCoreService.assign_interviewers(number_of_rounds)
            
            # Create feedback array with proper structure
            feedback_array = []
            
            # Collect interviewer emails
            interviewer_emails = []
            for i in range(number_of_rounds):
                round_type = round_types[i] if i < len(round_types) else "Technical"
                interviewer = interviewer_assignments[i] if i < len(interviewer_assignments) else {
                    "id": "", 
                    "name": f"{round_type} Interviewer",
                    "email": f"{round_type.lower()}_interviewer@example.com",
                    "department": {
                        "Technical": "Engineering", 
                        "Manager": "Management", 
                        "HR": "Human Resources"
                    }.get(round_type, "Engineering")
                }
                
                interviewer_emails.append(interviewer.get("email"))
            
            print(f"📧 Scheduling interview with interviewers: {interviewer_emails} and candidate: {candidate.email}")
            
            # Define interview window (8-hour window starting at 9AM)
            interview_date_dt = interview_date_dt.replace(hour=9, minute=0, second=0, microsecond=0)
            start_window = interview_date_dt
            end_window = interview_date_dt.replace(hour=17, minute=0, second=0, microsecond=0)
            
            # Generate 30-minute time slots for the day
            print(f"⏰ Generating time slots from {start_window} to {end_window}")
            time_slots = generate_time_slots(start_window, end_window, 30)
            
            # Get busy slots for all interviewers and candidate
            busy_times = []
            for email in interviewer_emails:
                busy = get_busy_slots(email, start_window, end_window)
                busy_times.append(busy)
                
            # Add candidate busy times if available
            candidate_busy = get_busy_slots(candidate.email, start_window, end_window)
            if candidate_busy:
                busy_times.append(candidate_busy)
            
            # Compute availability bitmasks
            interviewer_masks = compute_bitmasks(busy_times, time_slots)
            
            # Find common available slots
            common_slots = secure_bitmask_intersection(interviewer_masks)
            
            # Find first available slot
            chosen_slot_index = -1
            for i, is_available in enumerate(common_slots):
                if is_available == 1:
                    chosen_slot_index = i
                    break
            
            if chosen_slot_index >= 0:
                # We found an available slot
                chosen_slot = time_slots[chosen_slot_index]
                start_time, end_time = chosen_slot
                
                # Add 30 more minutes for a 1-hour interview
                if chosen_slot_index + 1 < len(common_slots) and common_slots[chosen_slot_index + 1] == 1:
                    end_time = time_slots[chosen_slot_index + 1][1]
                
                print(f"🎯 Found available slot: {start_time} - {end_time}")
            else:
                # No common slot found - use default time
                print("❌ No common available slot found. Using default time.")
                start_time = interview_date_dt.replace(hour=10, minute=0, second=0, microsecond=0)
                end_time = start_time + timedelta(hours=1)
            
            # For each round, schedule an interview with found time slots
            created_records = []
            
            for i in range(number_of_rounds):
                # Get round type
                round_type = round_types[i] if i < len(round_types) else "Technical"
                
                # Get department based on round type
                department = {
                    "Technical": "Engineering", 
                    "Manager": "Management", 
                    "HR": "Human Resources"
                }.get(round_type, "Engineering")
                
                # Assign interviewer
                interviewer = interviewer_assignments[i] if i < len(interviewer_assignments) else {
                    "id": "", 
                    "name": f"{round_type} Interviewer",
                    "email": f"{round_type.lower()}_interviewer@example.com",
                    "department": department
                }
                
                # Only schedule first round initially
                if i == 0:
                    # Calculate round time (use the found availability)
                    # Add days based on the round if we're scheduling multiple rounds on separate days
                    if i > 0:
                        # For rounds after the first, add days
                        start_time = start_time + timedelta(days=i)
                        end_time = end_time + timedelta(days=i)
                    
                    # Format dates in ISO format with timezone
                    start_iso = start_time.strftime("%Y-%m-%dT%H:%M:%S+05:30")
                    end_iso = end_time.strftime("%Y-%m-%dT%H:%M:%S+05:30")
                    
                    # Generate unique ID for the event
                    event_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=22))
                    
                    # Generate Google Meet link
                    meet_code = ''.join(random.choices(string.ascii_lowercase, k=3)) + '-' + \
                                ''.join(random.choices(string.ascii_lowercase, k=4)) + '-' + \
                                ''.join(random.choices(string.ascii_lowercase, k=3))
                    meet_link = f"https://meet.google.com/{meet_code}"
                    
                    # Create formatted time (e.g., "10AM")
                    hour_12 = start_time.hour if start_time.hour <= 12 else start_time.hour - 12
                    am_pm = 'AM' if start_time.hour < 12 else 'PM'
                    formatted_time = f"{hour_12}{am_pm}"
                    
                    # Create event summary and description
                    summary = f"Interview: {candidate.name} with {interviewer.get('name')} - Round {i+1} ({round_type})"
                    
                    # Safely access job attributes - convert Pydantic model to dict if needed
                    job_role_name = job.job_role_name if hasattr(job, 'job_role_name') else 'Unknown Position'
                    
                    description = f"""
                    Interview for {candidate.name} ({candidate.email})
                    Job: {job_role_name}
                    Round: {i+1} of {number_of_rounds} - {round_type} Round
                    Interviewer: {interviewer.get('name')} ({interviewer.get('email')})
                    
                    Please join using the Google Meet link at the scheduled time.
                    """
                    
                    # Create calendar event using our enhanced CalendarService
                    try:
                        # Generate a unique Meet code
                        meet_code = ''.join(random.choices(string.ascii_lowercase, k=3)) + '-' + \
                                ''.join(random.choices(string.ascii_lowercase, k=4)) + '-' + \
                                ''.join(random.choices(string.ascii_lowercase, k=3))
                        meet_link = f"https://meet.google.com/{meet_code}"
                        
                        # Format start and end times
                        start_iso = start_time.isoformat()
                        end_iso = end_time.isoformat()
                        
                        # Create event
                        print(f"🗓️ Creating calendar event from {start_iso} to {end_iso}")
                        
                        calendar_event = create_calendar_event(
                            summary=summary,
                            description=description,
                            start_time=start_iso,
                            end_time=end_iso,
                            attendees=[
                                {"email": interviewer.get('email')},
                                {"email": candidate.email}
                            ]
                        )
                        
                        if calendar_event:
                            event_id = calendar_event.get('id', event_id)
                            meet_link = calendar_event.get('hangoutLink', calendar_event.get('manual_meet_link', meet_link))
                            html_link = calendar_event.get('htmlLink', f"https://www.google.com/calendar/event?eid={event_id}")
                        
                        # Send email notification with proper parameters
                        additional_note = (f"Interview Round {i+1} ({round_type})\n" 
                                          f"Scheduled for {start_time.strftime('%A, %B %d, %Y')} at {formatted_time}")
                        
                        send_interview_notification(
                            recipient_email=candidate.email,
                            start_time=start_iso,
                            end_time=end_iso,
                            meet_link=meet_link,
                            event_id=event_id,
                            interviewer_name=interviewer.get('name'),
                            candidate_name=candidate.name,
                            job_title=job.job_role_name if hasattr(job, 'job_role_name') else 'Unknown Position',
                            additional_note=additional_note,
                            interviewer_email=interviewer.get('email')
                        )
                    except Exception as calendar_error:
                        print(f"Error creating calendar event: {calendar_error}")
                        # Continue with mock data
                else:
                    # For future rounds, we'll only create placeholder data
                    event_id = ''
                    meet_link = ''
                    formatted_time = ''
                    start_iso = ''
                    end_iso = ''
                    html_link = ''
                
                # Create feedback object for this round
                feedback_object = {
                    "interviewer_id": interviewer.get("id", ""),
                    "interviewer_name": interviewer.get("name", f"{round_type} Interviewer {i+1}"),
                    "interviewer_email": interviewer.get("email", f"{round_type.lower()}_interviewer@example.com"),
                    "department": department,
                    "feedback": None,
                    "isSelectedForNextRound": None,
                    "rating_out_of_10": None,
                    "meet_link": meet_link,
                    "scheduled_time": formatted_time,
                    "round_type": round_type,
                    "round_number": i + 1,
                    "scheduled_event": {
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
                    } if event_id else {}
                }
                
                # Add to feedback array
                feedback_array.append(feedback_object)
            
            # Create interview candidate record
            interview_candidate = {
                "job_id": job_id,
                "candidate_id": candidate.id,
                "candidate_name": candidate.name,
                "candidate_email": candidate.email,
                "job_role": job.job_role_name,
                "no_of_interviews": number_of_rounds,
                "feedback": feedback_array,
                "completedRounds": 0,
                "nextRoundIndex": 0,
                "status": "scheduled",
                "last_updated": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat(),
                "current_round_scheduled": True
            }
            
            # Save to database
            doc_id = InterviewCoreService.create_interview_candidate(interview_candidate)
            
            # Add ID to the record
            interview_candidate["id"] = doc_id
            created_records.append(interview_candidate)
            
            result = f"Successfully scheduled interview for {candidate.name} for job {job.job_role_name}.\n\n"
            result += f"Interview ID: {doc_id}\n"
            result += f"First round scheduled on: {feedback_array[0]['scheduled_event'].get('start', {}).get('dateTime', 'Not scheduled')}\n"
            result += f"Google Meet link: {feedback_array[0]['meet_link']}\n"
            result += f"Total rounds: {number_of_rounds}\n"
            
            return result
    except Exception as e:
        return f"Error scheduling interview: {str(e)}"

@tool("GetShortlistedCandidates")
def get_shortlisted_candidates(job_id: str) -> str:
    """Get shortlisted candidates for a job"""
    try:
        # First try to get from specialized collection
        shortlisted = FirestoreDB.execute_query("shortlisted_candidates", "job_id", "==", job_id)
        
        if not shortlisted:
            # Fall back to sorting candidates by AI fit score
            candidates = CandidateService.get_candidates_by_job_id(job_id)
            if not candidates:
                return f"No candidates found for job {job_id}"
            
            # Sort by AI fit score
            try:
                sorted_candidates = sorted(
                    candidates,
                    key=lambda c: int(c.ai_fit_score),
                    reverse=True
                )
                # Take top 2 by default
                shortlisted = sorted_candidates[:min(2, len(sorted_candidates))]
            except (ValueError, TypeError) as e:
                return f"Error sorting candidates: {str(e)}"
        
        result = f"Shortlisted candidates for job {job_id}:\n\n"
        
        for i, candidate in enumerate(shortlisted):
            # Format candidate info (handle both dict and object formats)
            name = candidate.get('name', candidate.name if hasattr(candidate, 'name') else 'Unknown')
            email = candidate.get('email', candidate.email if hasattr(candidate, 'email') else 'Unknown')
            candidate_id = candidate.get('candidate_id', candidate.id if hasattr(candidate, 'id') else 'Unknown')
            
            result += f"Candidate {i+1}:\n"
            result += f"ID: {candidate_id}\n"
            result += f"Name: {name}\n"
            result += f"Email: {email}\n\n"
        
        return result
    except Exception as e:
        return f"Error getting shortlisted candidates: {str(e)}"


#-----------------------
# Agent Definitions
#-----------------------

# Shortlisting Agent
shortlisting_agent = Agent(
    role="Candidate Shortlisting Specialist",
    goal="Select the best candidates for interviews based on their qualifications and fit scores",
    backstory="""You are an expert in talent acquisition with years of experience identifying the most promising candidates for technical roles. 
    
    IMPORTANT GUIDELINES:
    1. Only process the exact job role or ID provided by the user
    2. Do NOT attempt to use empty role names or make up role names
    3. If no jobs are found with the exact name provided, clearly report this to the user
    4. When using ShortlistCandidatesByRole, you MUST specify a valid existing role name
    5. You are NOT to try multiple different job roles when the specified one isn't found
    
    Your job is to analyze candidate profiles and select those who best match the requirements for the EXACT job specified.""",
    verbose=True,
    allow_delegation=True,
    llm=llm,
    tools=[
        find_job_by_role,
        get_candidates,
        shortlist_candidates,
        shortlist_candidates_by_role,
        get_job_details
    ]
)

# Scheduling Agent
scheduling_agent = Agent(
    role="Interview Scheduling Specialist",
    goal="Efficiently schedule interviews for shortlisted candidates across multiple rounds",
    backstory="You are an expert in coordinating complex interview schedules, making sure that candidates and interviewers are properly matched and have all the information they need. Your scheduling optimizes the interview process.",
    verbose=True,
    allow_delegation=True,
    llm=llm,
    tools=[
        get_shortlisted_candidates,
        schedule_interview,
        get_job_details
    ]
)

#-----------------------
# Crew Definition and Functions
#-----------------------
def create_shortlisting_crew(job_id: str, number_of_candidates: int = 2):
    """Create a crew for shortlisting candidates"""
    
    # Create shortlisting task
    shortlisting_task = Task(
        description=f"""
        Shortlist the top {number_of_candidates} candidates for job ID: {job_id}.
        
        Steps:
        1. Get the job details to understand the requirements
        2. Get all candidates for this job
        3. Shortlist the top {number_of_candidates} candidates based on AI fit scores
        
        IMPORTANT: Process only the exact job ID or role name provided. If no candidates are found for this exact job, return a message indicating no candidates were found. Do NOT attempt to query multiple job roles.
        
        Return the shortlisted candidates with their details.
        """,
        expected_output=f"List of top {number_of_candidates} candidates for job ID: {job_id}, sorted by AI fit score",
        agent=shortlisting_agent
    )
    
    # Create the crew
    crew = Crew(
        agents=[shortlisting_agent],
        tasks=[shortlisting_task],
        verbose=True,
        process=Process.sequential
    )
    
    return crew

def create_scheduling_crew(job_id: str, interview_date: str = None, number_of_rounds: int = 2):
    """Create a crew for scheduling interviews"""
    
    # If no interview date provided, use tomorrow's date
    if not interview_date:
        interview_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Create scheduling task
    scheduling_task = Task(
        description=f"""
        Schedule interviews for all shortlisted candidates for job ID: {job_id}.
        
        Interview details:
        - Date: {interview_date}
        - Number of rounds: {number_of_rounds}
        
        Steps:
        1. Get the shortlisted candidates for this job
        2. For each candidate, schedule an interview with {number_of_rounds} rounds
        3. Ensure calendar events are created and email notifications are sent
        
        Return the scheduling details for each candidate.
        """,
        expected_output=f"Interview schedules for all shortlisted candidates for job ID: {job_id}",
        agent=scheduling_agent
    )
    
    # Create the crew
    crew = Crew(
        agents=[scheduling_agent],
        tasks=[scheduling_task],
        verbose=True,
        process=Process.sequential
    )
    
    return crew

def create_end_to_end_crew(job_id: str, number_of_candidates: int = 2, interview_date: str = None, number_of_rounds: int = 2):
    """Create a crew for the entire process from shortlisting to scheduling"""
    
    # If no interview date provided, use tomorrow's date
    if not interview_date:
        interview_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Create shortlisting task
    shortlisting_task = Task(
        description=f"""
        Shortlist the top {number_of_candidates} candidates for job ID: {job_id}.
        
        Steps:
        1. Get the job details to understand the requirements
        2. Get all candidates for this job
        3. Shortlist the top {number_of_candidates} candidates based on AI fit scores
        
        IMPORTANT: Process only the exact job ID provided. If no candidates are found for this exact job, return a message indicating no candidates were found. Do NOT attempt to query multiple job IDs or role names.
        
        Return the shortlisted candidates with their details.
        """,
        expected_output=f"List of top {number_of_candidates} candidates for job ID: {job_id}, sorted by AI fit score",
        agent=shortlisting_agent
    )
    
    # Create scheduling task
    scheduling_task = Task(
        description=f"""
        Schedule interviews for all shortlisted candidates for job ID: {job_id}.
        
        Interview details:
        - Date: {interview_date}
        - Number of rounds: {number_of_rounds}
        
        Steps:
        1. Get the shortlisted candidates for this job
        2. For each candidate, schedule an interview with {number_of_rounds} rounds
        3. Ensure calendar events are created and email notifications are sent
        
        Return the scheduling details for each candidate.
        """,
        expected_output=f"Interview schedules for all shortlisted candidates for job ID: {job_id}",
        agent=scheduling_agent,
        context=[shortlisting_task]  # Pass the shortlisting task as context
    )
    
    # Create the crew
    crew = Crew(
        agents=[shortlisting_agent, scheduling_agent],
        tasks=[shortlisting_task, scheduling_task],
        verbose=True,
        process=Process.sequential
    )
    
    return crew

# Functions to run the specific processes
def run_shortlisting_process(job_role_name: str, number_of_candidates: int = 2):
    """Run the shortlisting process for a job
    
    Args:
        job_role_name: The job role name to search for
        number_of_candidates: Number of candidates to shortlist
        
    Returns:
        Result from the crew execution
    """
    # Validate job_role_name
    if not job_role_name or job_role_name.strip() == "":
        return "Error: job_role_name must be provided"
    
    # Verify the job exists
    print(f"Looking up job with role name: '{job_role_name}'")
    job = JobService.get_job_posting_by_role_name(job_role_name)
    if not job:
        return f"Error: No job found with role name '{job_role_name}'"
    
    # Get the job_id for internal reference 
    job_id = job.id
    print(f"Found job with ID {job_id} for role: '{job_role_name}'")
    
    # Create crew with the job_role_name
    print(f"Creating shortlisting crew for job role: '{job_role_name}'")
    
    # Modify the crew creation to use job_role_name
    task = Task(
        description=f"""
        Shortlist the top {number_of_candidates} candidates for job role: '{job_role_name}'.
        
        Steps:
        1. First find the job by its role name using FindJobByRole tool
        2. Get all candidates for this job using GetCandidates with the job ID you found
        3. Shortlist the top {number_of_candidates} candidates based on AI fit scores using ShortlistCandidatesByRole
        
        IMPORTANT: Process only the exact job role provided ({job_role_name}). Do NOT attempt to query multiple job roles.
        
        Return the shortlisted candidates with their details.
        """,
        expected_output=f"List of top {number_of_candidates} candidates for job role: '{job_role_name}', sorted by AI fit score",
        agent=shortlisting_agent
    )
    
    crew = Crew(
        agents=[shortlisting_agent],
        tasks=[task],
        verbose=True,
        process=Process.sequential
    )
    
    result = crew.kickoff()
    return result

def run_scheduling_process(job_role_name: str, interview_date: str = None, number_of_rounds: int = 2):
    """Run the scheduling process for shortlisted candidates
    
    Args:
        job_role_name: The job role name to search for
        interview_date: Optional date for the interview (YYYY-MM-DD format)
        number_of_rounds: Number of interview rounds to schedule
        
    Returns:
        Result from the crew execution
    """
    # Validate job_role_name
    if not job_role_name or job_role_name.strip() == "":
        return "Error: job_role_name must be provided"
    
    # Verify the job exists
    print(f"Looking up job with role name: '{job_role_name}'")
    job = JobService.get_job_posting_by_role_name(job_role_name)
    if not job:
        return f"Error: No job found with role name '{job_role_name}'"
    
    # Get the job_id for internal reference 
    job_id = job.id
    print(f"Found job with ID {job_id} for role: '{job_role_name}'")
    
    # Create task specifically for job_role_name
    task = Task(
        description=f"""
        Schedule interviews for all shortlisted candidates for job role: '{job_role_name}'.
        
        Interview details:
        - Date: {interview_date or (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")}
        - Number of rounds: {number_of_rounds}
        
        Steps:
        1. Find the job by its role name ({job_role_name})
        2. Get all shortlisted candidates for this job
        3. For each candidate, schedule an interview with {number_of_rounds} rounds
        
        IMPORTANT: Only process the exact job role name provided. Do not attempt other roles.
        
        Return the scheduling details for each candidate.
        """,
        expected_output=f"Interview schedules for all shortlisted candidates for job role: '{job_role_name}'",
        agent=scheduling_agent
    )
    
    crew = Crew(
        agents=[scheduling_agent],
        tasks=[task],
        verbose=True,
        process=Process.sequential
    )
    
    result = crew.kickoff()
    return result

def run_end_to_end_process(job_role_name: str, number_of_candidates: int = 2, interview_date: str = None, number_of_rounds: int = 2):
    """Run the entire process from shortlisting to scheduling
    
    Args:
        job_role_name: The job role name to search for
        number_of_candidates: Number of candidates to shortlist
        interview_date: Optional date for the interview (YYYY-MM-DD format)
        number_of_rounds: Number of interview rounds to schedule
        
    Returns:
        Result from the crew execution
    """
    # Validate job_role_name
    if not job_role_name or job_role_name.strip() == "":
        return "Error: job_role_name must be provided"
    
    # Verify the job exists
    print(f"Looking up job with role name: '{job_role_name}'")
    job = JobService.get_job_posting_by_role_name(job_role_name)
    if not job:
        return f"Error: No job found with role name '{job_role_name}'"
    
    # Get the job_id for internal reference 
    job_id = job.id
    print(f"Found job with ID {job_id} for role: '{job_role_name}'")
    
    # Run shortlisting first
    print(f"Starting shortlisting process for job role: '{job_role_name}'")
    shortlisting_result = run_shortlisting_process(job_role_name, number_of_candidates)
    
    # Then run scheduling
    print(f"Starting scheduling process for job role: '{job_role_name}'")
    scheduling_result = run_scheduling_process(job_role_name, interview_date, number_of_rounds)
    
    # Combine results
    result = f"END-TO-END PROCESS COMPLETE FOR JOB ROLE: '{job_role_name}'\n\n"
    result += f"SHORTLISTING RESULTS:\n{shortlisting_result}\n\n"
    result += f"SCHEDULING RESULTS:\n{scheduling_result}\n"
    
    return result
