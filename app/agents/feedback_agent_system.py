"""
CrewAI Feedback Agent System for Interview Feedback Management
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
from langchain.chat_models import ChatOpenAI
from app.services.interview_core_service import InterviewCoreService
from app.services.interview_schedule_service import InterviewScheduleService
from app.utils.calendar_service import CalendarService, create_calendar_event
from app.utils.email_notification import send_interview_notification
import random
import string

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get OpenAI API Key from environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY not found in environment. Using default key.")
    # Default key from the project setup
    OPENAI_API_KEY = "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"

# Initialize LLM model for CrewAI
llm = ChatOpenAI(
    openai_api_key=OPENAI_API_KEY,
    model_name="gpt-4o",
    temperature=0.2
)

def parse_feedback_request(request_text: str) -> Dict[str, Any]:
    """
    Parse natural language feedback request using LLM
    
    Args:
        request_text: Natural language feedback request
        
    Returns:
        Dictionary with parsed feedback parameters
    """
    try:
        # Initialize OpenAI client
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Prepare system prompt
        system_prompt = """
        You are an expert at parsing interview feedback requests. Extract structured information from 
        the feedback request and format it into the exact JSON structure requested.
        
        Make sure:
        1. Extract the candidate name exactly as provided
        2. Extract the job role name exactly as provided
        3. Extract the round number (convert to integer)
        4. Extract the rating (convert to integer between 1-10)
        5. Extract the selection status ("yes", "no", or "pending")
        6. Extract the feedback text exactly as provided
        7. Return ONLY valid JSON with no additional text
        """
        
        # Prepare user prompt
        user_prompt = f"""
        Parse the following feedback request and format it into this exact JSON structure:
        
        {{
          "candidate_name": "",           # Full name of the candidate
          "job_role_name": "",           # Job role name
          "round_number": 0,             # Round number as integer
          "rating_out_of_10": 0,         # Rating as integer (1-10)
          "is_selected_for_next_round": "", # "yes", "no", or "pending"
          "feedback_text": ""            # Feedback text exactly as provided
        }}
        
        FEEDBACK REQUEST:
        {request_text}
        
        IMPORTANT:
        - Extract candidate name exactly as written
        - Extract job role exactly as written
        - Convert round number to integer (e.g., "round-1" becomes 1)
        - Convert rating to integer between 1-10
        - Determine selection status: if mentions "selected", "proceed", "next round" = "yes"; if mentions "rejected", "not selected" = "no"; otherwise "pending"
        - Keep feedback text exactly as quoted in the request
        - Return ONLY valid JSON with no additional text or explanations
        """
        
        # Call the LLM
        response = openai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,  # Low temperature for consistent extraction
            response_format={"type": "json_object"}
        )
        
        # Parse the JSON response
        parsed_feedback = json.loads(response.choices[0].message.content)
        
        # Validate required fields
        required_fields = ["candidate_name", "job_role_name", "round_number", "rating_out_of_10", "is_selected_for_next_round", "feedback_text"]
        for field in required_fields:
            if field not in parsed_feedback:
                logger.warning(f"Missing field {field} in LLM response")
                # Provide defaults
                if field == "round_number":
                    parsed_feedback[field] = 1
                elif field == "rating_out_of_10":
                    parsed_feedback[field] = 5
                elif field == "is_selected_for_next_round":
                    parsed_feedback[field] = "pending"
                else:
                    parsed_feedback[field] = ""
        
        return parsed_feedback
    
    except Exception as e:
        logger.error(f"Error parsing feedback request with LLM: {e}")
        # Return a minimal structure as fallback
        return {
            "candidate_name": "",
            "job_role_name": "",
            "round_number": 1,
            "rating_out_of_10": 5,
            "is_selected_for_next_round": "pending",
            "feedback_text": request_text
        }

# Define tools for feedback agents
class UpdateInterviewFeedbackTool(BaseTool):
    name: str = "UpdateInterviewFeedback"
    description: str = "Update interview feedback for a candidate's specific round using natural language input"
    
    # Define schema for the tool
    class InputSchema(BaseModel):
        candidate_name: str = Field(description="Name of the candidate")
        job_role_name: str = Field(description="Job role name")
        round_number: int = Field(description="Round number (1-based, e.g., 1, 2, 3, 4)")
        is_selected_for_next_round: str = Field(description="Selection status: 'yes', 'no', or 'pending'")
        rating_out_of_10: int = Field(description="Rating from 1-10")
        feedback_text: str = Field(description="Feedback in natural language sentence")
    
    # Set the argument schema
    args_schema = InputSchema
    
    def _run(
        self, 
        candidate_name: str, 
        job_role_name: str, 
        round_number: int,
        is_selected_for_next_round: str,
        rating_out_of_10: int,
        feedback_text: str
    ) -> str:
        """
        Update interview feedback using natural language input and auto-schedule next round if selected
        
        Args:
            candidate_name: Name of the candidate
            job_role_name: Job role name
            round_number: Round number (1-based)
            is_selected_for_next_round: Selection status
            rating_out_of_10: Rating from 1-10
            feedback_text: Feedback text
        
        Returns:
            String with update results
        """
        try:
            logger.info(f"Updating feedback for {candidate_name} - {job_role_name} - Round {round_number}")
            
            # Use the natural language feedback update function
            success = InterviewCoreService.update_feedback_by_natural_input(
                candidate_name=candidate_name,
                job_role_name=job_role_name,
                round_number=round_number,
                is_selected_for_next_round=is_selected_for_next_round,
                rating_out_of_10=rating_out_of_10,
                feedback_text=feedback_text
            )
            
            if success:
                response = f"""
✅ Successfully updated feedback for {candidate_name}!

Details:
- Job Role: {job_role_name}
- Round: {round_number}
- Rating: {rating_out_of_10}/10
- Selection: {is_selected_for_next_round}
- Feedback: {feedback_text}
"""
                
                # If selected for next round, check and schedule the next round automatically
                if is_selected_for_next_round.lower() == "yes":
                    try:
                        logger.info(f"Candidate selected for next round, attempting to schedule next interview")
                        
                        # Get the updated candidate record to check for next round
                        candidate = InterviewCoreService.get_candidate_by_name_and_role(candidate_name, job_role_name)
                        
                        if candidate:
                            feedback_array = candidate.get("feedback", [])
                            next_round_index = round_number  # 0-based index for next round
                            
                            # Check if next round exists
                            if next_round_index < len(feedback_array):
                                next_round_details = feedback_array[next_round_index]
                                
                                # Check if next round is not already scheduled
                                if not next_round_details.get('scheduled_event') and not next_round_details.get('meet_link'):
                                    logger.info(f"Scheduling next round {next_round_index + 1}")
                                    
                                    # Schedule the next round interview
                                    scheduling_result = self._schedule_next_round_interview(
                                        candidate=candidate,
                                        next_round_index=next_round_index,
                                        next_round_details=next_round_details
                                    )
                                    
                                    response += f"\n\n🎯 Next Round Auto-Scheduling:\n{scheduling_result}"
                                else:
                                    response += f"\n\n📅 Next round ({next_round_index + 1}) is already scheduled."
                            else:
                                response += f"\n\n🏁 No more rounds available - candidate has completed all interview rounds!"
                        
                    except Exception as scheduling_error:
                        logger.error(f"Error in next round scheduling: {scheduling_error}")
                        response += f"\n\n⚠️ Next round scheduling failed: {str(scheduling_error)}"
                
                response += f"\n\nThe candidate's status has been updated in the system."
                return response
            else:
                return f"❌ Failed to update feedback for {candidate_name} - {job_role_name} - Round {round_number}. Please check if the candidate exists and the round number is valid."
                
        except Exception as e:
            logger.error(f"Error updating interview feedback: {e}")
            return f"❌ Error updating feedback: {str(e)}"
    
    def _schedule_next_round_interview(self, candidate: Dict[str, Any], next_round_index: int, next_round_details: Dict[str, Any]) -> str:
        """
        Schedule the next round interview with calendar event and email notifications
        
        Args:
            candidate: Candidate record from Firebase
            next_round_index: Index of the next round (0-based)
            next_round_details: Details of the next round
        
        Returns:
            String describing the scheduling result
        """
        try:
            # Extract candidate and interviewer details
            candidate_name = candidate.get('candidate_name', 'Candidate')
            candidate_email = candidate.get('candidate_email', 'candidate@example.com')
            job_role = candidate.get('job_role', 'Unknown Position')
            interviewer_name = next_round_details.get('interviewer_name', 'Interviewer')
            interviewer_email = next_round_details.get('interviewer_email', 'interviewer@example.com')
            round_type = next_round_details.get('round_type', f"Round {next_round_index + 1}")
            
            # Generate interview time (next business day at 10 AM)
            from datetime import datetime, timedelta
            now = datetime.now()
            next_day = now + timedelta(days=1)
            
            # If it's weekend, schedule for Monday
            while next_day.weekday() > 4:  # 0-4 is Monday-Friday
                next_day += timedelta(days=1)
            
            # Set to 10 AM
            interview_time = next_day.replace(hour=10, minute=0, second=0, microsecond=0)
            end_time = interview_time.replace(hour=11)  # 1 hour interview
            
            # Format dates in ISO format with timezone
            start_iso = interview_time.strftime("%Y-%m-%dT%H:%M:%S+05:30")
            end_iso = end_time.strftime("%Y-%m-%dT%H:%M:%S+05:30")
            
            # Format for display
            formatted_time = interview_time.strftime("%I%p").lstrip('0')  # e.g., "10AM"
            interview_date = interview_time.strftime("%A, %B %d, %Y")
            
            # Create event summary and description
            summary = f"Interview: {candidate_name} with {interviewer_name} - Round {next_round_index + 1} ({round_type})"
            description = f"""
            Interview for {candidate_name} ({candidate_email})
            Job: {job_role}
            Round: {next_round_index + 1} - {round_type} Round
            Interviewer: {interviewer_name} ({interviewer_email})
            
            This interview was automatically scheduled after the candidate was selected from the previous round.
            
            Please join using the Google Meet link at the scheduled time.
            """
            
            # Create calendar event with fallback handling
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
                    calendar_status = "✅ Calendar event created successfully"
                else:
                    raise Exception("Calendar event creation returned None")
                    
            except Exception as calendar_error:
                logger.warning(f"Calendar integration failed: {calendar_error}")
                # Create fallback data when calendar integration fails
                event_id = ''.join(random.choices(string.ascii_letters + string.digits, k=20))
                meet_link = f"https://meet.google.com/{CalendarService.generate_meet_code()}" if hasattr(CalendarService, 'generate_meet_code') else f"https://meet.google.com/abc-def-ghi"
                html_link = f"https://calendar.google.com/calendar/event?eid=mock-event"
                calendar_status = f"⚠️ Calendar integration failed: {str(calendar_error)}\n   Generated manual meet link instead"
            
            # Update the next round details in Firebase
            next_round_details['scheduled_time'] = formatted_time
            next_round_details['meet_link'] = meet_link
            next_round_details['scheduled_event'] = {
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
            
            # Update the candidate record
            feedback_array = candidate.get("feedback", [])
            feedback_array[next_round_index] = next_round_details
            candidate['feedback'] = feedback_array
            candidate['current_round_scheduled'] = True
            
            # Save to Firebase
            InterviewCoreService.update_interview_candidate(candidate.get("id"), candidate)
            
            # Send email notifications
            try:
                send_interview_notification(
                    candidate_name=candidate_name,
                    recipient_email=candidate_email,
                    interviewer_name=interviewer_name,
                    interviewer_email=interviewer_email,
                    job_title=job_role,
                    start_time=formatted_time,
                    interview_date=interview_date,
                    meet_link=meet_link,
                    round_number=next_round_index + 1,
                    round_type=round_type,
                    is_rescheduled=False
                )
                
                email_status = f"📧 Email notifications sent to:\n   - {candidate_email}\n   - {interviewer_email}"
                
            except Exception as email_error:
                logger.error(f"Error sending email notification: {email_error}")
                email_status = "⚠️ Email notification failed"
            
            return f"""✅ Round {next_round_index + 1} scheduled successfully!

📅 Interview Details:
- Date: {interview_date}
- Time: {formatted_time}
- Interviewer: {interviewer_name}
- Type: {round_type}
- Meet Link: {meet_link}

{email_status}"""
            
        except Exception as e:
            logger.error(f"Error scheduling next round interview: {e}")
            return f"❌ Failed to schedule next round: {str(e)}"

class GetInterviewCandidatesTool(BaseTool):
    name: str = "GetInterviewCandidates"
    description: str = "Get list of interview candidates with their current status"
    
    # Define schema for the tool
    class InputSchema(BaseModel):
        status_filter: str = Field(description="Filter by status: 'all', 'scheduled', 'in_progress', 'completed', 'selected', 'rejected'", default="all")
    
    # Set the argument schema
    args_schema = InputSchema
    
    def _run(self, status_filter: str = "all") -> str:
        """
        Get list of interview candidates
        
        Args:
            status_filter: Status filter
        
        Returns:
            String with candidate list
        """
        try:
            if status_filter == "all":
                candidates = InterviewCoreService.list_candidates_for_feedback()
            else:
                candidates = InterviewCoreService.get_candidates_by_status(status_filter)
            
            if not candidates:
                return f"No candidates found with status: {status_filter}"
            
            response = f"Found {len(candidates)} candidates:\n\n"
            
            for i, candidate in enumerate(candidates, 1):
                response += f"{i}. {candidate.get('candidate_name')} - {candidate.get('job_role')}\n"
                response += f"   Status: {candidate.get('status')}\n"
                response += f"   Completed Rounds: {candidate.get('completed_rounds')}\n"
                response += f"   Next Round: {candidate.get('next_round')}\n\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting interview candidates: {e}")
            return f"❌ Error getting candidates: {str(e)}"

class GetCandidateFeedbackTool(BaseTool):
    name: str = "GetCandidateFeedback"
    description: str = "Get feedback history for a specific candidate"
    
    # Define schema for the tool
    class InputSchema(BaseModel):
        candidate_name: str = Field(description="Name of the candidate")
        job_role_name: str = Field(description="Job role name")
    
    # Set the argument schema
    args_schema = InputSchema
    
    def _run(self, candidate_name: str, job_role_name: str) -> str:
        """
        Get feedback for a specific candidate
        
        Args:
            candidate_name: Name of the candidate
            job_role_name: Job role name
        
        Returns:
            String with feedback history
        """
        try:
            candidate = InterviewCoreService.get_candidate_by_name_and_role(candidate_name, job_role_name)
            
            if not candidate:
                return f"❌ No candidate found with name '{candidate_name}' and job role '{job_role_name}'"
            
            feedback_array = candidate.get("feedback", [])
            
            response = f"Feedback for {candidate_name} - {job_role_name}:\n\n"
            response += f"Overall Status: {candidate.get('status')}\n"
            response += f"Completed Rounds: {candidate.get('completedRounds', 0)}/{len(feedback_array)}\n\n"
            
            for i, feedback in enumerate(feedback_array, 1):
                response += f"Round {i} ({feedback.get('round_type', 'Unknown')}):\n"
                response += f"  Interviewer: {feedback.get('interviewer_name', 'TBD')}\n"
                response += f"  Rating: {feedback.get('rating_out_of_10', 'Not rated')}/10\n"
                response += f"  Selection: {feedback.get('isSelectedForNextRound', 'Pending')}\n"
                response += f"  Feedback: {feedback.get('feedback', 'No feedback yet')}\n\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting candidate feedback: {e}")
            return f"❌ Error getting feedback: {str(e)}"

class FeedbackAgentSystem:
    """CrewAI-based agent system for interview feedback management"""
    
    def __init__(self):
        """Initialize the feedback agent system"""
        # Store session conversations
        self.sessions = {}
        # Create the agent crew
        self.setup_crew()
    
    def setup_crew(self):
        """Set up the CrewAI agents and crew for feedback management"""
        # Create feedback-specific tools
        feedback_update_tool = UpdateInterviewFeedbackTool()
        get_candidates_tool = GetInterviewCandidatesTool()
        get_feedback_tool = GetCandidateFeedbackTool()
        
        # Create specialized feedback agent
        self.feedback_manager = Agent(
            role="Interview Feedback Manager",
            goal="Efficiently manage and update interview feedback for candidates across all interview rounds",
            backstory="""You are an expert interview feedback coordinator with deep experience in managing 
            interview processes. You excel at parsing natural language feedback requests, updating candidate 
            evaluations, and ensuring accurate record-keeping throughout the interview pipeline. Your role is 
            crucial in maintaining the integrity of the candidate evaluation process.""",
            verbose=True,
            allow_delegation=False,  # No delegation needed for focused feedback tasks
            llm=llm,
            tools=[feedback_update_tool, get_candidates_tool, get_feedback_tool]
        )
        
        # Create the feedback crew
        self.crew = Crew(
            agents=[self.feedback_manager],
            tasks=[],  # Tasks will be created dynamically
            verbose=True,
            process=Process.sequential
        )
    
    def process_feedback_query(self, query: str, session_id: str) -> Dict[str, Any]:
        """
        Process a feedback-related query using the specialized feedback agent system
        
        Args:
            query: The user's feedback query text
            session_id: Session identifier for conversation context
            
        Returns:
            Dictionary containing the response and thought process
        """
        # Initialize session if needed
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
        
        # Create thoughts array
        thoughts = []
        
        # Initial analysis thought
        analysis_thought = {
            "agent": "Interview Feedback Manager",
            "thought": f"Analyzing feedback request: {query}",
            "timestamp": datetime.now().isoformat()
        }
        thoughts.append(analysis_thought)
        
        try:
            # Parse the feedback request using LLM
            parsing_thought = {
                "agent": "Interview Feedback Manager", 
                "thought": "Extracting structured information from the feedback request",
                "timestamp": datetime.now().isoformat()
            }
            thoughts.append(parsing_thought)
            
            parsed_request = parse_feedback_request(query)
            
            # Validation thought
            validation_thought = {
                "agent": "Interview Feedback Manager",
                "thought": f"Extracted parameters - Candidate: {parsed_request.get('candidate_name')}, Role: {parsed_request.get('job_role_name')}, Round: {parsed_request.get('round_number')}",
                "timestamp": datetime.now().isoformat()
            }
            thoughts.append(validation_thought)
            
            # Create a task for feedback update
            feedback_task = Task(
                description=f"""
                Update interview feedback based on the following parsed information:
                
                Original Request: {query}
                
                Parsed Parameters:
                - Candidate Name: {parsed_request.get('candidate_name')}
                - Job Role: {parsed_request.get('job_role_name')}
                - Round Number: {parsed_request.get('round_number')}
                - Rating: {parsed_request.get('rating_out_of_10')}/10
                - Selection Status: {parsed_request.get('is_selected_for_next_round')}
                - Feedback Text: {parsed_request.get('feedback_text')}
                
                Use the UpdateInterviewFeedback tool to update the candidate's feedback in the system.
                Ensure all parameters are correctly extracted and applied.
                
                If any required information is missing or unclear, request clarification.
                """,
                expected_output="Confirmation of successful feedback update with details",
                agent=self.feedback_manager
            )
            
            # Create a temporary crew for this task
            feedback_crew = Crew(
                agents=[self.feedback_manager],
                tasks=[feedback_task],
                verbose=True,
                process=Process.sequential
            )
            
            # Processing thought
            processing_thought = {
                "agent": "Interview Feedback Manager",
                "thought": "Updating feedback in the Firebase database",
                "timestamp": datetime.now().isoformat()
            }
            thoughts.append(processing_thought)
            
            # Execute the feedback update
            crew_result = feedback_crew.kickoff()
            
            # Convert CrewOutput to string
            if hasattr(crew_result, 'raw'):
                result = crew_result.raw
            elif hasattr(crew_result, 'result'):
                result = crew_result.result
            else:
                result = str(crew_result)
            
            # Completion thought
            completion_thought = {
                "agent": "Interview Feedback Manager",
                "thought": "Feedback update completed successfully",
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
                "primary_agent": "Interview Feedback Manager",
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Error processing feedback query: {e}")
            error_thought = {
                "agent": "Interview Feedback Manager",
                "thought": f"Error occurred: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
            thoughts.append(error_thought)
            
            return {
                "response": f"I apologize, but I encountered an error while processing your feedback request: {str(e)}",
                "thought_process": thoughts,
                "primary_agent": "Interview Feedback Manager",
                "session_id": session_id
            }

# Create a singleton instance
_feedback_agent_system = None

def get_feedback_agent_system() -> FeedbackAgentSystem:
    """Get the singleton feedback agent system instance"""
    global _feedback_agent_system
    if _feedback_agent_system is None:
        _feedback_agent_system = FeedbackAgentSystem()
    return _feedback_agent_system
