"""
Job management agents for the interview system

These agents handle job-related operations including:
- Creating new job postings
- Retrieving job information
- Listing available jobs
- Processing resume data
"""
import os
import logging
from typing import Dict, Any, List, Optional
import uuid

# CrewAI imports
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from langchain.chat_models import ChatOpenAI

# Service imports
from app.services.job_service import JobService
from app.services.candidate_service import extract_resume_data
from app.database.firebase_db import FirestoreDB

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize LLM model for CrewAI
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY not found in environment. Using default key.")
    # Default key from project setup
    OPENAI_API_KEY = "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"

# Initialize LLM model for CrewAI
llm = ChatOpenAI(
    openai_api_key=OPENAI_API_KEY,
    model_name="gpt-4o",
    temperature=0.2
)

#-----------------------
# Job Management Tools
#-----------------------
class CreateJobTool(BaseTool):
    name: str = "CreateJob"
    description: str = "Create a new job posting with the specified details"
    
    def _run(self, job_details: Dict[str, Any] = None, job_role_name: str = None, job_description: str = None, 
             years_of_experience_needed: str = None, status: str = None, location: str = None) -> str:
        """Create a new job posting with the provided details"""
        try:
            # Import job schema dynamically to avoid circular imports
            from app.schemas.job_schema import JobPostingCreate
            
            # Handle both direct parameters and job_details object
            if job_details:
                # Extract values from job_details object
                role = job_details.get("job_role_name")
                desc = job_details.get("job_description")
                exp = job_details.get("years_of_experience_needed")
                job_status = job_details.get("status", "open")
                job_location = job_details.get("location", "remote")
            else:
                # Use directly provided parameters
                role = job_role_name
                desc = job_description
                exp = years_of_experience_needed
                job_status = status or "open"
                job_location = location or "remote"
                
            # Log the job details for debugging
            print(f"Creating job with details: role={role}, exp={exp}, location={job_location}")
            
            # Create job posting object
            job_posting = JobPostingCreate(
                job_role_name=role,
                job_description=desc,
                years_of_experience_needed=exp,
                status=job_status,
                location=job_location
            )
            
            # Save job posting using service
            job_id = JobService.create_job_posting(job_posting)
            
            return f"""Successfully created job posting:
            ID: {job_id}
            Role: {role}
            Experience: {exp}
            Status: {job_status}
            Location: {job_location}
            """
        except Exception as e:
            return f"Error creating job posting: {str(e)}"

class GetAllJobsTool(BaseTool):
    name: str = "GetAllJobs"
    description: str = "Get all job postings"
    
    def _run(self) -> str:
        """Get all job postings"""
        try:
            jobs = JobService.get_all_job_postings()
            
            if not jobs or len(jobs) == 0:
                return "No job postings found."
            
            result = f"Found {len(jobs)} job postings:\n\n"
            
            for i, job in enumerate(jobs):
                # Handle different job object formats
                if hasattr(job, "job_role_name"):
                    # It's a Pydantic model
                    job_id = job.id if hasattr(job, "id") else "Unknown"
                    role = job.job_role_name
                    description = job.job_description[:100] + "..." if len(job.job_description) > 100 else job.job_description
                    experience = job.years_of_experience_needed
                    status = job.status
                    location = job.location
                else:
                    # It's a dictionary
                    job_id = job.get("id", "Unknown")
                    role = job.get("job_role_name", "Unknown")
                    description = job.get("job_description", "No description")
                    if len(description) > 100:
                        description = description[:100] + "..."
                    experience = job.get("years_of_experience_needed", "Unknown")
                    status = job.get("status", "Unknown")
                    location = job.get("location", "Unknown")
                
                result += f"Job {i+1}:\n"
                result += f"ID: {job_id}\n"
                result += f"Role: {role}\n"
                result += f"Description: {description}\n"
                result += f"Experience Required: {experience}\n"
                result += f"Status: {status}\n"
                result += f"Location: {location}\n\n"
            
            return result
        except Exception as e:
            return f"Error getting job postings: {str(e)}"

class GetJobTool(BaseTool):
    name: str = "GetJob"
    description: str = "Get a specific job posting by ID"
    
    def _run(self, job_id: str) -> str:
        """Get a specific job posting by ID"""
        try:
            job = JobService.get_job_posting(job_id)
            
            if not job:
                return f"No job found with ID {job_id}"
            
            # Handle different job object formats
            if hasattr(job, "job_role_name"):
                # It's a Pydantic model
                result = f"Job Details for ID: {job_id}\n\n"
                result += f"Role: {job.job_role_name}\n"
                result += f"Description: {job.job_description}\n"
                result += f"Experience Required: {job.years_of_experience_needed}\n"
                result += f"Status: {job.status}\n"
                result += f"Location: {job.location}\n"
            else:
                # It's a dictionary
                result = f"Job Details for ID: {job_id}\n\n"
                result += f"Role: {job.get('job_role_name', 'Unknown')}\n"
                result += f"Description: {job.get('job_description', 'No description')}\n"
                result += f"Experience Required: {job.get('years_of_experience_needed', 'Unknown')}\n"
                result += f"Status: {job.get('status', 'Unknown')}\n"
                result += f"Location: {job.get('location', 'Unknown')}\n"
            
            return result
        except Exception as e:
            return f"Error getting job details: {str(e)}"

class ProcessResumeDataTool(BaseTool):
    name: str = "ProcessResumeData"
    description: str = "Process resume data for a specific job"
    
    def _run(self, job_id: str) -> str:
        """Process resume data for a job"""
        try:
            # Get job details to pass to the resume processor
            job = JobService.get_job_posting(job_id)
            
            if not job:
                return f"No job found with ID {job_id}"
            
            # Convert job to dict if needed
            job_dict = job
            if hasattr(job, "dict"):
                job_dict = job.dict()
                
            # Process the resume data
            result = extract_resume_data(job_id=job_id, job_data=job_dict)
            
            if not result:
                return f"No candidates processed for job {job_id}"
            
            # Format the response
            response = f"Successfully processed resumes for job {job_id}\n\n"
            response += f"Processed {len(result)} candidate resumes\n"
            
            return response
        except Exception as e:
            return f"Error processing resume data: {str(e)}"

#-----------------------
# Agent Definitions
#-----------------------

# Job Management Agent
job_agent = Agent(
    role="Job Management Specialist",
    goal="Efficiently manage job postings and related operations",
    backstory="You are an expert in managing job postings with years of experience in talent acquisition. Your job is to create, retrieve, and manage job postings in the system.",
    verbose=True,
    allow_delegation=True,
    llm=llm,
    tools=[
        CreateJobTool(),
        GetAllJobsTool(),
        GetJobTool(),
        ProcessResumeDataTool()
    ]
)

#-----------------------
# Crew Definition and Functions
#-----------------------

def create_job_creation_crew(job_details: Dict[str, Any]):
    """Create a crew for job creation"""
    
    # Extract job details
    job_role = job_details.get("job_role_name", "Software Engineer")
    job_description = job_details.get("job_description", "Default job description")
    years_of_experience = job_details.get("years_of_experience_needed", "0-1 years")
    status = job_details.get("status", "open")
    location = job_details.get("location", "remote")
    
    # Create job creation task
    job_creation_task = Task(
        description=f"""
        Create a new job posting with the following details:
        
        Role: {job_role}
        Description: {job_description}
        Experience Required: {years_of_experience}
        Status: {status}
        Location: {location}
        
        Return the job posting details.
        """,
        expected_output="Details of the created job posting",
        agent=job_agent
    )
    
    # Create the crew
    crew = Crew(
        agents=[job_agent],
        tasks=[job_creation_task],
        verbose=True,
        process=Process.sequential
    )
    
    return crew

def create_job_retrieval_crew(job_id: str = None):
    """Create a crew for retrieving job information"""
    
    # Create task based on whether a job ID was provided
    if job_id:
        # Retrieve specific job
        retrieval_task = Task(
            description=f"""
            Retrieve details for job with ID: {job_id}
            
            Return all details of the job posting.
            """,
            expected_output=f"Complete details of job with ID {job_id}",
            agent=job_agent
        )
    else:
        # Retrieve all jobs
        retrieval_task = Task(
            description="""
            Retrieve a list of all job postings in the system.
            
            Return the list of jobs with their key details.
            """,
            expected_output="List of all job postings with their details",
            agent=job_agent
        )
    
    # Create the crew
    crew = Crew(
        agents=[job_agent],
        tasks=[retrieval_task],
        verbose=True,
        process=Process.sequential
    )
    
    return crew

def create_resume_processing_crew(job_id: str):
    """Create a crew for processing resume data"""
    
    # Create resume processing task
    processing_task = Task(
        description=f"""
        Process resume data for job with ID: {job_id}
        
        This task involves:
        1. Retrieving the job details
        2. Processing all resumes associated with the job
        3. Analyzing resumes for fit with the job requirements
        
        Return the results of the resume processing.
        """,
        expected_output=f"Results of resume processing for job {job_id}",
        agent=job_agent
    )
    
    # Create the crew
    crew = Crew(
        agents=[job_agent],
        tasks=[processing_task],
        verbose=True,
        process=Process.sequential
    )
    
    return crew

# Functions to run the specific processes
def run_job_creation_process(job_details: Dict[str, Any]):
    """Run the job creation process"""
    print(f"Starting job creation process with details: {job_details}")
    crew = create_job_creation_crew(job_details)
    result = crew.kickoff()
    return result

def run_job_retrieval_process(job_id: str = None):
    """Run the job retrieval process"""
    crew = create_job_retrieval_crew(job_id)
    result = crew.kickoff()
    return result

def run_resume_processing_process(job_id: str):
    """Run the resume processing process"""
    crew = create_resume_processing_crew(job_id)
    result = crew.kickoff()
    return result
