"""
CrewAI Agent System for Interview Scheduler
"""
import os
import re
from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime
import logging
import json

from pydantic import BaseModel, Field
from openai import OpenAI
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from langchain.chat_models import ChatOpenAI
from app.services.job_service import JobService
from app.services.candidate_service import CandidateService
from app.schemas.job_schema import JobPostingCreate, JobPostingResponse
from app.schemas.candidate_schema import CandidateResponse

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
    
    def _run(self, job_details: str) -> str:
        """
        Create a job posting from the provided details
        
        Args:
            job_details: Can be either a string or a dict with description field
        """
        # Convert to string if dictionary is passed
        if isinstance(job_details, dict) and 'description' in job_details:
            job_details = job_details['description']
        elif not isinstance(job_details, str):
            return "Error: Invalid job details format. Please provide either a string or a dictionary with a 'description' field."
        """Create a job posting from the provided details"""
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
            
            # Format response
            response = f"""
 Job posting created successfully!

Job ID: {result.job_id}
Role: {result.job_role_name}
Experience Required: {result.years_of_experience_needed}
Location: {result.location}
Status: {result.status}

Description:
{result.job_description}
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
            
            # Sort candidates by fit score
            sorted_candidates = sorted(
                candidates,
                key=lambda c: int(c.ai_fit_score) if c.ai_fit_score.isdigit() else 0,
                reverse=True
            )
            
            for i, candidate in enumerate(sorted_candidates):
                response += f"#{i+1}: {candidate.name}\n"
                response += f"   Email: {candidate.email}\n"
                response += f"   Phone: {candidate.phone_no}\n"
                response += f"   AI Fit Score: {candidate.ai_fit_score}/100\n"
                response += f"   Experience: {candidate.total_experience_in_years}\n"
                response += f"   Skills: {candidate.technical_skills}\n\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing resumes: {e}")
            return f"Failed to process resumes: {str(e)}"

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
        
        self.scheduler = Agent(
            role="Interview Scheduling Coordinator",
            goal="Efficiently schedule interviews considering all parties' availability",
            backstory="You excel at coordinating complex schedules across multiple stakeholders. You understand the importance of finding optimal time slots and managing the logistics of interview processes.",
            verbose=True,
            allow_delegation=True,
            llm=llm,
            tools=[]
        )
        
        # Create the crew
        self.crew = Crew(
            agents=[self.job_analyzer, self.candidate_screener, 
                   self.interview_planner, self.scheduler],
            tasks=[],  # Tasks will be created dynamically
            verbose=True,  # Changed from 2 to True to fix validation error
            process=Process.sequential
        )
    
    def process_query(self, query: str, session_id: str) -> Dict[str, Any]:
        """
        Process a query using the agent system
        
        Args:
            query: The user's query text
            session_id: Session identifier for conversation context
            
        Returns:
            Dictionary containing the response and thought process
        """
        # Check if query is related to processing resumes
        if any(phrase in query.lower() for phrase in ["process resumes", "process candidates", "analyze resumes", "evaluate candidates", "screen candidates"]):
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
            memory=True
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
