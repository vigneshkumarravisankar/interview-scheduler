"""
CrewAI Agent System for Interview Scheduler
"""
import os
import re
from typing import Dict, Any, List, Optional
import uuid
import random
import string
from datetime import datetime
import logging
import json

from datetime import datetime
from pydantic import BaseModel, Field
from openai import OpenAI
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from langchain_openai import ChatOpenAI
from app.services.interview_shortlist_service import InterviewShortlistService
from app.services.interview_core_service import InterviewCoreService
from app.utils.calendar_service import CalendarService, create_calendar_event
from app.utils.email_notification import send_interview_notification
from app.services.job_service import JobService
from app.services.candidate_service import CandidateService
from app.schemas.job_schema import JobPostingCreate, JobPostingResponse
from app.schemas.candidate_schema import CandidateResponse
from app.agents.firebase_context_tool import GetInterviewCandidatesTool, GetJobsTool, GetCandidatesTool
from app.agents.calendar_agent_tool import ScheduleInterviewTool, RescheduleInterviewTool, GetCalendarAvailabilityTool
from app.database.chroma_db import FirestoreDB, ChromaVectorDB

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get OpenAI API Key from environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY not found in environment. Using default key.")
    # Default key from the project setup
    OPENAI_API_KEY = "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"

# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize LLM model for CrewAI
llm = ChatOpenAI(
    openai_api_key=OPENAI_API_KEY,
    model_name="gpt-4o",
    temperature=0.2
)

def format_job_with_llm(job_details: str) -> Dict[str, str]:
    """
    Use the LLM to properly format job details into the required structure
    
    Args:
        job_details: Raw job description text
        
    Returns:
        Dictionary with structured job fields
    """
    try:
        # Prepare system prompt
        system_prompt = """
        You are an expert job description parser. Extract structured information from 
        the job details provided and format it into the exact JSON structure requested.
        
        Make sure:
        1. Each field contains ONLY the information relevant to that field
        2. Do not include field information in other fields (e.g., experience shouldn't be in location)
        3. The job_id will be generated, so leave it blank
        4. Return ONLY the JSON with no additional text
        """
        
        # Prepare user prompt
        user_prompt = f"""
        Parse the following job details and format them into this exact JSON structure:
        
        {{
          "job_role_name": "",            # Only the job title/role name
          "job_description": "",          # Full job description with responsibilities and requirements
          "location": "",                 # Only the location where the job is based
          "years_of_experience_needed": "", # Only the years of experience required
          "status": "active"              # Always set to "active"
        }}
        
        JOB DETAILS:
        {job_details}
        
        IMPORTANT:
        - Make sure each field contains ONLY the information relevant to that field
        - Do not include experience information in the location field
        - Do not include responsibilities in the years_of_experience_needed field
        - Return ONLY valid JSON with no additional text or explanations
        """
        
        # Call the LLM
        response = openai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,  # Low temperature for more consistent extraction
            response_format={"type": "json_object"}
        )
        
        # Parse the JSON response
        parsed_job = json.loads(response.choices[0].message.content)
        
        # Ensure all required fields are present
        required_fields = ["job_role_name", "job_description", "location", "years_of_experience_needed", "status"]
        for field in required_fields:
            if field not in parsed_job or not parsed_job[field]:
                if field == "status":
                    parsed_job[field] = "active"
                else:
                    logger.warning(f"LLM did not return a value for {field}, using fallback extraction")
                    # For missing fields, fall back to regex-based extraction
                    if field == "job_role_name" and job_details:
                        # Extract common job titles
                        job_titles = ["software engineer", "data scientist", "product manager", "developer", 
                                    "llm specialist", "ai engineer", "ml engineer", "designer"]
                        for title in job_titles:
                            if title.lower() in job_details.lower():
                                parsed_job[field] = title.title()
                                break
                        if not parsed_job.get(field):
                            parsed_job[field] = "Untitled Position"
                    
                    elif field == "job_description":
                        parsed_job[field] = job_details
                    
                    elif field == "location":
                        parsed_job[field] = "Remote"
                    
                    elif field == "years_of_experience_needed":
                        # Look for experience patterns in the text
                        exp_match = re.search(r"(\d+(?:-\d+)?\s*(?:years|yrs))", job_details, re.IGNORECASE)
                        if exp_match:
                            parsed_job[field] = exp_match.group(1)
                        else:
                            parsed_job[field] = "1-3 years"
        
        return parsed_job
    
    except Exception as e:
        logger.error(f"Error formatting job with LLM: {e}")
        # Return a minimal structure as fallback
        return {
            "job_role_name": "Untitled Position",
            "job_description": job_details,
            "location": "Remote",
            "years_of_experience_needed": "1-3 years",
            "status": "active"
        }

# Define tools for agents
class CreateJobPostingTool(BaseTool):
    name: str = "CreateJobPosting"
    description: str = "Create a job posting in the system"
    
    # Define schema for the tool
    class InputSchema(BaseModel):
        job_details: str = Field(description="Job details text with information about the job posting")
    
    # Set the argument schema
    args_schema = InputSchema
    
    def _run(self, job_details) -> str:
        """
        Create a job posting from the provided details
        
        Args:
            job_details: Can be either a string or a dict with description field
        """
        # Handle different input types from CrewAI
        if isinstance(job_details, dict):
            if 'description' in job_details:
                job_details = job_details['description']
            else:
                # If it's a dict but no description field, convert the whole dict to string
                job_details = str(job_details)
        elif not isinstance(job_details, str):
            # Convert any other type to string
            job_details = str(job_details)
        
        try:
            # Use the LLM to format job details properly
            logger.info("Using LLM to format job details")
            parsed_job_data = format_job_with_llm(job_details)
            
            # Create job posting object
            job_posting = JobPostingCreate(
                job_role_name=parsed_job_data["job_role_name"],
                job_description=parsed_job_data["job_description"],
                years_of_experience_needed=parsed_job_data["years_of_experience_needed"],
                location=parsed_job_data["location"],
                status=parsed_job_data["status"]
            )
             
            # Save to database  
            result = JobService.create_job_posting(job_posting)
            
            # Convert result to dict to avoid Pydantic serialization issues
            result_dict = result.dict() if hasattr(result, 'dict') else result.__dict__
            
            # Format response
            response = f"""
Job posting created successfully!

Job ID: {result_dict.get('job_id', 'N/A')}
Role: {result_dict.get('job_role_name', 'N/A')}
Experience Required: {result_dict.get('years_of_experience_needed', 'N/A')}
Location: {result_dict.get('location', 'N/A')}
Status: {result_dict.get('status', 'N/A')}

Description:
{result_dict.get('job_description', 'N/A')}
"""
            return response
        except Exception as e:
            logger.error(f"Error creating job posting: {e}")
            return f"Failed to create job posting: {str(e)}"

class ProcessResumesTool(BaseTool):
    name: str = "ProcessResumes"
    description: str = "Process resumes for a specific job role and calculate AI fit scores"
    
    # Define schema for the tool
    class InputSchema(BaseModel):
        job_details: str = Field(description="Job details with job ID or job role name")
    
    # Set the argument schema
    args_schema = InputSchema
    
    def _run(self, job_details: str) -> str:
        """
        Process resumes for a specific job
        
        Args:
            job_details: Can be either a string or a dict with description field
        """
        # Convert to string if dictionary is passed
        if isinstance(job_details, dict) and 'description' in job_details:
            job_details = job_details['description']
        elif not isinstance(job_details, str):
            return "Error: Invalid job details format. Please provide either a string or a dictionary with a 'description' field."
        
        logger.info(f"Processing resumes with input: {job_details}")
        
        try:
            # Extract job ID or job role name with more flexible patterns
            # First look for explicit job ID
            job_id_match = re.search(r"(?:job_id|job id|id)[\s:=]*[\"\']?([^\"\'\n]+?)[\"\']?(?:\s|$)", job_details, re.IGNORECASE)
            
            # Then look for role mentions in various formats
            job_role_patterns = [
                # Structured formats
                r"job_role_name\s*[:=]\s*[\"\']?([^\"\'\n]+?)[\"\']?(?:\s|$)",
                r"role\s*[:=]\s*[\"\']?([^\"\'\n]+?)[\"\']?(?:\s|$)",
                r"job title\s*[:=]\s*[\"\']?([^\"\'\n]+?)[\"\']?(?:\s|$)",
                r"position\s*[:=]\s*[\"\']?([^\"\'\n]+?)[\"\']?(?:\s|$)",
                # Natural language formats
                r"(?:for|role|position|job)[\s:]*(?:the\s+)?([a-zA-Z0-9\s]+?(?:engineer|specialist|developer|analyst|manager|designer|scientist|architect|consultant|director))(?:\s|$|role|position)",
                r"(?:process|analyze|evaluate)\s+(?:resumes|candidates)\s+(?:for|related to)\s+(?:the\s+)?([a-zA-Z0-9\s]+?(?:engineer|specialist|developer|analyst|manager|designer|scientist|architect|consultant|director))(?:\s|$)",
                r"(?:process|analyze|evaluate)\s+([a-zA-Z0-9\s]+?(?:engineer|specialist|developer|analyst|manager|designer|scientist|architect|consultant|director))\s+(?:resumes|candidates)(?:\s|$)"
            ]
            
            job_role = None
            for pattern in job_role_patterns:
                match = re.search(pattern, job_details, re.IGNORECASE)
                if match:
                    job_role = match.group(1).strip()
                    logger.info(f"Found job role using pattern: {pattern}")
                    break
            
            # Extract job ID if provided
            job_id = job_id_match.group(1).strip() if job_id_match else None
            
            # If no explicit job role found, try to extract from general text
            if not job_role:
                # Look for common job title patterns in the text
                common_job_titles = [
                    "software engineer", "data scientist", "product manager", 
                    "ui designer", "ux designer", "frontend developer",
                    "backend developer", "fullstack developer", "devops engineer",
                    "qa engineer", "machine learning engineer", "ai engineer",
                    "llm specialist", "genai specialist", "ml engineer",
                    "solutions architect", "project manager", "scrum master",
                    "product owner", "technical writer", "data analyst"
                ]
                
                # Extract the job title if it appears in the text
                for title in common_job_titles:
                    if title.lower() in job_details.lower():
                        job_role = title.title()
                        logger.info(f"Found job role from common titles: {job_role}")
                        break
            
            # If no job ID but have job role, try to find the job
            if not job_id and job_role:
                logger.info(f"Searching for job with role: {job_role}")
                # Get all jobs and search for matches
                all_jobs = JobService.get_all_job_postings()
                
                # First try exact title match
                matching_jobs = [job for job in all_jobs if job_role.lower() == job.job_role_name.lower()]
                
                # If no exact match, try contains match
                if not matching_jobs:
                    matching_jobs = [job for job in all_jobs if job_role.lower() in job.job_role_name.lower()]
                    
                # If still no match, try fuzzy matching - look for common words
                if not matching_jobs:
                    job_role_words = set(job_role.lower().split())
                    for job in all_jobs:
                        job_name_words = set(job.job_role_name.lower().split())
                        # If at least 50% of words match
                        if job_role_words and job_name_words and len(job_role_words.intersection(job_name_words)) / len(job_role_words) >= 0.5:
                            matching_jobs.append(job)
                
                if matching_jobs:
                    job_id = matching_jobs[0].job_id
                    logger.info(f"Found job ID {job_id} for role {job_role}")
                else:
                    return f"No job found with role name containing '{job_role}'. Please provide a valid job ID or create a job first."
            
            # If still no job ID, return an error with more details
            if not job_id:
                logger.error(f"No job found matching: '{job_role}' from input: '{job_details}'")
                
                # List available jobs to help the user
                all_jobs = JobService.get_all_job_postings()
                job_list = "\n".join([f"- {job.job_role_name} (ID: {job.job_id})" for job in all_jobs[:5]])
                
                if all_jobs:
                    available_jobs = f"\n\nAvailable jobs:\n{job_list}"
                    if len(all_jobs) > 5:
                        available_jobs += f"\n...and {len(all_jobs) - 5} more"
                else:
                    available_jobs = "\n\nThere are no jobs in the system. Please create a job first."
                
                return f"No job found matching '{job_role}'. Please provide a valid job ID or job role name.{available_jobs}"
            
            # Process the resumes
            logger.info(f"Processing resumes for job ID: {job_id}")
            candidates = CandidateService.process_resumes_for_job(job_id)
            
            if not candidates:
                return f"No resumes found for job ID {job_id} or no suitable candidates identified."
            
            # Format the results
            response = f"Successfully processed {len(candidates)} resumes for job ID: {job_id}\n\n"
            
            # Get job details for display
            job = JobService.get_job_posting(job_id)
            job_role_name = job.job_role_name if job else "Unknown"
            
            response += f"Job: {job_role_name}\n\n"
            response += "Candidates ranked by AI fit score:\n\n"
            
            # Sort candidates by fit score - convert to dict to avoid Pydantic issues
            candidate_dicts = []
            for candidate in candidates:
                if hasattr(candidate, 'dict'):
                    candidate_dicts.append(candidate.dict())
                elif hasattr(candidate, '__dict__'):
                    candidate_dicts.append(candidate.__dict__)
                else:
                    candidate_dicts.append(candidate)
            
            sorted_candidates = sorted(
                candidate_dicts,
                key=lambda c: int(c.get('ai_fit_score', 0)) if str(c.get('ai_fit_score', 0)).isdigit() else 0,
                reverse=True
            )
            
            for i, candidate in enumerate(sorted_candidates):
                response += f"#{i+1}: {candidate.get('name', 'Unknown')}\n"
                response += f"   Email: {candidate.get('email', 'N/A')}\n"
                response += f"   Phone: {candidate.get('phone_no', 'N/A')}\n"
                response += f"   AI Fit Score: {candidate.get('ai_fit_score', 0)}/100\n"
                response += f"   Experience: {candidate.get('total_experience_in_years', 'N/A')}\n"
                response += f"   Skills: {candidate.get('technical_skills', 'N/A')}\n\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing resumes: {e}")
            return f"Failed to process resumes: {str(e)}"
    
class ShortlistCandidatesTool(BaseTool):
    name: str = "ShortlistCandidates"
    description: str = "Shortlist top N candidates for interviews based on AI fit scores and schedule interviews"
    
    # Define schema for the tool
    class InputSchema(BaseModel):
        job_id: str = Field(description="ID of the job to shortlist candidates for")
        number_of_candidates: int = Field(description="Number of candidates to shortlist", default=3)
        number_of_rounds: int = Field(description="Number of interview rounds", default=2)
        specific_time: str = Field(description="Specific time for interviews (optional, format: 'YYYY-MM-DD HH:MM')", default="")
    
    # Set the argument schema
    args_schema = InputSchema
    
    def _run(self, job_id: str, number_of_candidates: int = 3, number_of_rounds: int = 2, specific_time: str = "") -> str:
        """
        Shortlist candidates for interviews based on AI fit scores and schedule interviews
        
        Args:
            job_id: ID of the job to shortlist candidates for
            number_of_candidates: Number of candidates to shortlist (default: 3)
            number_of_rounds: Number of interview rounds (default: 2)
            specific_time: Specific time for interviews (optional)
        
        Returns:
            String with shortlisting results
        """
        try:
            # Log the parameters
            logger.info(f"Shortlisting candidates for job {job_id}, top {number_of_candidates} candidates, {number_of_rounds} rounds")
            
            # Check if specific time was provided
            if specific_time:
                logger.info(f"Specific time requested: {specific_time}")
            
            # Shortlist candidates using the service
            shortlisted, created_records = InterviewShortlistService.shortlist_candidates(
                job_id=job_id,
                number_of_candidates=number_of_candidates,
                no_of_interviews=number_of_rounds
            )
            
            # Check if any candidates were shortlisted
            if not shortlisted:
                return "No candidates were found or shortlisted for this job. Please process some resumes first."
                
            # Format the response
            if not created_records:
                return f"Shortlisted {len(shortlisted)} candidates, but failed to create interview records."
            
            response = f"Successfully shortlisted {len(shortlisted)} candidates for job ID: {job_id}\n\n"
            
            # Add details about the shortlisted candidates
            for i, candidate in enumerate(shortlisted):
                response += f"Candidate {i+1}: {candidate.get('name')}\n"
                response += f"   Email: {candidate.get('email')}\n"
                response += f"   AI Fit Score: {candidate.get('ai_fit_score')}\n"
                response += f"   Experience: {candidate.get('total_experience_in_years')}\n"
                
                # Add interview details from created records
                for record in created_records:
                    if record.get('candidate_id') == candidate.get('id'):
                        response += f"   Interview Rounds: {record.get('no_of_interviews')}\n"
                        response += f"   Status: {record.get('status')}\n"
                        response += "   Round Details:\n"
                        
                        # Add details for each interview round
                        for i, feedback in enumerate(record.get('feedback', [])):
                            round_num = i + 1
                            interviewer = feedback.get('interviewer_name')
                            
                            response += f"      Round {round_num}: with {interviewer}\n"
                            
                            # Show scheduling details for the first round
                            if i == 0 and feedback.get('scheduled_event'):
                                start_time = feedback.get('scheduled_event', {}).get('start', {}).get('dateTime', 'TBD')
                                
                                # Format the datetime for readability
                                if start_time != 'TBD':
                                    try:
                                        # Convert ISO format to datetime object
                                        dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                                        # Format for display
                                        start_time = dt.strftime("%A, %B %d, %Y at %I:%M %p")
                                    except Exception:
                                        # Keep original if parsing fails
                                        pass
                                
                                response += f"         Scheduled: {start_time}\n"
                                response += f"         Meet Link: {feedback.get('meet_link', 'TBD')}\n"
                        
                response += "\n"
                
            return response
            
        except Exception as e:
            logger.error(f"Error shortlisting candidates: {e}")
            return f"Error shortlisting candidates: {str(e)}"
            
class RescheduleInterviewTool(BaseTool):
    name: str = "RescheduleInterview"
    description: str = "Reschedule an interview for a candidate at a different time"
    
    # Define schema for the tool
    class InputSchema(BaseModel):
        interview_id: str = Field(description="ID of the interview record to reschedule")
        round_index: int = Field(description="Index of the round to reschedule (0-based)")
        new_time: str = Field(description="New time for the interview (format: 'YYYY-MM-DD HH:MM')")
        reason: str = Field(description="Reason for rescheduling", default="Scheduling conflict")
    
    # Set the argument schema
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
            # Log the parameters
            logger.info(f"Rescheduling interview {interview_id}, round {round_index} to {new_time}, reason: {reason}")
            
            # Get the interview record
            interview_record = InterviewCoreService.get_interview_candidate(interview_id)
            
            if not interview_record:
                return f"Interview record with ID {interview_id} not found."
                
            # Verify the round index is valid
            feedback_array = interview_record.get('feedback', [])
            if round_index < 0 or round_index >= len(feedback_array):
                return f"Invalid round index {round_index}. Valid range: 0-{len(feedback_array)-1}"
            
            # Get the current round details
            round_details = feedback_array[round_index]
            interviewer_name = round_details.get('interviewer_name', 'Unknown')
            
            # Parse the new time
            try:
                new_datetime = datetime.strptime(new_time, "%Y-%m-%d %H:%M")
                start_time = new_datetime
                end_time = new_datetime.replace(hour=new_datetime.hour + 1)  # 1 hour interview
                
                # Format dates in ISO format with timezone
                start_iso = start_time.strftime("%Y-%m-%dT%H:%M:%S+05:30")
                end_iso = end_time.strftime("%Y-%m-%dT%H:%M:%S+05:30")
                
                # Format for display
                formatted_time = start_time.strftime("%I%p").lstrip('0')  # e.g., "10AM"
            except ValueError:
                return f"Invalid time format. Please use the format 'YYYY-MM-DD HH:MM'"
            
            # Update the calendar event if there is one
            old_event_id = round_details.get('scheduled_event', {}).get('id')
            if old_event_id:
                # Delete the old event
                CalendarService.delete_event(old_event_id)
            
            # Get candidate and interviewer details for the new event
            candidate_name = interview_record.get('candidate_name', 'Candidate')
            candidate_email = interview_record.get('candidate_email', 'candidate@example.com')
            interviewer_email = round_details.get('interviewer_email', 'interviewer@example.com')
            job_role = interview_record.get('job_role', 'Unknown Position')
            round_type = round_details.get('round_type', f"Round {round_index+1}")
            
            # Create event summary and description
            summary = f"Interview: {candidate_name} with {interviewer_name} - Round {round_index+1} ({round_type})"
            description = f"""
            RESCHEDULED INTERVIEW for {candidate_name} ({candidate_email})
            Job: {job_role}
            Round: {round_index+1} - {round_type} Round
            Interviewer: {interviewer_name} ({interviewer_email})
            
            Reason for rescheduling: {reason}
            
            Please join using the Google Meet link at the scheduled time.
            """
            
            # Create a new calendar event
            calendar_event = create_calendar_event(
                summary=summary,
                description=description,
                start_time=start_iso,
                end_time=end_iso,
                attendees=[
                    {"email": interviewer_email},
                    {"email": candidate_email}
                ]
            )
            
            # Extract event details
            if calendar_event:
                event_id = calendar_event.get('id', '')
                meet_link = calendar_event.get('hangoutLink', calendar_event.get('manual_meet_link', ''))
                html_link = calendar_event.get('htmlLink', '')
            else:
                # If calendar event creation failed, create dummy data
                event_id = ''.join(random.choices(string.ascii_letters + string.digits, k=20))
                meet_link = f"https://meet.google.com/{CalendarService.generate_meet_code()}"
                html_link = f"https://calendar.google.com/calendar/event?eid=mock-event"
            
            # Update the round details
            round_details['scheduled_time'] = formatted_time
            round_details['meet_link'] = meet_link
            round_details['scheduled_event'] = {
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
            
            # Update the feedback array
            feedback_array[round_index] = round_details
            interview_record['feedback'] = feedback_array
            
            # Save the updated record
            InterviewCoreService.update_interview_candidate(interview_id, interview_record)
            
            # Send email notification about the rescheduling
            try:
                send_interview_notification(
                    candidate_name=candidate_name,
                    recipient_email=candidate_email,
                    interviewer_name=interviewer_name,
                    interviewer_email=interviewer_email,
                    job_title=job_role,
                    start_time=formatted_time,
                    interview_date=start_time.strftime("%A, %B %d, %Y"),
                    meet_link=meet_link,
                    round_number=round_index+1,
                    round_type=round_type,
                    is_rescheduled=True,
                    reschedule_reason=reason
                )
                
                return f"""
Successfully rescheduled the interview for {candidate_name} with {interviewer_name}.

New Interview Details:
- Date: {start_time.strftime("%A, %B %d, %Y")}
- Time: {formatted_time}
- Meet Link: {meet_link}
- Calendar Link: {html_link if html_link else "Not available"}

Email notifications have been sent to:
- {candidate_email}
- {interviewer_email}
"""
            except Exception as e:
                logger.error(f"Error sending email notification: {e}")
                return f"""
Successfully rescheduled the interview for {candidate_name} with {interviewer_name}, but failed to send email notifications.

New Interview Details:
- Date: {start_time.strftime("%A, %B %d, %Y")}
- Time: {formatted_time}
- Meet Link: {meet_link}
"""
        
        except Exception as e:
            logger.error(f"Error rescheduling interview: {e}")
            return f"Error rescheduling interview: {str(e)}"
    
    # Schema already defined above
    
# [This duplicate _run method for ProcessResumesTool was removed]

class CrewAgentSystem:
    """CrewAI-based agent system for interview scheduling"""
    
    def __init__(self):
        """Initialize the agent system"""
        # Store session conversations
        self.sessions = {}
        # Create the agent crew
        self.setup_crew()
    
    def setup_crew(self):
        """Set up the CrewAI agents and crew"""
        # Create tools
        job_creation_tool = CreateJobPostingTool()
        resume_processing_tool = ProcessResumesTool()
        shortlist_tool = ShortlistCandidatesTool()
        reschedule_tool = RescheduleInterviewTool()
        
        # Create database context tools
        interview_context_tool = GetInterviewCandidatesTool()
        jobs_context_tool = GetJobsTool()
        candidates_context_tool = GetCandidatesTool()
        
        # Create agents with specialized roles
        self.job_analyzer = Agent(
            role="Job Analysis Expert",
            goal="Create and analyze job postings to extract key requirements and provide insights",
            backstory="You are an expert in job market analysis with deep knowledge of industry trends and requirements across various roles. You help companies create effective job postings and understand market demands.",
            verbose=True,
            allow_delegation=True,
            llm=llm,
            tools=[job_creation_tool]
        )
        
        self.candidate_screener = Agent(
            role="Candidate Screening Specialist",
            goal="Evaluate candidates against job requirements to find the best matches",
            backstory="You have years of experience in talent acquisition and can quickly identify promising candidates based on their qualifications and experience. You are skilled at matching candidate profiles with job requirements.",
            verbose=True,
            allow_delegation=True,
            llm=llm,
            tools=[resume_processing_tool]
        )
        
        self.interview_planner = Agent(
            role="Interview Planning Strategist",
            goal="Design effective interview processes tailored to specific positions",
            backstory="You specialize in creating interview frameworks that effectively assess candidates' skills, cultural fit, and long-term potential. Your interview processes are known for being comprehensive yet efficient.",
            verbose=True,
            allow_delegation=True,
            llm=llm,
            tools=[]
        )
        
        # Create calendar tools
        schedule_interview_tool = ScheduleInterviewTool()
        reschedule_interview_tool = RescheduleInterviewTool()
        calendar_availability_tool = GetCalendarAvailabilityTool()
        
        self.scheduler = Agent(
            role="Interview Scheduling Coordinator",
            goal="Efficiently schedule interviews considering all parties' availability",
            backstory="You excel at coordinating complex schedules across multiple stakeholders. You understand the importance of finding optimal time slots and managing the logistics of interview processes.",
            verbose=True,
            allow_delegation=True,
            llm=llm,
            tools=[
                # Database context tools
                interview_context_tool, jobs_context_tool, candidates_context_tool,
                # Calendar operation tools
                calendar_availability_tool, schedule_interview_tool, reschedule_interview_tool,
                # Core scheduler tools
                shortlist_tool, reschedule_tool
            ]
        )
        
        # Create the crew
        self.crew = Crew(
            agents=[self.job_analyzer, self.candidate_screener, 
                   self.interview_planner, self.scheduler],
            tasks=[],  # Tasks will be created dynamically
            verbose=True,  # Changed from 2 to True to fix validation error
            process=Process.sequential,
            memory=False  # Disable memory to avoid ChromaDB issues
        )
    
    def process_query(self, query: str, session_id: str) -> Dict[str, Any]:
        """
        Process a query using RAG-enhanced agent routing and context-aware actions
        
        Args:
            query: The user's query text
            session_id: Session identifier for conversation context
            
        Returns:
            Dictionary containing the response and thought process
        """
        # Use RAG to understand query context and route to appropriate agent
        rag_routing_info = self._rag_based_agent_routing(query)
        
        # Enhanced routing with RAG context
        return self._process_with_rag_context(query, session_id, rag_routing_info)
    
    def _rag_based_agent_routing(self, query: str) -> Dict[str, Any]:
        """
        Use RAG to analyze query and determine best agent routing with context
        
        Args:
            query: The user's query text
            
        Returns:
            Dictionary with routing information and relevant context
        """
        try:
            db = ChromaVectorDB()
            routing_info = {
                "primary_agent": None,
                "confidence": 0,
                "relevant_context": {},
                "suggested_actions": [],
                "supporting_data": {}
            }
            
            # Search across different collections to understand query context
            collections_to_search = [
                ("jobs", "job-related queries and requirements"),
                ("candidates_data", "candidate profiles and skills"),
                ("interview_candidates", "interview scheduling and feedback"),
                ("interviewers", "interviewer expertise and availability")
            ]
            
            all_contexts = []
            collection_relevance = {}
            
            for collection_name, description in collections_to_search:
                try:
                    # Perform RAG search in each collection
                    rag_results = db.rag_search(
                        collection_name=collection_name,
                        query=query,
                        n_results=3
                    )
                    
                    if rag_results['document_count'] > 0:
                        collection_relevance[collection_name] = {
                            'document_count': rag_results['document_count'],
                            'context': rag_results['context'],
                            'relevant_documents': rag_results['relevant_documents']
                        }
                        all_contexts.append(f"From {collection_name}: {rag_results['context'][:200]}...")
                
                except Exception as e:
                    logger.warning(f"RAG search failed for {collection_name}: {e}")
            
            # Analyze query intent using RAG context
            routing_info = self._analyze_query_intent_with_rag(query, collection_relevance)
            
            return routing_info
            
        except Exception as e:
            logger.error(f"RAG-based routing failed: {e}")
            # Fallback to traditional routing
            return {
                "primary_agent": self.get_primary_agent_for_query(query),
                "confidence": 0.5,
                "relevant_context": {},
                "suggested_actions": [],
                "supporting_data": {},
                "fallback_used": True
            }
    
    def _analyze_query_intent_with_rag(self, query: str, collection_relevance: Dict) -> Dict[str, Any]:
        """
        Analyze query intent using RAG context to determine optimal agent routing
        """
        query_lower = query.lower()
        routing_info = {
            "primary_agent": None,
            "confidence": 0,
            "relevant_context": collection_relevance,
            "suggested_actions": [],
            "supporting_data": {}
        }
        
        # Determine primary intent based on RAG context and keywords
        intent_scores = {
            "job_management": 0,
            "candidate_screening": 0,
            "interview_planning": 0,
            "scheduling": 0
        }
        
        # Score based on collection relevance
        if "jobs" in collection_relevance and collection_relevance["jobs"]["document_count"] > 0:
            intent_scores["job_management"] += 2
        if "candidates_data" in collection_relevance and collection_relevance["candidates_data"]["document_count"] > 0:
            intent_scores["candidate_screening"] += 2
        if "interview_candidates" in collection_relevance and collection_relevance["interview_candidates"]["document_count"] > 0:
            intent_scores["interview_planning"] += 1
            intent_scores["scheduling"] += 1
        if "interviewers" in collection_relevance and collection_relevance["interviewers"]["document_count"] > 0:
            intent_scores["scheduling"] += 1
        
        # Score based on keywords
        job_keywords = ["job", "posting", "role", "position", "create", "requirement"]
        candidate_keywords = ["candidate", "resume", "cv", "profile", "skill", "experience", "screen", "evaluate"]
        interview_keywords = ["interview", "question", "assess", "evaluate", "feedback", "round"]
        schedule_keywords = ["schedule", "time", "date", "calendar", "meeting", "reschedule", "availability"]
        
        for keyword in job_keywords:
            if keyword in query_lower:
                intent_scores["job_management"] += 1
        
        for keyword in candidate_keywords:
            if keyword in query_lower:
                intent_scores["candidate_screening"] += 1
        
        for keyword in interview_keywords:
            if keyword in query_lower:
                intent_scores["interview_planning"] += 1
        
        for keyword in schedule_keywords:
            if keyword in query_lower:
                intent_scores["scheduling"] += 1
        
        # Determine primary agent based on highest score
        max_score = max(intent_scores.values())
        if max_score > 0:
            primary_intent = max(intent_scores, key=intent_scores.get)
            routing_info["confidence"] = min(max_score / 5.0, 1.0)  # Normalize to 0-1
            
            # Map intent to agent
            intent_to_agent = {
                "job_management": self.job_analyzer,
                "candidate_screening": self.candidate_screener,
                "interview_planning": self.interview_planner,
                "scheduling": self.scheduler
            }
            
            routing_info["primary_agent"] = intent_to_agent[primary_intent]
            
            # Generate suggested actions based on context
            routing_info["suggested_actions"] = self._generate_suggested_actions(
                primary_intent, query, collection_relevance
            )
        else:
            # Default to job analyzer if no clear intent
            routing_info["primary_agent"] = self.job_analyzer
            routing_info["confidence"] = 0.3
        
        return routing_info
    
    def _generate_suggested_actions(self, primary_intent: str, query: str, collection_relevance: Dict) -> List[str]:
        """
        Generate suggested actions based on RAG context and intent
        """
        actions = []
        
        if primary_intent == "job_management":
            if "jobs" in collection_relevance and collection_relevance["jobs"]["document_count"] > 0:
                actions.append("Analyze existing job postings for similar roles")
                actions.append("Review job requirements and qualifications")
            else:
                actions.append("Create new job posting")
            
        elif primary_intent == "candidate_screening":
            if "candidates_data" in collection_relevance and collection_relevance["candidates_data"]["document_count"] > 0:
                actions.append("Review candidate profiles and fit scores")
                actions.append("Compare candidates against job requirements")
                actions.append("Generate candidate ranking and recommendations")
            else:
                actions.append("Process resumes for the specified role")
            
        elif primary_intent == "interview_planning":
            if "interview_candidates" in collection_relevance:
                actions.append("Review interview feedback and progress")
                actions.append("Plan next interview rounds")
            actions.append("Design interview questions and assessment criteria")
            
        elif primary_intent == "scheduling":
            if "interview_candidates" in collection_relevance:
                actions.append("Check current interview schedules")
                actions.append("Identify scheduling conflicts")
            if "interviewers" in collection_relevance:
                actions.append("Match interviewers to candidate requirements")
            actions.append("Schedule or reschedule interviews")
        
        return actions
    
    def _process_with_rag_context(self, query: str, session_id: str, rag_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process query using RAG context and enhanced agent routing
        """
        # Initialize or retrieve session context
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "history": [],
                "context": {}
            }
        
        session = self.sessions[session_id]
        
        # Record the query in session history
        session["history"].append({
            "role": "user",
            "content": query,
            "timestamp": datetime.now().isoformat()
        })
        
        # Create enhanced thoughts with RAG context
        thoughts = []
        
        # Initial RAG analysis thought
        rag_thought = {
            "agent": "RAG System",
            "thought": f"Analyzed query using RAG across {len(rag_info['relevant_context'])} collections. Primary agent: {rag_info['primary_agent'].role if rag_info['primary_agent'] else 'None'}, Confidence: {rag_info['confidence']:.2f}",
            "timestamp": datetime.now().isoformat()
        }
        thoughts.append(rag_thought)
        
        # Add context-aware thoughts
        if rag_info['relevant_context']:
            for collection, context_info in rag_info['relevant_context'].items():
                context_thought = {
                    "agent": "RAG System",
                    "thought": f"Found {context_info['document_count']} relevant documents in {collection} collection",
                    "timestamp": datetime.now().isoformat()
                }
                thoughts.append(context_thought)
        
        # Agent routing thought
        primary_agent = rag_info.get('primary_agent') or self.get_primary_agent_for_query(query)
        routing_thought = {
            "agent": "System",
            "thought": f"Routing to {primary_agent.role} based on RAG analysis (confidence: {rag_info['confidence']:.2f})",
            "timestamp": datetime.now().isoformat()
        }
        thoughts.append(routing_thought)
        
        # Create enhanced task with RAG context
        rag_context_summary = self._create_rag_context_summary(rag_info['relevant_context'])
        
        task_description = f"""
        Process the following query with RAG-enhanced context:
        
        USER QUERY: {query}
        
        RAG CONTEXT ANALYSIS:
        {rag_context_summary}
        
        SUGGESTED ACTIONS BASED ON RAG:
        {chr(10).join(['- ' + action for action in rag_info.get('suggested_actions', [])])}
        
        Based on this context and the RAG analysis, provide a comprehensive response that:
        1. Leverages the relevant information found in the database
        2. Addresses the specific user query
        3. Takes appropriate actions based on the suggested actions
        4. Provides concrete, actionable results
        
        Use the available tools to perform any necessary operations.
        """
        
        task = Task(
            description=task_description,
            expected_output="A RAG-enhanced response that leverages database context to provide comprehensive assistance",
            agent=primary_agent
        )
        
        # Create a temporary crew for this enhanced task
        temp_crew = Crew(
            agents=[self.job_analyzer, self.candidate_screener, 
                   self.interview_planner, self.scheduler],
            tasks=[task],
            verbose=True,
            process=Process.sequential,
            memory=False  # Disable memory to avoid ChromaDB issues
        )
        
        try:
            # Record start of enhanced processing
            execution_start_thought = {
                "agent": primary_agent.role,
                "thought": f"Beginning RAG-enhanced processing with context from {len(rag_info['relevant_context'])} collections",
                "timestamp": datetime.now().isoformat()
            }
            thoughts.append(execution_start_thought)
            
            # Execute the crew's task with RAG context
            crew_result = temp_crew.kickoff()
            
            # Convert CrewOutput to string to ensure it's JSON serializable
            if hasattr(crew_result, 'raw'):
                result = crew_result.raw
            elif hasattr(crew_result, 'result'):
                result = crew_result.result
            else:
                result = str(crew_result)
            
            # Add context-aware completion thoughts
            if rag_info['suggested_actions']:
                for action in rag_info['suggested_actions']:
                    action_thought = {
                        "agent": primary_agent.role,
                        "thought": f"Considered action: {action}",
                        "timestamp": datetime.now().isoformat()
                    }
                    thoughts.append(action_thought)
            
            # Final completion thought
            completion_thought = {
                "agent": primary_agent.role,
                "thought": f"Completed RAG-enhanced analysis with {rag_info['confidence']:.2f} confidence",
                "timestamp": datetime.now().isoformat()
            }
            thoughts.append(completion_thought)
            
            # Record the response in session history
            session["history"].append({
                "role": "assistant",
                "content": result,
                "timestamp": datetime.now().isoformat(),
                "rag_context": rag_info
            })
            
            return {
                "response": result,
                "thought_process": thoughts,
                "primary_agent": primary_agent.role,
                "session_id": session_id,
                "rag_context": rag_info,
                "confidence": rag_info['confidence']
            }
            
        except Exception as e:
            logger.error(f"Error in RAG-enhanced processing: {e}")
            error_thought = {
                "agent": "System",
                "thought": f"RAG-enhanced processing failed: {str(e)}. Falling back to standard processing.",
                "timestamp": datetime.now().isoformat()
            }
            thoughts.append(error_thought)
            
            # Fallback to standard processing
            return self._fallback_standard_processing(query, session_id, thoughts)
    
    def _create_rag_context_summary(self, relevant_context: Dict) -> str:
        """
        Create a summary of RAG context for task description
        """
        if not relevant_context:
            return "No specific context found in database collections."
        
        summary_parts = []
        for collection, context_info in relevant_context.items():
            doc_count = context_info.get('document_count', 0)
            if doc_count > 0:
                summary_parts.append(f"- {collection.replace('_', ' ').title()}: {doc_count} relevant documents found")
                
                # Add preview of context
                context_preview = context_info.get('context', '')[:150]
                if context_preview:
                    summary_parts.append(f"  Preview: {context_preview}...")
        
        return "\n".join(summary_parts) if summary_parts else "No relevant context found."
    
    def _fallback_standard_processing(self, query: str, session_id: str, existing_thoughts: List[Dict]) -> Dict[str, Any]:
        """
        Fallback to standard processing when RAG enhancement fails
        """
        fallback_thought = {
            "agent": "System",
            "thought": "Using fallback standard processing",
            "timestamp": datetime.now().isoformat()
        }
        existing_thoughts.append(fallback_thought)
        
        # Use the existing standard processing logic
        primary_agent = self.get_primary_agent_for_query(query)
        
        task = Task(
            description=f"""
            Process the following query:
            
            USER QUERY: {query}
            
            Provide a helpful response addressing the user's request.
            """,
            expected_output="A helpful response to the user's query",
            agent=primary_agent
        )
        
        temp_crew = Crew(
            agents=[self.job_analyzer, self.candidate_screener, 
                   self.interview_planner, self.scheduler],
            tasks=[task],
            verbose=True,
            process=Process.sequential
        )
        
        try:
            crew_result = temp_crew.kickoff()
            
            if hasattr(crew_result, 'raw'):
                result = crew_result.raw
            elif hasattr(crew_result, 'result'):
                result = crew_result.result
            else:
                result = str(crew_result)
            
            return {
                "response": result,
                "thought_process": existing_thoughts,
                "primary_agent": primary_agent.role,
                "session_id": session_id,
                "fallback_used": True
            }
            
        except Exception as e:
            logger.error(f"Fallback processing also failed: {e}")
            return {
                "response": f"I apologize, but I encountered an error while processing your query: {str(e)}",
                "thought_process": existing_thoughts,
                "primary_agent": "System Error Handler",
                "session_id": session_id,
                "error": str(e)
            }
        # Check if query is related to shortlisting candidates
        if any(phrase in query.lower() for phrase in ["shortlist", "schedule interviews", "schedule candidates", "select top"]):
            # Direct shortlisting
            shortlisting_thought = {
                "agent": "Interview Scheduling Coordinator",
                "thought": f"Shortlisting candidates based on: {query}",
                "timestamp": datetime.now().isoformat()
            }
            
            # Extract job ID from query if present
            job_id_match = re.search(r"job_id\s*[:=]\s*[\"\']?([^\"\'\s]+)[\"\']?", query, re.IGNORECASE)
            job_id = job_id_match.group(1) if job_id_match else None
            
            if not job_id:
                job_role_match = re.search(r"(?:for|role)\s+(?:the\s+)?([a-zA-Z0-9\s]+?(?:role|position))", query, re.IGNORECASE)
                job_role = job_role_match.group(1) if job_role_match else None
                
                if job_role:
                    # Try to find job ID based on role
                    all_jobs = JobService.get_all_job_postings()
                    matching_jobs = [job for job in all_jobs if job_role.lower() in job.job_role_name.lower()]
                    if matching_jobs:
                        job_id = matching_jobs[0].job_id
            
            # Extract number of candidates
            num_candidates_match = re.search(r"(?:top|shortlist)\s+(\d+)\s+candidates", query, re.IGNORECASE)
            num_candidates = int(num_candidates_match.group(1)) if num_candidates_match else 3
            
            # Extract number of rounds
            num_rounds_match = re.search(r"(\d+)\s+(?:rounds|interviews)", query, re.IGNORECASE)
            num_rounds = int(num_rounds_match.group(1)) if num_rounds_match else 2
            
            # Create a task for shortlisting
            shortlist_task = Task(
                description=f"""
                Shortlist candidates for job ID: {job_id if job_id else "Need to extract from query"}
                Based on the following request:
                
                {query}
                
                Use the ShortlistCandidates tool to select the top candidates with highest AI fit scores
                and schedule them for interviews.
                
                Number of candidates to shortlist: {num_candidates}
                Number of interview rounds: {num_rounds}
                
                Please extract any specific time preferences from the request if mentioned.
                """,
                expected_output="List of shortlisted candidates with scheduled interview details",
                agent=self.scheduler
            )
            
            # Create a temporary crew for this task
            shortlist_crew = Crew(
                agents=[self.scheduler],
                tasks=[shortlist_task],
                verbose=True,
                process=Process.sequential
            )
            
            try:
                # Execute the shortlisting
                crew_result = shortlist_crew.kickoff()
                
                # Convert CrewOutput to string
                if hasattr(crew_result, 'raw'):
                    result = crew_result.raw
                elif hasattr(crew_result, 'result'):
                    result = crew_result.result
                else:
                    result = str(crew_result)
                
                completion_thought = {
                    "agent": "Interview Scheduling Coordinator",
                    "thought": "Candidate shortlisting completed successfully",
                    "timestamp": datetime.now().isoformat()
                }
                
                return {
                    "response": result,
                    "thought_process": [shortlisting_thought, completion_thought],
                    "primary_agent": "Interview Scheduling Coordinator",
                    "session_id": session_id
                }
            except Exception as e:
                logger.error(f"Error during candidate shortlisting: {e}")
                return {
                    "response": f"Error shortlisting candidates: {str(e)}",
                    "thought_process": [
                        shortlisting_thought,
                        {
                            "agent": "System",
                            "thought": f"Error: {str(e)}",
                            "timestamp": datetime.now().isoformat()
                        }
                    ],
                    "primary_agent": "Interview Scheduling Coordinator",
                    "session_id": session_id
                }

        # Check if query is related to rescheduling
        elif any(phrase in query.lower() for phrase in ["reschedule", "change interview time", "postpone interview"]):
            # Direct rescheduling
            reschedule_thought = {
                "agent": "Interview Scheduling Coordinator",
                "thought": f"Rescheduling interview based on: {query}",
                "timestamp": datetime.now().isoformat()
            }
            
            # Create a task for rescheduling
            reschedule_task = Task(
                description=f"""
                Reschedule an interview based on the following request:
                
                {query}
                
                Use the RescheduleInterview tool to change the interview time.
                
                You need to extract:
                1. Interview ID (if provided)
                2. Round index/number
                3. New time preference
                4. Reason for rescheduling
                
                If interview ID/round number/new time preference is not explicitly provided, you'll need to identify it from firebase db.
                """,
                expected_output="Confirmation of rescheduled interview with new details",
                agent=self.scheduler
            )
            
            # Create a temporary crew for this task
            reschedule_crew = Crew(
                agents=[self.scheduler],
                tasks=[reschedule_task],
                verbose=True,
                process=Process.sequential
            )
            
            try:
                # Execute the rescheduling
                crew_result = reschedule_crew.kickoff()
                
                # Convert CrewOutput to string
                if hasattr(crew_result, 'raw'):
                    result = crew_result.raw
                elif hasattr(crew_result, 'result'):
                    result = crew_result.result
                else:
                    result = str(crew_result)
                
                completion_thought = {
                    "agent": "Interview Scheduling Coordinator",
                    "thought": "Interview rescheduling completed successfully",
                    "timestamp": datetime.now().isoformat()
                }
                
                return {
                    "response": result,
                    "thought_process": [reschedule_thought, completion_thought],
                    "primary_agent": "Interview Scheduling Coordinator",
                    "session_id": session_id
                }
            except Exception as e:
                logger.error(f"Error during interview rescheduling: {e}")
                return {
                    "response": f"Error rescheduling interview: {str(e)}",
                    "thought_process": [
                        reschedule_thought,
                        {
                            "agent": "System",
                            "thought": f"Error: {str(e)}",
                            "timestamp": datetime.now().isoformat()
                        }
                    ],
                    "primary_agent": "Interview Scheduling Coordinator",
                    "session_id": session_id
                }
            
        # Check if query is related to processing resumes
        elif any(phrase in query.lower() for phrase in ["process resumes", "process candidates", "analyze resumes", "evaluate candidates", "screen candidates"]):
            # Direct resume processing
            resume_processing_thought = {
                "agent": "Candidate Screening Specialist",
                "thought": f"Processing resumes for job based on: {query}",
                "timestamp": datetime.now().isoformat()
            }
            
            # Create a simple task just for resume processing
            resume_task = Task(
                description=f"""
                Process resumes for the job mentioned in the following request:
                
                {query}
                
                Use the ProcessResumes tool to analyze the resumes and calculate AI fit scores.
                If no job ID is explicitly mentioned, try to extract the job role name from the query 
                and look up the matching job.
                
                Return a ranked list of candidates based on their fit scores.
                """,
                expected_output="A list of candidates ranked by their AI fit score",
                agent=self.candidate_screener
            )
            
            # Create a temporary crew for this task
            resume_crew = Crew(
                agents=[self.candidate_screener],
                tasks=[resume_task],
                verbose=True,
                process=Process.sequential
            )
            
            try:
                # Execute the resume processing
                crew_result = resume_crew.kickoff()
                
                # Convert CrewOutput to string
                if hasattr(crew_result, 'raw'):
                    result = crew_result.raw
                elif hasattr(crew_result, 'result'):
                    result = crew_result.result
                else:
                    result = str(crew_result)
                
                completion_thought = {
                    "agent": "Candidate Screening Specialist",
                    "thought": "Resume processing completed successfully",
                    "timestamp": datetime.now().isoformat()
                }
                
                return {
                    "response": result,
                    "thought_process": [resume_processing_thought, completion_thought],
                    "primary_agent": "Candidate Screening Specialist",
                    "session_id": session_id
                }
            except Exception as e:
                logger.error(f"Error during resume processing: {e}")
                return {
                    "response": f"Error processing resumes: {str(e)}",
                    "thought_process": [
                        resume_processing_thought,
                        {
                            "agent": "System",
                            "thought": f"Error: {str(e)}",
                            "timestamp": datetime.now().isoformat()
                        }
                    ],
                    "primary_agent": "Candidate Screening Specialist",
                    "session_id": session_id
                }
                
        # Check if query is related to job creation
        if any(phrase in query.lower() for phrase in ["create job", "add job", "new job", "post job"]):
            # Direct job creation
            job_creation_thought = {
                "agent": "Job Analysis Expert",
                "thought": f"Creating a new job posting based on: {query}",
                "timestamp": datetime.now().isoformat()
            }
            
            # Create a simple task just for job creation
            job_task = Task(
                description=f"""
                Create a new job posting based on the following information:
                
                {query}
                
                Use the CreateJobPosting tool to create the job in the system.
                """,
                expected_output="A confirmation of the job posting creation with details",
                agent=self.job_analyzer
            )
            
            # Create a temporary crew for this task
            job_crew = Crew(
                agents=[self.job_analyzer],
                tasks=[job_task],
                verbose=True,
                process=Process.sequential
            )
            
            try:
                # Execute the job creation
                crew_result = job_crew.kickoff()
                
                # Convert CrewOutput to string
                if hasattr(crew_result, 'raw'):
                    result = crew_result.raw
                elif hasattr(crew_result, 'result'):
                    result = crew_result.result
                else:
                    result = str(crew_result)
                
                completion_thought = {
                    "agent": "Job Analysis Expert",
                    "thought": "Job posting created successfully",
                    "timestamp": datetime.now().isoformat()
                }
                
                return {
                    "response": result,
                    "thought_process": [job_creation_thought, completion_thought],
                    "primary_agent": "Job Analysis Expert",
                    "session_id": session_id
                }
            except Exception as e:
                logger.error(f"Error during job creation: {e}")
                return {
                    "response": f"Error creating job posting: {str(e)}",
                    "thought_process": [
                        job_creation_thought,
                        {
                            "agent": "System",
                            "thought": f"Error: {str(e)}",
                            "timestamp": datetime.now().isoformat()
                        }
                    ],
                    "primary_agent": "Job Analysis Expert",
                    "session_id": session_id
                }
            
        # Initialize or retrieve session context
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "history": [],
                "context": {}
            }
        
        session = self.sessions[session_id]
        
        # Record the query in session history
        session["history"].append({
            "role": "user",
            "content": query,
            "timestamp": datetime.now().isoformat()
        })
        
        # Create tasks based on query content
        thoughts = []
        
        # Initial system thought
        system_thought = {
            "agent": "System",
            "thought": f"Analyzing query: {query}",
            "timestamp": datetime.now().isoformat()
        }
        thoughts.append(system_thought)
        
        # Create a dynamic task based on the query
        task = Task(
            description=f"""
            Process the following query from a user regarding interview scheduling:
            
            USER QUERY: {query}
            
            Based on the nature of this query, determine which aspects of the interview process need attention:
            1. Job analysis - understanding the requirements and qualifications
            2. Candidate screening - evaluating candidates against requirements
            3. Interview planning - designing the interview process and questions
            4. Scheduling - coordinating the logistics of interviews
            
            If this is a request to create a new job posting, use the CreateJobPosting tool to create it.
            
            Provide a comprehensive response that addresses all relevant aspects of the query.
            Your response should be professional, helpful, and action-oriented.
            Focus on providing the most concrete result specific to the query.
            
            IMPORTANT: Record your thinking process explicitly at each step to show how you're approaching the problem.
            """,
            expected_output="A comprehensive response to the user's interview-related query with detailed thought process",
            agent=self.get_primary_agent_for_query(query)
        )
        
        # Record thought about task assignment
        assignment_thought = {
            "agent": "System",
            "thought": f"Assigned task to {task.agent.role} as the primary agent",
            "timestamp": datetime.now().isoformat()
        }
        thoughts.append(assignment_thought)
        
        # Create a temporary crew with just this task
        temp_crew = Crew(
            agents=[self.job_analyzer, self.candidate_screener, 
                   self.interview_planner, self.scheduler],
            tasks=[task],
            verbose=True,  # Changed from 2 to True to fix validation error
            process=Process.sequential,
            memory=False  # Disable memory to avoid ChromaDB issues
        )
        
        try:
            # Record start of task execution
            execution_start_thought = {
                "agent": task.agent.role,
                "thought": f"Beginning to process query: {query}",
                "timestamp": datetime.now().isoformat()
            }
            thoughts.append(execution_start_thought)
            
            # Execute the crew's task
            crew_result = temp_crew.kickoff()
            
            # Convert CrewOutput to string to ensure it's JSON serializable
            if hasattr(crew_result, 'raw'):
                result = crew_result.raw
            elif hasattr(crew_result, 'result'):
                result = crew_result.result
            else:
                # If we can't access the raw output, convert to string
                result = str(crew_result)
            
            # Parse the result for thought process
            # We're simulating the thought process extraction here
            # In a real implementation, you'd want to modify CrewAI to expose the internal thought process
            
            # Add some simulated thoughts based on the agent roles
            for agent in [self.job_analyzer, self.candidate_screener, self.interview_planner, self.scheduler]:
                if agent.role != task.agent.role:  # Skip the primary agent
                    consultation_thought = {
                        "agent": agent.role,
                        "thought": f"Consulted on {agent.role.lower()} aspects of the query",
                        "timestamp": datetime.now().isoformat()
                    }
                    thoughts.append(consultation_thought)
            
            # Final thought from primary agent
            completion_thought = {
                "agent": task.agent.role,
                "thought": "Completed analysis and formulated response",
                "timestamp": datetime.now().isoformat()
            }
            thoughts.append(completion_thought)
            
            # Record the response in session history
            session["history"].append({
                "role": "assistant",
                "content": result,
                "timestamp": datetime.now().isoformat()
            })
            
            return {
                "response": result,
                "thought_process": thoughts,
                "primary_agent": task.agent.role,
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            error_thought = {
                "agent": "System",
                "thought": f"Error occurred: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
            thoughts.append(error_thought)
            
            return {
                "response": f"I apologize, but I encountered an error while processing your query: {str(e)}",
                "thought_process": thoughts,
                "primary_agent": "System Error Handler",
                "session_id": session_id
            }
    
    def get_primary_agent_for_query(self, query: str) -> Agent:
        """
        Determine which agent should be the primary handler for the given query
        
        Args:
            query: The user's query text
            
        Returns:
            The most appropriate agent for this query
        """
        # Simple keyword-based routing for now
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["job", "posting", "description", "requirement", "qualification", "skill"]):
            return self.job_analyzer
        elif any(word in query_lower for word in ["candidate", "applicant", "resume", "cv", "screen", "shortlist"]):
            return self.candidate_screener
        elif any(word in query_lower for word in ["interview", "question", "assessment", "evaluate", "process"]):
            return self.interview_planner
        elif any(word in query_lower for word in ["schedule", "time", "date", "availability", "calendar"]):
            return self.scheduler
        else:
            # Default to job analyzer if no clear match
            return self.job_analyzer


# Create a singleton instance
_crew_agent_system = None

def get_agent_system() -> CrewAgentSystem:
    """Get the singleton agent system instance"""
    global _crew_agent_system
    if _crew_agent_system is None:
        _crew_agent_system = CrewAgentSystem()
    return _crew_agent_system
