"""
LangGraph Agent System for Interview Scheduler
"""
import os
import uuid
from typing import Dict, Any, List, Annotated, TypedDict, Sequence, Tuple
from datetime import datetime
import json
import logging

from langchain.prompts import ChatPromptTemplate
from langchain.schema import Document
from langchain.chat_models import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
# Removed problematic import

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get OpenAI API Key from environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY not found in environment. Using default key.")
    # Default key from the project setup
    OPENAI_API_KEY = "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"

# Initialize LLM model
llm = ChatOpenAI(
    openai_api_key=OPENAI_API_KEY,
    model_name="gpt-4o",
    temperature=0.2
)

# Define agent roles
JOB_ANALYZER_SYSTEM_PROMPT = """You are an expert job analyzer. Your role is to analyze job postings 
and extract key requirements and skills needed for the job. Provide insights into the job market trends 
and suggest improvements to the job description.
"""

CANDIDATE_SCREENER_SYSTEM_PROMPT = """You are a candidate screening specialist. Your role is to 
evaluate candidate profiles against job requirements. Identify the best candidates for each role 
and provide reasoning for your selections.
"""

INTERVIEW_PLANNER_SYSTEM_PROMPT = """You are an interview planning strategist. Your role is to 
design effective interview processes tailored to specific job positions. Create interview rounds, 
specify questions for each round, and provide evaluation criteria.
"""

SCHEDULER_SYSTEM_PROMPT = """You are an interview scheduling coordinator. Your role is to efficiently 
schedule interviews considering availability of all parties involved. Suggest optimal time slots and 
handle scheduling conflicts.
"""

# Define state schema
class InterviewState(TypedDict):
    """State for the interview workflow"""
    messages: Annotated[Sequence[BaseMessage], "Messages in the conversation so far"]
    job_data: Annotated[Dict[str, Any], "Job posting data"]
    candidate_data: Annotated[Dict[str, Any], "Candidate data"]
    analysis: Annotated[Dict[str, Any], "Analysis of the job posting"]
    interview_plan: Annotated[Dict[str, Any], "Interview process plan"]
    interview_schedule: Annotated[Dict[str, Any], "Interview schedule"]
    current_agent: Annotated[str, "Current agent in the workflow"]
    next_agent: Annotated[str, "Next agent to process"]
    thoughts: Annotated[List[Dict[str, Any]], "Thoughts from agents during processing"]
    output: Annotated[str, "Final output from the workflow"]


def initialize_interview_state() -> InterviewState:
    """Initialize the state for the interview workflow"""
    return {
        "messages": [],
        "job_data": {},
        "candidate_data": {},
        "analysis": {},
        "interview_plan": {},
        "interview_schedule": {},
        "current_agent": "",
        "next_agent": "job_analyzer",
        "thoughts": [],
        "output": ""
    }


class InterviewAgentGraph:
    """LangGraph-based agent for interview scheduling workflow"""
    
    def __init__(self):
        """Initialize the interview agent graph"""
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the state graph for the interview workflow"""
        # Define graph nodes
        workflow = StateGraph(InterviewState)
        
        # Add agent nodes
        workflow.add_node("job_analyzer", self.job_analyzer)
        workflow.add_node("candidate_screener", self.candidate_screener)
        workflow.add_node("interview_planner", self.interview_planner)
        workflow.add_node("scheduler", self.scheduler)
        workflow.add_node("router", self.route_agents)
        
        # Define the workflow edges
        workflow.set_entry_point("router")
        
        # From router to specific agents
        workflow.add_edge("router", "job_analyzer")
        workflow.add_edge("router", "candidate_screener")
        workflow.add_edge("router", "interview_planner")
        workflow.add_edge("router", "scheduler")
        workflow.add_edge("router", END)
        
        # From agents back to router
        workflow.add_edge("job_analyzer", "router")
        workflow.add_edge("candidate_screener", "router")
        workflow.add_edge("interview_planner", "router")
        workflow.add_edge("scheduler", "router")
        
        # Compile the workflow
        return workflow.compile()
    
    def job_analyzer(self, state: InterviewState) -> InterviewState:
        """Job analyzer agent"""
        logger.info("Job Analyzer agent activated")
        
        # Add thought
        thought = {
            "agent": "Job Analysis Expert",
            "thought": f"Analyzing job data: {state['job_data'].get('job_role_name', 'Unknown Job')}",
            "timestamp": datetime.now().isoformat()
        }
        state["thoughts"].append(thought)
        
        # Prepare prompt
        job_data = state["job_data"]
        job_title = job_data.get("job_role_name", "Unknown Job")
        job_description = job_data.get("job_description", "No description available")
        years_experience = job_data.get("years_of_experience_needed", "Not specified")
        
        messages = [
            SystemMessage(content=JOB_ANALYZER_SYSTEM_PROMPT),
            HumanMessage(content=f"""Please analyze the following job posting:
            
Job Title: {job_title}
Years of Experience: {years_experience}
Job Description: {job_description}

Please provide:
1. Key skills and requirements extracted from the job posting
2. Suggestions for improving the job description
3. Ideal candidate profile for this role
""")
        ]
        
        # Get analysis from LLM
        response = llm.invoke(messages)
        analysis = response.content
        
        # Add thought about the analysis
        thought = {
            "agent": "Job Analysis Expert",
            "thought": f"Completed job analysis: Extracted key requirements and created ideal candidate profile",
            "timestamp": datetime.now().isoformat()
        }
        state["thoughts"].append(thought)
        
        # Update state
        state["analysis"] = {
            "job_title": job_title,
            "analysis_text": analysis,
            "timestamp": datetime.now().isoformat()
        }
        state["messages"].append(SystemMessage(content="Job Analysis completed"))
        state["messages"].append(AIMessage(content=analysis))
        state["current_agent"] = "job_analyzer"
        state["next_agent"] = "candidate_screener"
        
        return state
    
    def candidate_screener(self, state: InterviewState) -> InterviewState:
        """Candidate screener agent"""
        logger.info("Candidate Screener agent activated")
        
        # Add thought
        thought = {
            "agent": "Candidate Screening Specialist",
            "thought": "Evaluating candidates against job requirements",
            "timestamp": datetime.now().isoformat()
        }
        state["thoughts"].append(thought)
        
        # Prepare prompt
        job_analysis = state["analysis"].get("analysis_text", "No analysis available")
        candidate_data = state["candidate_data"]
        
        if not candidate_data:
            # Create sample candidate data for demonstration
            candidate_data = {
                "candidates": [
                    {
                        "id": str(uuid.uuid4()),
                        "name": "John Smith",
                        "email": "john.smith@example.com",
                        "experience": "5 years",
                        "skills": ["Python", "React", "Node.js", "AWS"],
                        "education": "Master's in Computer Science"
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Sarah Johnson",
                        "email": "sarah.johnson@example.com",
                        "experience": "7 years",
                        "skills": ["Python", "Data Science", "Machine Learning", "SQL"],
                        "education": "PhD in Computer Science"
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Michael Chen",
                        "email": "michael.chen@example.com",
                        "experience": "3 years",
                        "skills": ["JavaScript", "React", "CSS", "HTML"],
                        "education": "Bachelor's in Software Engineering"
                    }
                ]
            }
            state["candidate_data"] = candidate_data
        
        candidates_str = json.dumps(candidate_data, indent=2)
        
        messages = [
            SystemMessage(content=CANDIDATE_SCREENER_SYSTEM_PROMPT),
            HumanMessage(content=f"""Based on the job analysis and requirements below, evaluate the candidate profiles and select the most suitable candidates:
            
Job Analysis:
{job_analysis}

Candidate Profiles:
{candidates_str}

Please provide:
1. A ranked list of candidates from most to least suitable
2. A brief explanation for each ranking
3. Suggested interview focus areas for each candidate
""")
        ]
        
        # Get screening from LLM
        response = llm.invoke(messages)
        screening_results = response.content
        
        # Add thought about the screening
        thought = {
            "agent": "Candidate Screening Specialist",
            "thought": "Completed candidate screening and ranking",
            "timestamp": datetime.now().isoformat()
        }
        state["thoughts"].append(thought)
        
        # Update state
        state["candidate_data"]["screening_results"] = screening_results
        state["messages"].append(SystemMessage(content="Candidate Screening completed"))
        state["messages"].append(AIMessage(content=screening_results))
        state["current_agent"] = "candidate_screener"
        state["next_agent"] = "interview_planner"
        
        return state
    
    def interview_planner(self, state: InterviewState) -> InterviewState:
        """Interview planner agent"""
        logger.info("Interview Planner agent activated")
        
        # Add thought
        thought = {
            "agent": "Interview Planning Strategist",
            "thought": "Designing interview process based on job requirements and candidate profiles",
            "timestamp": datetime.now().isoformat()
        }
        state["thoughts"].append(thought)
        
        # Prepare prompt
        job_title = state["job_data"].get("job_role_name", "Unknown Job")
        job_analysis = state["analysis"].get("analysis_text", "No analysis available")
        screening_results = state["candidate_data"].get("screening_results", "No screening results available")
        
        messages = [
            SystemMessage(content=INTERVIEW_PLANNER_SYSTEM_PROMPT),
            HumanMessage(content=f"""Design an interview process for the position of {job_title} based on the provided job analysis and candidate screening results:
            
Job Analysis:
{job_analysis}

Candidate Screening Results:
{screening_results}

Please provide:
1. Recommended number of interview rounds
2. Focus area for each round (technical, behavioral, etc.)
3. Specific interview questions for each round
4. Evaluation criteria for each round
5. Required interviewers (roles/expertise) for each round
""")
        ]
        
        # Get interview plan from LLM
        response = llm.invoke(messages)
        interview_plan = response.content
        
        # Add thought about the interview plan
        thought = {
            "agent": "Interview Planning Strategist",
            "thought": "Completed interview process design with rounds, questions, and evaluation criteria",
            "timestamp": datetime.now().isoformat()
        }
        state["thoughts"].append(thought)
        
        # Update state
        state["interview_plan"] = {
            "plan_text": interview_plan,
            "timestamp": datetime.now().isoformat()
        }
        state["messages"].append(SystemMessage(content="Interview Planning completed"))
        state["messages"].append(AIMessage(content=interview_plan))
        state["current_agent"] = "interview_planner"
        state["next_agent"] = "scheduler"
        
        return state
    
    def scheduler(self, state: InterviewState) -> InterviewState:
        """Interview scheduler agent"""
        logger.info("Scheduler agent activated")
        
        # Add thought
        thought = {
            "agent": "Interview Scheduling Coordinator",
            "thought": "Creating interview schedule based on interview plan",
            "timestamp": datetime.now().isoformat()
        }
        state["thoughts"].append(thought)
        
        # Prepare prompt
        job_title = state["job_data"].get("job_role_name", "Unknown Job")
        interview_plan = state["interview_plan"].get("plan_text", "No interview plan available")
        candidates = state["candidate_data"].get("candidates", [])
        candidate_names = [c.get("name", "Unknown") for c in candidates]
        
        messages = [
            SystemMessage(content=SCHEDULER_SYSTEM_PROMPT),
            HumanMessage(content=f"""Create an interview schedule for the position of {job_title} based on the interview plan:
            
Interview Plan:
{interview_plan}

Candidates to schedule:
{", ".join(candidate_names)}

Please provide:
1. Proposed interview schedule for each candidate
2. Estimated duration for each interview round
3. Required resources for each interview (meeting room, online meeting link, etc.)
4. Guidelines for interviewers to prepare for the interviews
5. Contingency plans for potential scheduling conflicts
""")
        ]
        
        # Get schedule from LLM
        response = llm.invoke(messages)
        schedule = response.content
        
        # Add thought about the schedule
        thought = {
            "agent": "Interview Scheduling Coordinator",
            "thought": "Completed interview scheduling with proposed times and resources",
            "timestamp": datetime.now().isoformat()
        }
        state["thoughts"].append(thought)
        
        # Update state
        state["interview_schedule"] = {
            "schedule_text": schedule,
            "timestamp": datetime.now().isoformat(),
            "status": "proposed"  # This would become 'confirmed' after actual scheduling
        }
        state["messages"].append(SystemMessage(content="Interview Scheduling completed"))
        state["messages"].append(AIMessage(content=schedule))
        state["current_agent"] = "scheduler"
        state["next_agent"] = "output_generator"
        
        # Add final compiled output
        state["output"] = self._generate_final_output(state)
        
        return state
    
    def _generate_final_output(self, state: InterviewState) -> str:
        """Generate the final output from all agent contributions"""
        job_title = state["job_data"].get("job_role_name", "Unknown Job")
        
        final_output = f"""# Complete Interview Process for {job_title}

## Job Analysis
{state["analysis"].get("analysis_text", "No analysis available")}

## Candidate Screening Results
{state["candidate_data"].get("screening_results", "No screening results available")}

## Interview Plan
{state["interview_plan"].get("plan_text", "No interview plan available")}

## Interview Schedule
{state["interview_schedule"].get("schedule_text", "No schedule available")}
"""
        
        return final_output
    
    def route_agents(self, state: InterviewState) -> str:
        """Route to the next agent in the workflow"""
        next_agent = state["next_agent"]
        
        if next_agent == "output_generator":
            return END
        
        return next_agent
    
    def process_query(self, query: str, job_data: Dict[str, Any], candidate_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process a user query through the interview workflow
        
        Args:
            query: User query string
            job_data: Job posting data
            candidate_data: Optional candidate data
            
        Returns:
            The result of the workflow
        """
        # Initialize state
        state = initialize_interview_state()
        state["messages"].append(HumanMessage(content=query))
        state["job_data"] = job_data
        if candidate_data:
            state["candidate_data"] = candidate_data
        
        # Generate a unique session id
        session_id = str(uuid.uuid4())
        config = {"configurable": {"session_id": session_id}}
        
        # Run the workflow
        result = self.graph.invoke(state, config)
        
        # Add thoughts to result for UI display
        result["thought_process"] = state["thoughts"]
        
        return result


# Create a singleton instance
graph_agent = InterviewAgentGraph()


def get_langgraph_agent() -> InterviewAgentGraph:
    """Get the singleton langgraph agent instance"""
    return graph_agent
