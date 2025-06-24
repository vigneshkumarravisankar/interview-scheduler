"""
Independent Resume Processing Agent System
Handles only resume processing and candidate evaluation
"""
import os
import re
import logging
from typing import Dict, Any
from datetime import datetime

from pydantic import BaseModel, Field
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from langchain.chat_models import ChatOpenAI

from app.services.job_service import JobService
from app.services.candidate_service import CandidateService

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

class ProcessResumesTool(BaseTool):
    name: str = "ProcessResumes"
    description: str = "Process resumes for a specific job role and calculate AI fit scores"
    
    class InputSchema(BaseModel):
        job_details: str = Field(description="Job details with job ID or job role name")
    
    args_schema = InputSchema
    
    def _run(self, job_details: str) -> str:
        """Process resumes for a specific job"""
        if isinstance(job_details, dict) and 'description' in job_details:
            job_details = job_details['description']
        elif not isinstance(job_details, str):
            return "Error: Invalid job details format. Please provide either a string or a dictionary with a 'description' field."
        
        logger.info(f"Processing resumes with input: {job_details}")
        
        try:
            # Extract job ID or job role name with flexible patterns
            job_id_match = re.search(r"(?:job_id|job id|id)[\s:=]*[\"\']?([^\"\'\n]+?)[\"\']?(?:\s|$)", job_details, re.IGNORECASE)
            
            # Look for role mentions in various formats
            job_role_patterns = [
                r"job_role_name\s*[:=]\s*[\"\']?([^\"\'\n]+?)[\"\']?(?:\s|$)",
                r"role\s*[:=]\s*[\"\']?([^\"\'\n]+?)[\"\']?(?:\s|$)",
                r"job title\s*[:=]\s*[\"\']?([^\"\'\n]+?)[\"\']?(?:\s|$)",
                r"position\s*[:=]\s*[\"\']?([^\"\'\n]+?)[\"\']?(?:\s|$)",
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
            
            job_id = job_id_match.group(1).strip() if job_id_match else None
            
            # If no explicit job role found, try to extract from general text
            if not job_role:
                common_job_titles = [
                    "software engineer", "data scientist", "product manager", 
                    "ui designer", "ux designer", "frontend developer",
                    "backend developer", "fullstack developer", "devops engineer",
                    "qa engineer", "machine learning engineer", "ai engineer",
                    "llm specialist", "genai specialist", "ml engineer",
                    "solutions architect", "project manager", "scrum master",
                    "product owner", "technical writer", "data analyst"
                ]
                
                for title in common_job_titles:
                    if title.lower() in job_details.lower():
                        job_role = title.title()
                        logger.info(f"Found job role from common titles: {job_role}")
                        break
            
            # If no job ID but have job role, try to find the job
            if not job_id and job_role:
                logger.info(f"Searching for job with role: {job_role}")
                all_jobs = JobService.get_all_job_postings()
                
                # First try exact title match
                matching_jobs = [job for job in all_jobs if job_role.lower() == job.job_role_name.lower()]
                
                # If no exact match, try contains match
                if not matching_jobs:
                    matching_jobs = [job for job in all_jobs if job_role.lower() in job.job_role_name.lower()]
                    
                # If still no match, try fuzzy matching
                if not matching_jobs:
                    job_role_words = set(job_role.lower().split())
                    for job in all_jobs:
                        job_name_words = set(job.job_role_name.lower().split())
                        if job_role_words and job_name_words and len(job_role_words.intersection(job_name_words)) / len(job_role_words) >= 0.5:
                            matching_jobs.append(job)
                
                if matching_jobs:
                    job_id = matching_jobs[0].job_id
                    logger.info(f"Found job ID {job_id} for role {job_role}")
                else:
                    return f"No job found with role name containing '{job_role}'. Please provide a valid job ID or create a job first."
            
            # If still no job ID, return an error with available jobs
            if not job_id:
                logger.error(f"No job found matching: '{job_role}' from input: '{job_details}'")
                
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

class GetCandidatesByJobTool(BaseTool):
    name: str = "GetCandidatesByJob"
    description: str = "Get all candidates processed for a specific job"
    
    class InputSchema(BaseModel):
        job_id: str = Field(description="ID of the job to get candidates for")
    
    args_schema = InputSchema
    
    def _run(self, job_id: str) -> str:
        """Get candidates for a specific job"""
        try:
            candidates = CandidateService.get_candidates_by_job(job_id)
            
            if not candidates:
                return f"No candidates found for job ID {job_id}"
            
            response = f"Found {len(candidates)} candidates for job ID {job_id}:\n\n"
            
            for i, candidate in enumerate(candidates, 1):
                response += f"{i}. {candidate.name}\n"
                response += f"   Email: {candidate.email}\n"
                response += f"   AI Fit Score: {candidate.ai_fit_score}/100\n"
                response += f"   Experience: {candidate.total_experience_in_years}\n\n"
            
            return response
            
        except Exception as e:
            return f"Error getting candidates: {str(e)}"

class ReprocessCandidatesTool(BaseTool):
    name: str = "ReprocessCandidates"
    description: str = "Re-evaluate candidates for a job with updated criteria"
    
    class InputSchema(BaseModel):
        job_id: str = Field(description="ID of the job to reprocess candidates for")
    
    args_schema = InputSchema
    
    def _run(self, job_id: str) -> str:
        """Reprocess candidates for a job"""
        try:
            # Get job details
            job = JobService.get_job_posting(job_id)
            if not job:
                return f"No job found with ID {job_id}"
            
            # Reprocess candidates
            candidates = CandidateService.process_resumes_for_job(job_id, force_reprocess=True)
            
            if not candidates:
                return f"No candidates reprocessed for job ID {job_id}"
            
            response = f"Successfully reprocessed {len(candidates)} candidates for job ID {job_id}\n\n"
            response += f"Updated candidate rankings:\n\n"
            
            # Sort by updated fit scores
            sorted_candidates = sorted(
                candidates,
                key=lambda c: int(c.ai_fit_score) if c.ai_fit_score.isdigit() else 0,
                reverse=True
            )
            
            for i, candidate in enumerate(sorted_candidates, 1):
                response += f"{i}. {candidate.name} - Score: {candidate.ai_fit_score}/100\n"
            
            return response
            
        except Exception as e:
            return f"Error reprocessing candidates: {str(e)}"

class ResumeProcessingAgentSystem:
    """Independent agent system for resume processing and candidate evaluation"""
    
    def __init__(self):
        """Initialize the resume processing agent system"""
        self.sessions = {}
        self.setup_crew()
    
    def setup_crew(self):
        """Set up the CrewAI agents and crew for resume processing"""
        # Create resume processing tools
        process_resumes_tool = ProcessResumesTool()
        get_candidates_tool = GetCandidatesByJobTool()
        reprocess_candidates_tool = ReprocessCandidatesTool()
        
        # Create specialized resume processing agent
        self.resume_processor = Agent(
            role="Resume Processing Specialist",
            goal="Efficiently process and evaluate candidate resumes against job requirements",
            backstory="""You are an expert talent acquisition specialist with deep experience in 
            resume analysis and candidate evaluation. You excel at matching candidate profiles 
            with job requirements, calculating fit scores, and providing detailed assessments 
            of candidate qualifications.""",
            verbose=True,
            allow_delegation=False,
            llm=llm,
            tools=[process_resumes_tool, get_candidates_tool, reprocess_candidates_tool]
        )
        
        # Create the resume processing crew
        self.crew = Crew(
            agents=[self.resume_processor],
            tasks=[],
            verbose=True,
            process=Process.sequential
        )
    
    def process_resume_query(self, query: str, session_id: str) -> Dict[str, Any]:
        """
        Process a resume-related query using the specialized resume processing agent system
        
        Args:
            query: The user's resume processing query text
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
            "agent": "Resume Processing Specialist",
            "thought": f"Analyzing resume processing request: {query}",
            "timestamp": datetime.now().isoformat()
        }
        thoughts.append(analysis_thought)
        
        try:
            # Create task for resume processing
            resume_task = Task(
                description=f"""
                Process the following resume processing request:
                
                USER REQUEST: {query}
                
                Determine the appropriate action:
                1. If processing resumes for a job, use ProcessResumes tool
                2. If getting existing candidates for a job, use GetCandidatesByJob tool
                3. If reprocessing candidates with updated criteria, use ReprocessCandidates tool
                
                Extract job information from the request and provide comprehensive results.
                """,
                expected_output="Complete response to the resume processing request with candidate rankings",
                agent=self.resume_processor
            )
            
            resume_crew = Crew(
                agents=[self.resume_processor],
                tasks=[resume_task],
                verbose=True,
                process=Process.sequential
            )
            
            processing_thought = {
                "agent": "Resume Processing Specialist",
                "thought": "Processing resumes and calculating candidate fit scores",
                "timestamp": datetime.now().isoformat()
            }
            thoughts.append(processing_thought)
            
            crew_result = resume_crew.kickoff()
            
            if hasattr(crew_result, 'raw'):
                result = crew_result.raw
            elif hasattr(crew_result, 'result'):
                result = crew_result.result
            else:
                result = str(crew_result)
            
            completion_thought = {
                "agent": "Resume Processing Specialist",
                "thought": "Resume processing completed successfully",
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
                "primary_agent": "Resume Processing Specialist",
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Error processing resume query: {e}")
            error_thought = {
                "agent": "Resume Processing Specialist",
                "thought": f"Error occurred: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
            thoughts.append(error_thought)
            
            return {
                "response": f"I apologize, but I encountered an error while processing your resume request: {str(e)}",
                "thought_process": thoughts,
                "primary_agent": "Resume Processing Specialist",
                "session_id": session_id
            }

# Create a singleton instance
_resume_processing_agent_system = None

def get_resume_processing_agent_system() -> ResumeProcessingAgentSystem:
    """Get the singleton resume processing agent system instance"""
    global _resume_processing_agent_system
    if _resume_processing_agent_system is None:
        _resume_processing_agent_system = ResumeProcessingAgentSystem()
    return _resume_processing_agent_system
