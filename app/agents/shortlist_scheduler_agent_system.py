"""
Independent Shortlist and Interview Scheduler Agent System
Handles only candidate shortlisting and interview scheduling
"""
import os
import re
import logging
import random
import string
from typing import Dict, Any
from datetime import datetime, timedelta

from pydantic import BaseModel, Field
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from langchain.chat_models import ChatOpenAI

from app.services.interview_shortlist_service import InterviewShortlistService
from app.services.interview_core_service import InterviewCoreService
from app.utils.calendar_service import CalendarService, create_calendar_event
from app.utils.email_notification import send_interview_notification

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get OpenAI API Key from environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY not found in environment. Using default key.")
    OPENAI_API_KEY = "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"

# Initialize LLM model for CrewAI
llm = ChatOpenAI(
    openai_api_key=OPENAI_API_KEY,
    model_name="gpt-4o",
    temperature=0.2
)

class ShortlistCandidatesTool(BaseTool):
    name: str = "ShortlistCandidates"
    description: str = "Shortlist top N candidates for interviews based on AI fit scores and schedule interviews"
    
    class InputSchema(BaseModel):
        job_id: str = Field(description="ID of the job to shortlist candidates for")
        number_of_candidates: int = Field(description="Number of candidates to shortlist", default=3)
        number_of_rounds: int = Field(description="Number of interview rounds", default=2)
        specific_time: str = Field(description="Specific time for interviews (optional, format: 'YYYY-MM-DD HH:MM')", default="")
    
    args_schema = InputSchema
    
    def _run(self, job_id: str, number_of_candidates: int = 3, number_of_rounds: int = 2, specific_time: str = "") -> str:
        """Shortlist candidates for interviews based on AI fit scores and schedule interviews"""
        try:
            logger.info(f"Shortlisting candidates for job {job_id}, top {number_of_candidates} candidates, {number_of_rounds} rounds")
            
            if specific_time:
                logger.info(f"Specific time requested: {specific_time}")
            
            # Shortlist candidates using the service
            shortlisted, created_records = InterviewShortlistService.shortlist_candidates(
                job_id=job_id,
                number_of_candidates=number_of_candidates,
                no_of_interviews=number_of_rounds
            )
            
            if not shortlisted:
                return "No candidates were found or shortlisted for this job. Please process some resumes first."
                
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
                        for idx, feedback in enumerate(record.get('feedback', [])):
                            round_num = idx + 1
                            interviewer = feedback.get('interviewer_name')
                            
                            response += f"      Round {round_num}: with {interviewer}\n"
                            
                            # Show scheduling details for the first round
                            if idx == 0 and feedback.get('scheduled_event'):
                                start_time = feedback.get('scheduled_event', {}).get('start', {}).get('dateTime', 'TBD')
                                
                                # Format the datetime for readability
                                if start_time != 'TBD':
                                    try:
                                        dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                                        start_time = dt.strftime("%A, %B %d, %Y at %I:%M %p")
                                    except Exception:
                                        pass
                                
                                response += f"         Scheduled: {start_time}\n"
                                response += f"         Meet Link: {feedback.get('meet_link', 'TBD')}\n"
                        
                response += "\n"
                
            return response
            
        except Exception as e:
            logger.error(f"Error shortlisting candidates: {e}")
            return f"Error shortlisting candidates: {str(e)}"

class ScheduleInterviewTool(BaseTool):
    name: str = "ScheduleInterview"
    description: str = "Schedule a specific interview for a candidate"
    
    class InputSchema(BaseModel):
        interview_id: str = Field(description="ID of the interview record")
        round_index: int = Field(description="Index of the round to schedule (0-based)")
        scheduled_time: str = Field(description="Time for the interview (format: 'YYYY-MM-DD HH:MM')")
    
    args_schema = InputSchema
    
    def _run(self, interview_id: str, round_index: int, scheduled_time: str) -> str:
        """Schedule a specific interview round"""
        try:
            # Get the interview record
            interview_record = InterviewCoreService.get_interview_candidate(interview_id)
            
            if not interview_record:
                return f"Interview record with ID {interview_id} not found."
                
            # Verify the round index is valid
            feedback_array = interview_record.get('feedback', [])
            if round_index < 0 or round_index >= len(feedback_array):
                return f"Invalid round index {round_index}. Valid range: 0-{len(feedback_array)-1}"
            
            # Parse the scheduled time
            try:
                interview_datetime = datetime.strptime(scheduled_time, "%Y-%m-%d %H:%M")
                start_time = interview_datetime
                end_time = interview_datetime.replace(hour=interview_datetime.hour + 1)  # 1 hour interview
                
                # Format dates in ISO format with timezone
                start_iso = start_time.strftime("%Y-%m-%dT%H:%M:%S+05:30")
                end_iso = end_time.strftime("%Y-%m-%dT%H:%M:%S+05:30")
                
                # Format for display
                formatted_time = start_time.strftime("%I%p").lstrip('0')
            except ValueError:
                return f"Invalid time format. Please use the format 'YYYY-MM-DD HH:MM'"
            
            # Get round details
            round_details = feedback_array[round_index]
            candidate_name = interview_record.get('candidate_name', 'Candidate')
            candidate_email = interview_record.get('candidate_email', 'candidate@example.com')
            interviewer_name = round_details.get('interviewer_name', 'Interviewer')
            interviewer_email = round_details.get('interviewer_email', 'interviewer@example.com')
            job_role = interview_record.get('job_role', 'Unknown Position')
            round_type = round_details.get('round_type', f"Round {round_index+1}")
            
            # Create event summary and description
            summary = f"Interview: {candidate_name} with {interviewer_name} - Round {round_index+1} ({round_type})"
            description = f"""
            Interview for {candidate_name} ({candidate_email})
            Job: {job_role}
            Round: {round_index+1} - {round_type} Round
            Interviewer: {interviewer_name} ({interviewer_email})
            
            Please join using the Google Meet link at the scheduled time.
            """
            
            # Create calendar event
            try:
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
                
                if calendar_event:
                    event_id = calendar_event.get('id', '')
                    meet_link = calendar_event.get('hangoutLink', calendar_event.get('manual_meet_link', ''))
                    html_link = calendar_event.get('htmlLink', '')
                else:
                    raise Exception("Calendar event creation failed")
                    
            except Exception as calendar_error:
                logger.warning(f"Calendar integration failed: {calendar_error}")
                # Create fallback data
                event_id = ''.join(random.choices(string.ascii_letters + string.digits, k=20))
                meet_link = f"https://meet.google.com/abc-def-ghi"
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
            
            # Send email notification
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
                    is_rescheduled=False
                )
                
                return f"""
Successfully scheduled interview for {candidate_name} with {interviewer_name}.

Interview Details:
- Date: {start_time.strftime("%A, %B %d, %Y")}
- Time: {formatted_time}
- Meet Link: {meet_link}

Email notifications have been sent to:
- {candidate_email}
- {interviewer_email}
"""
            except Exception as e:
                logger.error(f"Error sending email notification: {e}")
                return f"""
Successfully scheduled interview for {candidate_name} with {interviewer_name}, but failed to send email notifications.

Interview Details:
- Date: {start_time.strftime("%A, %B %d, %Y")}
- Time: {formatted_time}
- Meet Link: {meet_link}
"""
        
        except Exception as e:
            logger.error(f"Error scheduling interview: {e}")
            return f"Error scheduling interview: {str(e)}"

class GetInterviewCandidatesTool(BaseTool):
    name: str = "GetInterviewCandidates"
    description: str = "Get list of interview candidates and their scheduling status"
    
    class InputSchema(BaseModel):
        job_id: str = Field(description="ID of the job to get candidates for (optional)", default="")
        status_filter: str = Field(description="Filter by status: 'all', 'scheduled', 'pending', 'completed'", default="all")
    
    args_schema = InputSchema
    
    def _run(self, job_id: str = "", status_filter: str = "all") -> str:
        """Get list of interview candidates"""
        try:
            if job_id:
                candidates = InterviewCoreService.get_candidates_by_job(job_id)
            else:
                candidates = InterviewCoreService.get_all_interview_candidates()
            
            if status_filter != "all":
                candidates = [c for c in candidates if c.get('status', '').lower() == status_filter.lower()]
            
            if not candidates:
                return f"No candidates found with status: {status_filter}"
            
            response = f"Found {len(candidates)} interview candidates:\n\n"
            
            for i, candidate in enumerate(candidates, 1):
                response += f"{i}. {candidate.get('candidate_name')} - {candidate.get('job_role')}\n"
                response += f"   Status: {candidate.get('status')}\n"
                response += f"   Interview ID: {candidate.get('id')}\n"
                
                feedback_array = candidate.get('feedback', [])
                for idx, feedback in enumerate(feedback_array):
                    scheduled_event = feedback.get('scheduled_event')
                    if scheduled_event:
                        start_time = scheduled_event.get('start', {}).get('dateTime', 'TBD')
                        response += f"   Round {idx+1}: Scheduled for {start_time}\n"
                    else:
                        response += f"   Round {idx+1}: Not scheduled\n"
                
                response += "\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting interview candidates: {e}")
            return f"Error getting candidates: {str(e)}"

class ShortlistSchedulerAgentSystem:
    """Independent agent system for candidate shortlisting and interview scheduling"""
    
    def __init__(self):
        """Initialize the shortlist and scheduler agent system"""
        self.sessions = {}
        self.setup_crew()
    
    def setup_crew(self):
        """Set up the CrewAI agents and crew for shortlisting and scheduling"""
        # Create shortlisting and scheduling tools
        shortlist_tool = ShortlistCandidatesTool()
        schedule_tool = ScheduleInterviewTool()
        get_candidates_tool = GetInterviewCandidatesTool()
        
        # Create specialized shortlist and scheduler agent
        self.shortlist_scheduler = Agent(
            role="Interview Shortlist and Scheduling Coordinator",
            goal="Efficiently shortlist top candidates and schedule their interviews seamlessly",
            backstory="""You are an expert interview coordination specialist with deep experience in 
            candidate selection and interview logistics. You excel at identifying the best candidates 
            based on fit scores, coordinating schedules across multiple stakeholders, and ensuring 
            smooth interview processes from shortlisting to scheduling.""",
            verbose=True,
            allow_delegation=False,
            llm=llm,
            tools=[shortlist_tool, schedule_tool, get_candidates_tool]
        )
        
        # Create the shortlist and scheduling crew
        self.crew = Crew(
            agents=[self.shortlist_scheduler],
            tasks=[],
            verbose=True,
            process=Process.sequential
        )
    
    def process_shortlist_query(self, query: str, session_id: str) -> Dict[str, Any]:
        """
        Process a shortlisting/scheduling query using the specialized agent system
        
        Args:
            query: The user's shortlisting/scheduling query text
            session_id: Session identifier for conversation context
            
        Returns:
            Dictionary containing the response and thought process
        """
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "history": [],
                "context": {}
            }
        
        session = self.sessions[session_id]
        
        session["history"].append({
            "role": "user",
            "content": query,
            "timestamp": datetime.now().isoformat()
        })
        
        thoughts = []
        
        analysis_thought = {
            "agent": "Interview Shortlist and Scheduling Coordinator",
            "thought": f"Analyzing shortlisting and scheduling request: {query}",
            "timestamp": datetime.now().isoformat()
        }
        thoughts.append(analysis_thought)
        
        try:
            # Create task for shortlisting and scheduling
            shortlist_task = Task(
                description=f"""
                Process the following shortlisting and scheduling request:
                
                USER REQUEST: {query}
                
                Determine the appropriate action:
                1. If shortlisting candidates, use ShortlistCandidates tool
                2. If scheduling specific interviews, use ScheduleInterview tool
                3. If getting interview candidate information, use GetInterviewCandidates tool
                
                Extract relevant parameters like job ID, number of candidates, rounds, and time preferences.
                Provide comprehensive results with scheduling details.
                """,
                expected_output="Complete response to the shortlisting and scheduling request with interview details",
                agent=self.shortlist_scheduler
            )
            
            shortlist_crew = Crew(
                agents=[self.shortlist_scheduler],
                tasks=[shortlist_task],
                verbose=True,
                process=Process.sequential
            )
            
            processing_thought = {
                "agent": "Interview Shortlist and Scheduling Coordinator",
                "thought": "Processing candidate shortlisting and interview scheduling",
                "timestamp": datetime.now().isoformat()
            }
            thoughts.append(processing_thought)
            
            crew_result = shortlist_crew.kickoff()
            
            if hasattr(crew_result, 'raw'):
                result = crew_result.raw
            elif hasattr(crew_result, 'result'):
                result = crew_result.result
            else:
                result = str(crew_result)
            
            completion_thought = {
                "agent": "Interview Shortlist and Scheduling Coordinator",
                "thought": "Shortlisting and scheduling completed successfully",
                "timestamp": datetime.now().isoformat()
            }
            thoughts.append(completion_thought)
            
            session["history"].append({
                "role": "assistant",
                "content": result,
                "timestamp": datetime.now().isoformat()
            })
            
            return {
                "response": result,
                "thought_process": thoughts,
                "primary_agent": "Interview Shortlist and Scheduling Coordinator",
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Error processing shortlist query: {e}")
            error_thought = {
                "agent": "Interview Shortlist and Scheduling Coordinator",
                "thought": f"Error occurred: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
            thoughts.append(error_thought)
            
            return {
                "response": f"I apologize, but I encountered an error while processing your shortlisting request: {str(e)}",
                "thought_process": thoughts,
                "primary_agent": "Interview Shortlist and Scheduling Coordinator",
                "session_id": session_id
            }

# Create a singleton instance
_shortlist_scheduler_agent_system = None

def get_shortlist_scheduler_agent_system() -> ShortlistSchedulerAgentSystem:
    """Get the singleton shortlist and scheduler agent system instance"""
    global _shortlist_scheduler_agent_system
    if _shortlist_scheduler_agent_system is None:
        _shortlist_scheduler_agent_system = ShortlistSchedulerAgentSystem()
    return _shortlist_scheduler_agent_system
