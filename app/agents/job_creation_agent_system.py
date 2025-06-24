"""
Independent Job Creation Agent System
Handles only job posting creation and management
"""
import os
import re
import json
import logging
from typing import Dict, Any
from datetime import datetime

from pydantic import BaseModel, Field
from openai import OpenAI
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from langchain.chat_models import ChatOpenAI

from app.services.job_service import JobService
from app.schemas.job_schema import JobPostingCreate

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get OpenAI API Key from environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY not found in environment. Using default key.")
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
        system_prompt = """
        You are an expert job description parser. Extract structured information from 
        the job details provided and format it into the exact JSON structure requested.
        
        Make sure:
        1. Each field contains ONLY the information relevant to that field
        2. Do not include field information in other fields
        3. Return ONLY the JSON with no additional text
        """
        
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
        - Return ONLY valid JSON with no additional text or explanations
        """
        
        response = openai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        parsed_job = json.loads(response.choices[0].message.content)
        
        # Ensure all required fields are present
        required_fields = ["job_role_name", "job_description", "location", "years_of_experience_needed", "status"]
        for field in required_fields:
            if field not in parsed_job or not parsed_job[field]:
                if field == "status":
                    parsed_job[field] = "active"
                elif field == "job_role_name":
                    parsed_job[field] = "Untitled Position"
                elif field == "job_description":
                    parsed_job[field] = job_details
                elif field == "location":
                    parsed_job[field] = "Remote"
                elif field == "years_of_experience_needed":
                    exp_match = re.search(r"(\d+(?:-\d+)?\s*(?:years|yrs))", job_details, re.IGNORECASE)
                    parsed_job[field] = exp_match.group(1) if exp_match else "1-3 years"
        
        return parsed_job
    
    except Exception as e:
        logger.error(f"Error formatting job with LLM: {e}")
        return {
            "job_role_name": "Untitled Position",
            "job_description": job_details,
            "location": "Remote",
            "years_of_experience_needed": "1-3 years",
            "status": "active"
        }

class CreateJobPostingTool(BaseTool):
    name: str = "CreateJobPosting"
    description: str = "Create a job posting in the system"
    
    class InputSchema(BaseModel):
        job_details: str = Field(description="Job details text with information about the job posting")
    
    args_schema = InputSchema
    
    def _run(self, job_details: str) -> str:
        """Create a job posting from the provided details"""
        if isinstance(job_details, dict) and 'description' in job_details:
            job_details = job_details['description']
        elif not isinstance(job_details, str):
            return "Error: Invalid job details format. Please provide either a string or a dictionary with a 'description' field."
        
        try:
            logger.info("Using LLM to format job details")
            parsed_job_data = format_job_with_llm(job_details)
            
            job_posting = JobPostingCreate(
                job_role_name=parsed_job_data["job_role_name"],
                job_description=parsed_job_data["job_description"],
                years_of_experience_needed=parsed_job_data["years_of_experience_needed"],
                location=parsed_job_data["location"],
                status=parsed_job_data["status"]
            )
             
            result = JobService.create_job_posting(job_posting)
            
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

class GetAllJobsTool(BaseTool):
    name: str = "GetAllJobs"
    description: str = "Get all job postings in the system"
    
    class InputSchema(BaseModel):
        pass
    
    args_schema = InputSchema
    
    def _run(self) -> str:
        """Get all job postings"""
        try:
            jobs = JobService.get_all_job_postings()
            
            if not jobs or len(jobs) == 0:
                return "No job postings found."
            
            result = f"Found {len(jobs)} job postings:\n\n"
            
            for i, job in enumerate(jobs, 1):
                result += f"Job {i}:\n"
                result += f"ID: {job.job_id}\n"
                result += f"Role: {job.job_role_name}\n"
                result += f"Experience Required: {job.years_of_experience_needed}\n"
                result += f"Location: {job.location}\n"
                result += f"Status: {job.status}\n\n"
            
            return result
        except Exception as e:
            return f"Error getting job postings: {str(e)}"

class GetJobByIdTool(BaseTool):
    name: str = "GetJobById"
    description: str = "Get a specific job posting by ID"
    
    class InputSchema(BaseModel):
        job_id: str = Field(description="ID of the job to retrieve")
    
    args_schema = InputSchema
    
    def _run(self, job_id: str) -> str:
        """Get a specific job posting by ID"""
        try:
            job = JobService.get_job_posting(job_id)
            
            if not job:
                return f"No job found with ID {job_id}"
            
            result = f"Job Details for ID: {job_id}\n\n"
            result += f"Role: {job.job_role_name}\n"
            result += f"Description: {job.job_description}\n"
            result += f"Experience Required: {job.years_of_experience_needed}\n"
            result += f"Location: {job.location}\n"
            result += f"Status: {job.status}\n"
            
            return result
        except Exception as e:
            return f"Error getting job details: {str(e)}"

class JobCreationAgentSystem:
    """Independent agent system for job creation and management"""
    
    def __init__(self):
        """Initialize the job creation agent system"""
        self.sessions = {}
        self.setup_crew()
    
    def setup_crew(self):
        """Set up the CrewAI agents and crew for job management"""
        # Create job management tools
        create_job_tool = CreateJobPostingTool()
        get_all_jobs_tool = GetAllJobsTool()
        get_job_by_id_tool = GetJobByIdTool()
        
        # Create specialized job creation agent
        self.job_creator = Agent(
            role="Job Creation Specialist",
            goal="Create and manage job postings efficiently and accurately",
            backstory="""You are an expert job posting specialist with deep knowledge of job market 
            requirements and industry standards. You excel at creating comprehensive job descriptions 
            that attract the right candidates and accurately reflect job requirements.""",
            verbose=True,
            allow_delegation=False,
            llm=llm,
            tools=[create_job_tool, get_all_jobs_tool, get_job_by_id_tool]
        )
        
        # Create the job creation crew
        self.crew = Crew(
            agents=[self.job_creator],
            tasks=[],
            verbose=True,
            process=Process.sequential
        )
    
    def process_job_query(self, query: str, session_id: str) -> Dict[str, Any]:
        """
        Process a job-related query using the specialized job creation agent system
        
        Args:
            query: The user's job-related query text
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
            "agent": "Job Creation Specialist",
            "thought": f"Analyzing job creation request: {query}",
            "timestamp": datetime.now().isoformat()
        }
        thoughts.append(analysis_thought)
        
        try:
            # Create task for job management
            job_task = Task(
                description=f"""
                Process the following job management request:
                
                USER REQUEST: {query}
                
                Determine the appropriate action:
                1. If creating a job posting, use CreateJobPosting tool
                2. If requesting all jobs, use GetAllJobs tool
                3. If requesting specific job details, use GetJobById tool
                
                Provide a comprehensive response that addresses the request.
                """,
                expected_output="Complete response to the job management request",
                agent=self.job_creator
            )
            
            job_crew = Crew(
                agents=[self.job_creator],
                tasks=[job_task],
                verbose=True,
                process=Process.sequential
            )
            
            processing_thought = {
                "agent": "Job Creation Specialist",
                "thought": "Processing job management request",
                "timestamp": datetime.now().isoformat()
            }
            thoughts.append(processing_thought)
            
            crew_result = job_crew.kickoff()
            
            if hasattr(crew_result, 'raw'):
                result = crew_result.raw
            elif hasattr(crew_result, 'result'):
                result = crew_result.result
            else:
                result = str(crew_result)
            
            completion_thought = {
                "agent": "Job Creation Specialist",
                "thought": "Job management request completed successfully",
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
                "primary_agent": "Job Creation Specialist",
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Error processing job query: {e}")
            error_thought = {
                "agent": "Job Creation Specialist",
                "thought": f"Error occurred: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
            thoughts.append(error_thought)
            
            return {
                "response": f"I apologize, but I encountered an error while processing your job request: {str(e)}",
                "thought_process": thoughts,
                "primary_agent": "Job Creation Specialist",
                "session_id": session_id
            }

# Create a singleton instance
_job_creation_agent_system = None

def get_job_creation_agent_system() -> JobCreationAgentSystem:
    """Get the singleton job creation agent system instance"""
    global _job_creation_agent_system
    if _job_creation_agent_system is None:
        _job_creation_agent_system = JobCreationAgentSystem()
    return _job_creation_agent_system
