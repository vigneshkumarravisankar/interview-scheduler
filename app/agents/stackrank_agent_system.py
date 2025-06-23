"""
Enhanced CrewAI Stackranking Agent System - Modular and Production Ready
"""
import os
import logging
from typing import Dict, Any
from datetime import datetime

from crewai import Agent, Task, Crew, Process
from langchain.chat_models import ChatOpenAI

from .stackrank_parser import parse_stackrank_request
from .stackrank_tools import StackrankCandidatesTool, SendOfferLettersTool, GetStackrankResultsTool
from .stackrank_core import stackrank_candidates_by_job_role

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


class StackrankAgentSystem:
    """CrewAI-based agent system for candidate stackranking and offer management"""
    
    def __init__(self):
        """Initialize the stackranking agent system"""
        # Store session conversations
        self.sessions = {}
        # Create the agent crew
        self.setup_crew()
    
    def setup_crew(self):
        """Set up the CrewAI agents and crew for stackranking management"""
        # Create stackranking-specific tools
        stackrank_tool = StackrankCandidatesTool()
        send_offers_tool = SendOfferLettersTool()
        get_results_tool = GetStackrankResultsTool()
        
        # Create specialized stackranking agent
        self.stackrank_manager = Agent(
            role="Candidate Stackranking Manager",
            goal="Efficiently stackrank candidates based on interview performance and manage offer letter distribution",
            backstory="""You are an expert talent acquisition specialist with deep experience in candidate 
            evaluation and selection processes. You excel at analyzing interview performance data, ranking 
            candidates objectively based on cumulative scores, and managing the entire offer letter process. 
            Your role is crucial in ensuring the best candidates are selected and onboarded efficiently.""",
            verbose=True,
            allow_delegation=False,  # No delegation needed for focused stackranking tasks
            llm=llm,
            tools=[stackrank_tool, send_offers_tool, get_results_tool]
        )
        
        # Create the stackranking crew
        self.crew = Crew(
            agents=[self.stackrank_manager],
            tasks=[],  # Tasks will be created dynamically
            verbose=True,
            process=Process.sequential
        )
    
    def process_stackrank_query(self, query: str, session_id: str) -> Dict[str, Any]:
        """
        Process a stackranking-related query using the specialized stackranking agent system
        
        Args:
            query: The user's stackranking query text
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
            "agent": "Candidate Stackranking Manager",
            "thought": f"Analyzing stackranking request: {query}",
            "timestamp": datetime.now().isoformat()
        }
        thoughts.append(analysis_thought)
        
        try:
            # Parse the stackranking request using LLM
            parsing_thought = {
                "agent": "Candidate Stackranking Manager", 
                "thought": "Extracting structured information from the stackranking request",
                "timestamp": datetime.now().isoformat()
            }
            thoughts.append(parsing_thought)
            
            parsed_request = parse_stackrank_request(query)
            
            # Validation thought
            validation_thought = {
                "agent": "Candidate Stackranking Manager",
                "thought": f"Extracted parameters - Job Role: {parsed_request.get('job_role_name')}, Action: {parsed_request.get('action_type')}, Send Offers: {parsed_request.get('send_offer_letters')}",
                "timestamp": datetime.now().isoformat()
            }
            thoughts.append(validation_thought)
            
            # Create a task for stackranking
            if parsed_request.get('action_type') == 'stackrank':
                task_description = f"""
                Process stackranking request based on the following parsed information:
                
                Original Request: {query}
                
                Parsed Parameters:
                - Job Role: {parsed_request.get('job_role_name')}
                - Top Percentage: {parsed_request.get('top_percentage')}%
                - Compensation: {parsed_request.get('compensation_offered', 'Not specified')}
                - Joining Date: {parsed_request.get('joining_date', 'Not specified')}
                - Send Offer Letters: {parsed_request.get('send_offer_letters')}
                
                Process:
                1. Use StackrankCandidates tool to rank candidates and select top performers
                2. If send_offer_letters is true, use SendOfferLetters tool to send offers
                3. Provide comprehensive summary of the entire process
                
                Ensure all parameters are correctly applied and provide detailed feedback on the results.
                """
            else:
                task_description = f"""
                Process the following request: {query}
                
                Use appropriate tools to:
                - Get stackranking results if requested
                - Send offer letters if requested
                - Provide comprehensive information about candidate status
                """
            
            stackrank_task = Task(
                description=task_description,
                expected_output="Comprehensive report of stackranking process and results",
                agent=self.stackrank_manager
            )
            
            # Create a temporary crew for this task
            stackrank_crew = Crew(
                agents=[self.stackrank_manager],
                tasks=[stackrank_task],
                verbose=True,
                process=Process.sequential
            )
            
            # Processing thought
            processing_thought = {
                "agent": "Candidate Stackranking Manager",
                "thought": "Processing stackranking and offer management request",
                "timestamp": datetime.now().isoformat()
            }
            thoughts.append(processing_thought)
            
            # Execute the stackranking process
            crew_result = stackrank_crew.kickoff()
            
            # Convert CrewOutput to string
            if hasattr(crew_result, 'raw'):
                result = crew_result.raw
            elif hasattr(crew_result, 'result'):
                result = crew_result.result
            else:
                result = str(crew_result)
            
            # Completion thought
            completion_thought = {
                "agent": "Candidate Stackranking Manager",
                "thought": "Stackranking process completed successfully",
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
                "primary_agent": "Candidate Stackranking Manager",
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Error processing stackrank query: {e}")
            error_thought = {
                "agent": "Candidate Stackranking Manager",
                "thought": f"Error occurred: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
            thoughts.append(error_thought)
            
            return {
                "response": f"I apologize, but I encountered an error while processing your stackranking request: {str(e)}",
                "thought_process": thoughts,
                "primary_agent": "Candidate Stackranking Manager",
                "session_id": session_id
            }


# Create a singleton instance
_stackrank_agent_system = None

def get_stackrank_agent_system() -> StackrankAgentSystem:
    """Get the singleton stackranking agent system instance"""
    global _stackrank_agent_system
    if _stackrank_agent_system is None:
        _stackrank_agent_system = StackrankAgentSystem()
    return _stackrank_agent_system
