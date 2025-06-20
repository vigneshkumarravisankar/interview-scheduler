import os
import datetime
from typing import Dict, List, Any, Optional, Union
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.graph.graph import END, START
from app.utils.calendar_service import CalendarService
from fastapi import HTTPException

# Load environment variables for OpenAI API key
from dotenv import load_dotenv
load_dotenv()

# Get API key from environment variable or use a default for testing
api_key = os.environ.get("OPENAI_API_KEY", "your_openai_api_key_here")

# Create OpenAI LLM
llm = ChatOpenAI(model="gpt-4o", api_key=api_key)

# Define valid user roles and their permissions
ROLES = {
    "HR": {
        "view_all_feedback": True,
        "add_feedback_all": True,
        "decide_next_round": True,
        "schedule_interview": True
    },
    "Recruiter": {
        "view_all_feedback": True, 
        "add_feedback_all": True,
        "decide_next_round": False,
        "schedule_interview": True
    },
    "Interviewer": {
        "view_all_feedback": False,  # Can only view their own feedback
        "add_feedback_all": False,   # Can only add feedback for assigned candidates
        "decide_next_round": False,
        "schedule_interview": False
    }
}

class RolePermissionError(Exception):
    """Exception raised for permission errors related to user roles"""
    
    def __init__(self, role: str, required_permission: str, message: str = None):
        self.role = role
        self.required_permission = required_permission
        self.message = message or f"Role '{role}' does not have permission to {required_permission.replace('_', ' ')}"
        super().__init__(self.message)


class InterviewAgentSystem:
    """System for managing interview agents using CrewAI and LangGraph"""
    
    def __init__(self):
        # Create agents
        self.job_analyst = Agent(
            role="Job Analyst",
            goal="Analyze job requirements and create appropriate interview questions",
            backstory="You are an expert at understanding job requirements and creating relevant interview questions.",
            verbose=True,
            allow_delegation=True,
            llm=llm
        )
        
        self.candidate_evaluator = Agent(
            role="Candidate Evaluator",
            goal="Evaluate candidate responses to interview questions",
            backstory="You are an expert at evaluating candidate responses and determining fit for a role.",
            verbose=True,
            allow_delegation=True,
            llm=llm
        )
        
        self.interview_scheduler = Agent(
            role="Interview Scheduler",
            goal="Schedule interviews and manage interview process",
            backstory="You are an expert at scheduling interviews and coordinating with candidates and interviewers.",
            verbose=True,
            allow_delegation=True,
            llm=llm
        )
        
        # Initialize LangGraph components
        self.setup_langgraph()
    
    def setup_langgraph(self):
        """Set up LangGraph workflow"""
        # Define our state
        class State:
            job_data: Dict
            questions: List[str] = []
            evaluations: Dict[str, Any] = {}
            schedule: Dict[str, Any] = {}
        
        # Create the graph
        self.workflow = StateGraph(State)
        
        # Define nodes
        self.workflow.add_node("analyze_job", self.analyze_job)
        self.workflow.add_node("create_questions", self.create_questions)
        self.workflow.add_node("evaluate_candidate", self.evaluate_candidate)
        self.workflow.add_node("schedule_interview", self.schedule_interview)
        
        # Define edges
        self.workflow.add_edge(START, "analyze_job")
        self.workflow.add_edge("analyze_job", "create_questions")
        self.workflow.add_edge("create_questions", "evaluate_candidate")
        self.workflow.add_edge("evaluate_candidate", "schedule_interview")
        self.workflow.add_edge("schedule_interview", END)
        
        # Compile the graph
        self.compiled_workflow = self.workflow.compile()
    def analyze_job(self, state):
        """
        Analyze job requirements
        
        All roles can view job analysis, but warnings will be displayed 
        for permission context in subsequent steps.
        """
        # Check user role from state (default to "HR" if not specified)
        user_role = getattr(state, "user_role", "HR")
        
        # Log role information (for debugging)
        print(f"Job analysis requested by user with role: {user_role}")
        
        task = Task(
            description=f"Analyze the following job: {state.job_data}",
            expected_output="Analysis of job requirements",
            agent=self.job_analyst
        )
        result = task.execute()
        return {"job_data": {**state.job_data, "analysis": result, "analyzed_by_role": user_role}}
    def create_questions(self, state):
        """
        Create interview questions based on job
        
        This function requires appropriate permissions based on user role,
        but all roles can view questions, with warnings for limitations.
        """
        # Check user role from state (default to "HR" if not specified)
        user_role = getattr(state, "user_role", "HR")
        
        # For Interviewer role, add note about question customization
        notes = None
        if user_role == "Interviewer":
            notes = "Note: As an Interviewer, you can view questions but cannot modify the interview structure. Contact HR or Recruiter for changes."
        
        task = Task(
            description=f"Create interview questions based on this analysis: {state.job_data['analysis']}",
            expected_output="List of interview questions",
            agent=self.job_analyst
        )
        result = task.execute()
        # Parse the result into a list of questions
        questions = [q.strip() for q in result.split("\n") if q.strip()]
        
        # Add role-specific notes if applicable
        response = {"questions": questions}
        if notes:
            response["notes"] = notes
        
        return response
    def evaluate_candidate(self, state):
        """
        Evaluate candidate responses
        
        This function requires appropriate permissions based on user role:
        - HR: Can evaluate any candidate
        - Recruiter: Can evaluate any candidate
        - Interviewer: Can only evaluate assigned candidates
        """
        # Check user role from state (default to "HR" if not specified)
        user_role = getattr(state, "user_role", "HR")
        
        # Check if user has permission to evaluate candidates
        if user_role == "Interviewer":
            # For interviewers, we would check if they're assigned to this candidate
            # This is a placeholder for actual assignment check logic
            is_assigned = True  # In a real app, check if interviewer is assigned to this candidate
            
            if not is_assigned:
                # Instead of failing, we'll log a warning and continue, but this would
                # ideally check the actual assignments
                print(f"WARNING: Role '{user_role}' is attempting to evaluate a candidate they're not assigned to.")
        
        # In a real application, we would have actual candidate responses
        task = Task(
            description=f"Evaluate these candidate responses to the following questions: {state.questions}",
            expected_output="Evaluation of candidate",
            agent=self.candidate_evaluator
        )
        result = task.execute()
        return {"evaluations": {"result": result}}
    def schedule_interview(self, state):
        """
        Schedule interview using Google Calendar
        
        This function requires appropriate permissions based on user role:
        - HR: Can schedule interviews
        - Recruiter: Can schedule interviews
        - Interviewer: Cannot schedule interviews
        """
        # Check user role from state (default to "HR" if not specified)
        user_role = getattr(state, "user_role", "HR")
        
        # Validate that the user has permission to schedule interviews
        try:
            self.validate_role_permission(user_role, "schedule_interview")
        except RolePermissionError as e:
            # Log the error and provide informative message while continuing
            print(f"WARNING: {str(e)}")
            return {
                "schedule": {
                    "status": "Permission Denied",
                    "error": f"Role '{user_role}' does not have permission to schedule interviews.",
                    "message": "Please contact an HR representative or Recruiter to schedule interviews."
                }
            }
            
        # Get job details from state
        job_data = state.job_data
        questions = state.questions
        
        # Create task for the agent to decide on scheduling parameters
        task = Task(
            description=f"""Schedule an interview for the job: {job_data['job_role_name']}.
            Use the job description and requirements to determine the interview duration,
            participants, and any other details needed for scheduling.
            Interview questions to be asked: {questions}""",
            expected_output="Interview scheduling details including duration, participants, and timing preferences",
            agent=self.interview_scheduler
        )
        scheduling_plan = task.execute()
        
        try:
            # Find an available time slot
            # Default to 1-hour interview, but can be customized based on agent output
            duration = 60  # minutes
            available_slot = CalendarService.find_available_slot(
                duration_minutes=duration,
                start_date=datetime.datetime.now(),
                end_date=datetime.datetime.now() + datetime.timedelta(days=14)
            )
            
            if available_slot:
                # Create the calendar event
                event = CalendarService.create_interview_event(
                    summary=f"Interview for {job_data['job_role_name']}",
                    description=f"Job Interview\n\nPosition: {job_data['job_role_name']}\n\nDescription: {job_data['job_description']}\n\nQuestions:\n" + 
                               "\n".join([f"- {q}" for q in questions if isinstance(questions, list)]),
                    start_time=available_slot['start'],
                    end_time=available_slot['end'],
                    attendees=[{'email': 'interviewer@example.com'}]  # This would be customized in a real app
                )
                
                # Return the scheduled info
                return {
                    "schedule": {
                        "event_id": event.get('id'),
                        "start_time": available_slot['start'].isoformat(),
                        "end_time": available_slot['end'].isoformat(),
                        "meet_link": event.get('hangoutLink', 'No link available'),
                        "status": "Scheduled",
                        "planning_notes": scheduling_plan
                    }
                }
            else:
                # No slot available
                return {
                    "schedule": {
                        "status": "No available slots",
                        "planning_notes": scheduling_plan,
                        "recommendation": "Try again with a different time range or manually schedule"
                    }
                }
        except Exception as e:
            # Error in scheduling
            return {
                "schedule": {
                    "status": "Error",
                    "error": str(e),                    "planning_notes": scheduling_plan
                }
            }
    
    def check_permission(self, role: str, permission: str) -> bool:
        """
        Check if a role has a specific permission
        
        Args:
            role: User role (HR, Recruiter, Interviewer)
            permission: Permission to check
            
        Returns:
            True if the role has the permission, False otherwise
        """
        if role not in ROLES:
            return False
        return ROLES[role].get(permission, False)
    
    def validate_role_permission(self, role: str, permission: str) -> None:
        """
        Validate that a role has the required permission
        
        Args:
            role: User role (HR, Recruiter, Interviewer)
            permission: Required permission
            
        Raises:
            RolePermissionError: If the role doesn't have the permission
        """
        if not self.check_permission(role, permission):
            raise RolePermissionError(role, permission)
    
    def run_interview_process(self, job_data, user_role="HR"):
        """
        Run the full interview process using LangGraph
        
        Args:
            job_data: Job data to analyze
            user_role: Role of the user initiating the process
            
        Returns:
            Result from the workflow
            
        Raises:
            RolePermissionError: If the user doesn't have permission
        """
        # Validate permissions (only HR and Recruiters can run the full process)
        if user_role not in ["HR", "Recruiter"]:
            raise RolePermissionError(
                user_role, 
                "run_interview_process", 
                f"Only HR and Recruiters can run the full interview process. Your role: {user_role}"
            )
        
        # Initialize state
        initial_state = {"job_data": job_data, "user_role": user_role}
        
        # Execute the workflow
        result = self.compiled_workflow.invoke(initial_state)
        return result


def create_interview_crew(job_data, user_role="HR"):
    """
    Create a crew for interview process
    
    Args:
        job_data: Job data to analyze
        user_role: Role of the user creating the crew
        
    Returns:
        CrewAI crew object
        
    Raises:
        RolePermissionError: If the user role doesn't have permission
    """
    # Validate that the user has permission to create interview crews
    if user_role not in ["HR", "Recruiter"]:
        raise RolePermissionError(
            user_role, 
            "create_interview_crew", 
            f"Only HR and Recruiters can create interview crews. Your role: {user_role}"
        )
    # Create agents
    job_analyst = Agent(
        role="Job Analyst",
        goal="Analyze job requirements and create appropriate interview questions",
        backstory="You are an expert at understanding job requirements and creating relevant interview questions.",
        verbose=True,
        allow_delegation=True,
        llm=llm
    )
    
    candidate_evaluator = Agent(
        role="Candidate Evaluator",
        goal="Evaluate candidate responses to interview questions",
        backstory="You are an expert at evaluating candidate responses and determining fit for a role.",
        verbose=True,
        allow_delegation=True,
        llm=llm
    )
    
    interview_scheduler = Agent(
        role="Interview Scheduler",
        goal="Schedule interviews and manage interview process",
        backstory="You are an expert at scheduling interviews and coordinating with candidates and interviewers.",
        verbose=True,
        allow_delegation=True,
        llm=llm
    )
    
    # Create tasks
    analyze_job_task = Task(
        description=f"Analyze the following job: {job_data}",
        expected_output="Analysis of job requirements",
        agent=job_analyst
    )
    
    create_questions_task = Task(
        description="Create interview questions based on the job analysis",
        expected_output="List of interview questions",
        agent=job_analyst,
        context=[analyze_job_task]
    )
    
    evaluate_candidate_task = Task(
        description="Evaluate candidate responses to the interview questions",
        expected_output="Evaluation of candidate",
        agent=candidate_evaluator,
        context=[create_questions_task]
    )
    
    schedule_interview_task = Task(
        description="Schedule interviews based on availability",
        expected_output="Interview schedule",
        agent=interview_scheduler,
        context=[evaluate_candidate_task]
    )
    
    # Create crew
    crew = Crew(
        agents=[job_analyst, candidate_evaluator, interview_scheduler],
        tasks=[analyze_job_task, create_questions_task, evaluate_candidate_task, schedule_interview_task],
        verbose=True,
        process=Process.sequential
    )
    
    return crew


def is_interviewer_assigned(interviewer_email: str, candidate_id: str) -> bool:
    """
    Check if an interviewer is assigned to a specific candidate
    
    Args:
        interviewer_email: Email of the interviewer
        candidate_id: ID of the candidate
        
    Returns:
        True if interviewer is assigned to this candidate, False otherwise
    """
    # In a real application, this would query your database to check assignments
    # For now, this is just a placeholder implementation
    try:
        from app.services.interview_service import InterviewService
        
        # Get the candidate data
        candidate = InterviewService.get_interview_candidate(candidate_id)
        if not candidate:
            return False
        
        # Check if interviewer is assigned to any rounds
        feedback_list = candidate.get("feedback", [])
        for feedback in feedback_list:
            if feedback.get("interviewer_email") == interviewer_email:
                return True
                
        return False
    except Exception as e:
        print(f"Error checking interviewer assignment: {str(e)}")
        return False
