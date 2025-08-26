#commit interview_agent from stackblitz commit
#commit2 interview_agent from stackblitz commit




import os
import datetime
from typing import Dict, List, Any, Optional
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.graph.graph import END, START
from app.utils.calendar_service import CalendarService

# Load environment variables for OpenAI API key
from dotenv import load_dotenv
load_dotenv()

# Create OpenAI LLM
llm = ChatOpenAI(model="gpt-4o")


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
        """Analyze job requirements"""
        task = Task(
            description=f"Analyze the following job: {state.job_data}",
            expected_output="Analysis of job requirements",
            agent=self.job_analyst
        )
        result = task.execute()
        return {"job_data": {**state.job_data, "analysis": result}}
    
    def create_questions(self, state):
        """Create interview questions based on job"""
        task = Task(
            description=f"Create interview questions based on this analysis: {state.job_data['analysis']}",
            expected_output="List of interview questions",
            agent=self.job_analyst
        )
        result = task.execute()
        # Parse the result into a list of questions
        questions = [q.strip() for q in result.split("\n") if q.strip()]
        return {"questions": questions}
    
    def evaluate_candidate(self, state):
        """Evaluate candidate responses"""
        # In a real application, we would have actual candidate responses
        task = Task(
            description=f"Evaluate these candidate responses to the following questions: {state.questions}",
            expected_output="Evaluation of candidate",
            agent=self.candidate_evaluator
        )
        result = task.execute()
        return {"evaluations": {"result": result}}
    
    def schedule_interview(self, state):
        """Schedule interview using Google Calendar"""
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
                    "error": str(e),
                    "planning_notes": scheduling_plan
                }
            }
    
    def run_interview_process(self, job_data):
        """Run the full interview process using LangGraph"""
        # Initialize state
        initial_state = {"job_data": job_data}
        
        # Execute the workflow
        result = self.compiled_workflow.invoke(initial_state)
        return result


def create_interview_crew(job_data):
    """Create a crew for interview process"""
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
