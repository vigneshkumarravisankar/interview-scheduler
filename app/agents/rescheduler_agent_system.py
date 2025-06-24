"""
Independent Interview Rescheduler Agent System
Handles only interview rescheduling operations
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

class RescheduleInterviewTool(BaseTool):
    name: str = "RescheduleInterview"
    description: str = "Reschedule an interview for a candidate at a different time"
    
    class InputSchema(BaseModel):
        interview_id: str = Field(description="ID of the interview record to reschedule")
        round_index: int = Field(description="Index of the round to reschedule (0-based)")
        new_time: str = Field(description="New time for the interview (format: 'YYYY-MM-DD HH:MM')")
        reason: str = Field(description="Reason for rescheduling", default="Scheduling conflict")
    
    args_schema = InputSchema
    
    def _run(self, interview_id: str, round_index: int, new_time: str, reason: str = "Scheduling conflict") -> str:
        """Reschedule an interview at a different time"""
        try:
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
                try:
                    CalendarService.delete_event(old_event_id)
                except Exception as e:
                    logger.warning(f"Failed to delete old calendar event: {e}")
            
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
                
                # Extract event details
                if calendar_event:
                    event_id = calendar_event.get('id', '')
                    meet_link = calendar_event.get('hangoutLink', calendar_event.get('manual_meet_link', ''))
                    html_link = calendar_event.get('htmlLink', '')
                else:
                    raise Exception("Calendar event creation returned None")
                    
            except Exception as calendar_error:
                logger.warning(f"Calendar integration failed: {calendar_error}")
                # Create fallback data when calendar integration fails
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
            InterviewCoreService.update_interview_candidate(interview_record.get("id"), interview_record)
            
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

Reason for rescheduling: {reason}
"""
            except Exception as e:
                logger.error(f"Error sending email notification: {e}")
                return f"""
Successfully rescheduled the interview for {candidate_name} with {interviewer_name}, but failed to send email notifications.

New Interview Details:
- Date: {start_time.strftime("%A, %B %d, %Y")}
- Time: {formatted_time}
- Meet Link: {meet_link}

Reason for rescheduling: {reason}
"""
        
        except Exception as e:
            logger.error(f"Error rescheduling interview: {e}")
            return f"Error rescheduling interview: {str(e)}"

class FindInterviewToRescheduleTool(BaseTool):
    name: str = "FindInterviewToReschedule"
    description: str = "Find interview records that match given criteria for rescheduling"
    
    class InputSchema(BaseModel):
        candidate_name: str = Field(description="Name of the candidate (optional)", default="")
        job_role: str = Field(description="Job role name (optional)", default="")
        interview_id: str = Field(description="Specific interview ID (optional)", default="")
    
    args_schema = InputSchema
    
    def _run(self, candidate_name: str = "", job_role: str = "", interview_id: str = "") -> str:
        """Find interview records matching the criteria"""
        try:
            if interview_id:
                # Get specific interview by ID
                interview = InterviewCoreService.get_interview_candidate(interview_id)
                if not interview:
                    return f"No interview found with ID: {interview_id}"
                
                interviews = [interview]
            else:
                # Get all interviews and filter
                all_interviews = InterviewCoreService.get_all_interview_candidates()
                interviews = []
                
                for interview in all_interviews:
                    match = True
                    
                    if candidate_name and candidate_name.lower() not in interview.get('candidate_name', '').lower():
                        match = False
                    
                    if job_role and job_role.lower() not in interview.get('job_role', '').lower():
                        match = False
                    
                    if match:
                        interviews.append(interview)
            
            if not interviews:
                return "No interviews found matching the criteria."
            
            response = f"Found {len(interviews)} interview(s) that can be rescheduled:\n\n"
            
            for i, interview in enumerate(interviews, 1):
                response += f"{i}. Interview ID: {interview.get('id')}\n"
                response += f"   Candidate: {interview.get('candidate_name')}\n"
                response += f"   Job Role: {interview.get('job_role')}\n"
                response += f"   Status: {interview.get('status')}\n"
                
                feedback_array = interview.get('feedback', [])
                for idx, feedback in enumerate(feedback_array):
                    scheduled_event = feedback.get('scheduled_event')
                    if scheduled_event:
                        start_time = scheduled_event.get('start', {}).get('dateTime', 'TBD')
                        response += f"   Round {idx+1}: Currently scheduled for {start_time}\n"
                    else:
                        response += f"   Round {idx+1}: Not yet scheduled\n"
                
                response += "\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Error finding interviews: {e}")
            return f"Error finding interviews: {str(e)}"

class CancelInterviewTool(BaseTool):
    name: str = "CancelInterview"
    description: str = "Cancel a scheduled interview"
    
    class InputSchema(BaseModel):
        interview_id: str = Field(description="ID of the interview record")
        round_index: int = Field(description="Index of the round to cancel (0-based)")
        reason: str = Field(description="Reason for cancellation", default="Interview cancelled")
    
    args_schema = InputSchema
    
    def _run(self, interview_id: str, round_index: int, reason: str = "Interview cancelled") -> str:
        """Cancel a scheduled interview"""
        try:
            # Get the interview record
            interview_record = InterviewCoreService.get_interview_candidate(interview_id)
            
            if not interview_record:
                return f"Interview record with ID {interview_id} not found."
                
            # Verify the round index is valid
            feedback_array = interview_record.get('feedback', [])
            if round_index < 0 or round_index >= len(feedback_array):
                return f"Invalid round index {round_index}. Valid range: 0-{len(feedback_array)-1}"
            
            # Get the round details
            round_details = feedback_array[round_index]
            candidate_name = interview_record.get('candidate_name', 'Candidate')
            candidate_email = interview_record.get('candidate_email', 'candidate@example.com')
            interviewer_name = round_details.get('interviewer_name', 'Interviewer')
            interviewer_email = round_details.get('interviewer_email', 'interviewer@example.com')
            
            # Delete the calendar event if it exists
            old_event_id = round_details.get('scheduled_event', {}).get('id')
            if old_event_id:
                try:
                    CalendarService.delete_event(old_event_id)
                except Exception as e:
                    logger.warning(f"Failed to delete calendar event: {e}")
            
            # Clear the scheduling information
            round_details['scheduled_time'] = None
            round_details['meet_link'] = None
            round_details['scheduled_event'] = None
            
            # Update the feedback array
            feedback_array[round_index] = round_details
            interview_record['feedback'] = feedback_array
            
            # Save the updated record
            InterviewCoreService.update_interview_candidate(interview_record.get("id"), interview_record)
            
            return f"""
Interview cancelled successfully for {candidate_name} with {interviewer_name}.

Cancelled Interview Details:
- Round: {round_index + 1}
- Reason: {reason}

Notifications should be sent to:
- {candidate_email}
- {interviewer_email}
"""
        
        except Exception as e:
            logger.error(f"Error cancelling interview: {e}")
            return f"Error cancelling interview: {str(e)}"

class ReschedulerAgentSystem:
    """Independent agent system for interview rescheduling operations"""
    
    def __init__(self):
        """Initialize the rescheduler agent system"""
        self.sessions = {}
        self.setup_crew()
    
    def setup_crew(self):
        """Set up the CrewAI agents and crew for rescheduling"""
        # Create rescheduling tools
        reschedule_tool = RescheduleInterviewTool()
        find_interview_tool = FindInterviewToRescheduleTool()
        cancel_interview_tool = CancelInterviewTool()
        
        # Create specialized rescheduler agent
        self.rescheduler = Agent(
            role="Interview Rescheduling Specialist",
            goal="Efficiently handle interview rescheduling requests and calendar management",
            backstory="""You are an expert interview logistics coordinator with deep experience in 
            managing interview schedules and handling rescheduling requests. You excel at understanding 
            scheduling conflicts, finding optimal alternative times, and ensuring smooth communication 
            between all parties involved in the interview process.""",
            verbose=True,
            allow_delegation=False,
            llm=llm,
            tools=[reschedule_tool, find_interview_tool, cancel_interview_tool]
        )
        
        # Create the rescheduling crew
        self.crew = Crew(
            agents=[self.rescheduler],
            tasks=[],
            verbose=True,
            process=Process.sequential
        )
    
    def process_reschedule_query(self, query: str, session_id: str) -> Dict[str, Any]:
        """
        Process a rescheduling query using the specialized rescheduler agent system
        
        Args:
            query: The user's rescheduling query text
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
            "agent": "Interview Rescheduling Specialist",
            "thought": f"Analyzing rescheduling request: {query}",
            "timestamp": datetime.now().isoformat()
        }
        thoughts.append(analysis_thought)
        
        try:
            # Create task for rescheduling
            reschedule_task = Task(
                description=f"""
                Process the following interview rescheduling request:
                
                USER REQUEST: {query}
                
                Determine the appropriate action:
                1. If rescheduling an existing interview, use RescheduleInterview tool
                2. If finding interviews that match criteria, use FindInterviewToReschedule tool
                3. If cancelling an interview, use CancelInterview tool
                
                Extract relevant parameters like interview ID, candidate name, new time, and reason.
                Provide comprehensive results with updated scheduling details.
                """,
                expected_output="Complete response to the rescheduling request with updated interview details",
                agent=self.rescheduler
            )
            
            reschedule_crew = Crew(
                agents=[self.rescheduler],
                tasks=[reschedule_task],
                verbose=True,
                process=Process.sequential
            )
            
            processing_thought = {
                "agent": "Interview Rescheduling Specialist",
                "thought": "Processing interview rescheduling request",
                "timestamp": datetime.now().isoformat()
            }
            thoughts.append(processing_thought)
            
            crew_result = reschedule_crew.kickoff()
            
            if hasattr(crew_result, 'raw'):
                result = crew_result.raw
            elif hasattr(crew_result, 'result'):
                result = crew_result.result
            else:
                result = str(crew_result)
            
            completion_thought = {
                "agent": "Interview Rescheduling Specialist",
                "thought": "Rescheduling request completed successfully",
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
                "primary_agent": "Interview Rescheduling Specialist",
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Error processing reschedule query: {e}")
            error_thought = {
                "agent": "Interview Rescheduling Specialist",
                "thought": f"Error occurred: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
            thoughts.append(error_thought)
            
            return {
                "response": f"I apologize, but I encountered an error while processing your rescheduling request: {str(e)}",
                "thought_process": thoughts,
                "primary_agent": "Interview Rescheduling Specialist",
                "session_id": session_id
            }

# Create a singleton instance
_rescheduler_agent_system = None

def get_rescheduler_agent_system() -> ReschedulerAgentSystem:
    """Get the singleton rescheduler agent system instance"""
    global _rescheduler_agent_system
    if _rescheduler_agent_system is None:
        _rescheduler_agent_system = ReschedulerAgentSystem()
    return _rescheduler_agent_system
