import os
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from firebase_admin import get_app
import socketio

from app.api import job_routes, calendar_routes, auth_routes, candidate_routes, interview_routes, response_routes, final_selection_routes, chatbot_routes, agent_routes
from app.agents.interview_agent import InterviewAgentSystem, create_interview_crew

# Load environment variables
load_dotenv()

# Get Firebase app (it's initialized in app/database/firebase_db.py)
try:
    firebase_app = get_app()
except ValueError:
    print("Firebase app not initialized. It will be initialized when accessing the database.")
    firebase_app = None

# Create FastAPI app
app = FastAPI(
    title="Interview Scheduler Agent API",
    description="API for job posting and interview scheduling",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers
app.include_router(job_routes.router)
app.include_router(calendar_routes.router)
app.include_router(auth_routes.router)
app.include_router(candidate_routes.router)
app.include_router(interview_routes.router)
app.include_router(response_routes.router)
app.include_router(final_selection_routes.router)
app.include_router(chatbot_routes.router)
app.include_router(agent_routes.router)

# Mount the Socket.IO app
app.mount("/socket.io", agent_routes.socket_app)

# Initialize interview agent system
interview_system = InterviewAgentSystem()


@app.get("/")
def root():
    """Root endpoint"""
    return {"message": "Welcome to the Interview Scheduler Agent API"}


@app.get("/chatbot")
def chatbot_demo():
    """Serve the chatbot demo page"""
    return FileResponse("app/static/chatbot_demo.html")

@app.get("/agent")
def agent_interface():
    """Serve the agent interface page"""
    return FileResponse("app/static/agent_interface.html")


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "api": "Interview Scheduler Agent API", "version": "1.0.0"}


@app.post("/analyze-job/{job_id}")
async def analyze_job(job_id: str):
    """
    Analyze a job posting using AI agents
    """
    from app.services.job_service import JobService

    # Get job posting
    job_posting = JobService.get_job_posting(job_id)
    if not job_posting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job posting with ID {job_id} not found",
        )
    
    # Convert Pydantic model to dict
    job_data = job_posting.dict()
    
    # Run interview process
    try:
        result = interview_system.run_interview_process(job_data)
        return {
            "job_id": job_id,
            "analysis": result.job_data.get("analysis", "No analysis available"),
            "questions": result.questions,
            "evaluation": result.evaluations,
            "schedule": result.schedule
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing job: {str(e)}",
        )


@app.post("/create-interview-crew/{job_id}")
async def create_job_crew(job_id: str):
    """
    Create a CrewAI crew for a job posting
    """
    from app.services.job_service import JobService

    # Get job posting
    job_posting = JobService.get_job_posting(job_id)
    if not job_posting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job posting with ID {job_id} not found",
        )
    
    # Convert Pydantic model to dict
    job_data = job_posting.dict()
    
    try:
        # Create interview crew
        crew = create_interview_crew(job_data)
        
        # Run the crew
        result = crew.kickoff()
        
        return {
            "job_id": job_id,
            "crew_result": result,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating interview crew: {str(e)}",
        )


if __name__ == "__main__":
    import uvicorn
    
    # Run the application
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )
