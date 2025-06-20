"""
Example script demonstrating how to use the Interview Scheduler Agent API
"""
import requests
import json
import os
import time
from pprint import pprint

# Configuration
API_BASE_URL = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}

def print_section(title):
    """Print a section title"""
    print("\n" + "="*80)
    print(f" {title} ".center(80, "="))
    print("="*80 + "\n")

def print_response(response, label="Response"):
    """Pretty print an API response"""
    print(f"\n--- {label} ---")
    print(f"Status Code: {response.status_code}")
    try:
        pprint(response.json())
    except:
        print(response.text)
    print("---\n")

def create_job_posting():
    """Create a job posting"""
    print_section("CREATE JOB POSTING")
    
    job_data = {
        "job_role_name": "Senior Python Developer",
        "job_description": """
We are seeking a Senior Python Developer to join our team. The ideal candidate will have:
- 5+ years of experience with Python
- Strong knowledge of FastAPI, Django, or Flask
- Experience with database design and SQL
- Familiarity with AWS or other cloud platforms
- Excellent communication skills and ability to work in a team
        """,
        "years_of_experience_needed": "5+ years",
        "location": "Remote (US Time Zones)"
    }
    
    print("Creating job posting with data:")
    pprint(job_data)
    
    response = requests.post(f"{API_BASE_URL}/jobs/", json=job_data, headers=HEADERS)
    print_response(response)
    
    if response.status_code == 201:
        job_id = response.json().get("job_id")
        print(f"Job created successfully with ID: {job_id}")
        return job_id
    else:
        print("Failed to create job posting")
        return None

def get_job_posting(job_id):
    """Get a job posting by ID"""
    print_section(f"GET JOB POSTING: {job_id}")
    
    response = requests.get(f"{API_BASE_URL}/jobs/{job_id}", headers=HEADERS)
    print_response(response)
    
    if response.status_code == 200:
        return response.json()
    else:
        print("Failed to get job posting")
        return None

def analyze_job_with_langgraph(job_id):
    """Analyze a job using the LangGraph agent"""
    print_section(f"ANALYZE JOB WITH LANGGRAPH: {job_id}")
    
    query = "Analyze this job posting and extract the key requirements and ideal candidate profile"
    
    data = {
        "query": query,
        "job_id": job_id
    }
    
    print(f"Sending analysis request to LangGraph with query: '{query}'")
    response = requests.post(f"{API_BASE_URL}/langgraph/analyze-job/{job_id}", headers=HEADERS)
    print_response(response)
    
    if response.status_code == 200:
        return response.json()
    else:
        print("Failed to analyze job with LangGraph")
        return None

def upload_resume_for_job(job_id, resume_path=None):
    """Upload a sample resume for a specific job"""
    print_section(f"UPLOAD RESUME FOR JOB: {job_id}")
    
    # If no resume provided, show instructions
    if not resume_path:
        print("No resume file provided. In a real scenario, you would upload a PDF or DOCX file.")
        print("For this demo, we're simulating the resume upload process.")
        
        # Create form data with dummy candidate info
        data = {
            "candidate_name": "John Doe",
            "candidate_email": "john.doe@example.com"
        }
        
        print("Using dummy candidate information:")
        pprint(data)
        print("\nNOTE: In a real scenario, you would include a file=@path/to/resume.pdf in the request")
        
        # We'll just print instructions since we can't upload an actual file in this demo
        print("\nTo upload a real resume, use a command like:")
        print(f"curl -X POST {API_BASE_URL}/resume/upload/{job_id} -F \"file=@/path/to/resume.pdf\" -F \"candidate_name=John Doe\" -F \"candidate_email=john.doe@example.com\"")
        
        # Return a simulated response
        return {
            "job_id": job_id,
            "status": "Resume upload simulated. In a real scenario, use the API to upload an actual resume file."
        }
    
    # For when an actual file path is provided (not used in this demo)
    return None

def process_resumes_for_job(job_id):
    """Process resumes for a specific job ID"""
    print_section(f"PROCESS RESUMES FOR JOB: {job_id}")
    
    data = {
        "job_id": job_id,
        "process_all": True
    }
    
    print("Sending resume processing request with data:")
    pprint(data)
    
    response = requests.post(f"{API_BASE_URL}/resume/process", json=data, headers=HEADERS)
    print_response(response)
    
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        print("""
IMPORTANT: No resumes found for this job. 

RESUME UPLOAD IS A REQUIRED STEP:
In a real scenario, you must upload candidate resumes before processing them.
Use the /resume/upload/{job_id} endpoint to upload resumes.

For production use:
1. Upload resumes for each candidate (PDF/DOCX)
2. Process those resumes to generate AI fit scores
3. Only then can you shortlist candidates
        """)
        return None
    else:
        print("Failed to process resumes")
        return None

def shortlist_candidates_with_agent(job_id):
    """Shortlist candidates using the CrewAI agent"""
    print_section(f"SHORTLIST CANDIDATES WITH AGENT: {job_id}")
    
    data = {
        "job_id": job_id,
        "number_of_candidates": 3,
        "number_of_rounds": 2
    }
    
    print("Sending shortlist request with data:")
    pprint(data)
    
    response = requests.post(f"{API_BASE_URL}/shortlist/agent", json=data, headers=HEADERS)
    print_response(response)
    
    if response.status_code == 200:
        return response.json()
    else:
        print("Failed to shortlist candidates")
        return None

def reschedule_interview(interview_id, round_index=0):
    """Reschedule an interview"""
    print_section(f"RESCHEDULE INTERVIEW: {interview_id}, Round {round_index}")
    
    # One month from now
    import datetime
    new_time = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d %H:%M")
    
    data = {
        "interview_id": interview_id,
        "round_index": round_index,
        "new_time": new_time,
        "reason": "Candidate requested postponement due to personal reasons"
    }
    
    print("Sending reschedule request with data:")
    pprint(data)
    
    response = requests.post(f"{API_BASE_URL}/reschedule/", json=data, headers=HEADERS)
    print_response(response)
    
    if response.status_code == 200:
        return response.json()
    else:
        print("Failed to reschedule interview")
        return None

def run_demo():
    """Run the full demo workflow"""
    print_section("INTERVIEW SCHEDULER AGENT DEMO")
    print("This script demonstrates the key features of the Interview Scheduler Agent API")
    
    # Step 1: Create a job posting
    job_id = create_job_posting()
    if not job_id:
        print("Demo cannot continue without a job ID. Please check your server configuration.")
        return
    
    # Step 2: Get the job posting
    job_details = get_job_posting(job_id)
    
    # Step 3: Analyze the job with LangGraph
    print("Analyzing job with LangGraph...")
    analysis = analyze_job_with_langgraph(job_id)
    
    # Step 4: Upload a sample resume (simulation only)
    print("Uploading a sample resume...")
    upload_result = upload_resume_for_job(job_id)
    
    # Step 5: Process resumes for the job
    print("Processing resumes for the job...")
    resume_result = process_resumes_for_job(job_id)
    
    # Check if resume processing was successful
    if not resume_result or resume_result.get("processed_count", 0) == 0:
        print("\n==== WORKFLOW ERROR ====")
        print("No resumes were processed. This is a critical step in the workflow.")
        print("In a production environment, you must:")
        print("1. Create a job posting")
        print("2. Upload actual candidate resumes (PDF/DOCX)")
        print("3. Process those resumes to generate AI fit scores") 
        print("4. Only then can you shortlist candidates")
        print("\nWithout processed resumes, shortlisting will fail.")
        print("=======================")
    else:
        print(f"Successfully processed {resume_result.get('processed_count', 0)} resumes")
    
    # Step 6: Shortlist candidates
    print("Shortlisting candidates...")
    shortlist_result = shortlist_candidates_with_agent(job_id)
    
    # Step 5: Get the interview ID from shortlist result
    interview_id = None
    if shortlist_result and "response" in shortlist_result:
        # Try to extract interview ID from the response text
        # This would need to be adjusted based on the actual response structure
        import re
        interview_match = re.search(r"interview\s+([a-zA-Z0-9-]+)", shortlist_result["response"], re.IGNORECASE)
        if interview_match:
            interview_id = interview_match.group(1)
    
    # If we got an interview ID, try rescheduling
    if interview_id:
        print(f"Found interview ID: {interview_id}")
        reschedule_interview(interview_id)
    else:
        print("No interview ID found in the response. Skipping rescheduling step.")
    
    print_section("DEMO COMPLETED")
    print("Thank you for exploring the Interview Scheduler Agent API.")
    print("You can use this script as a reference for how to interact with the API.")

if __name__ == "__main__":
    # Check if server is running
    try:
        health_check = requests.get(f"{API_BASE_URL}/health", timeout=2)
        if health_check.status_code == 200:
            print("Server is running. Starting demo...")
            run_demo()
        else:
            print("Server seems to be running but health check failed.")
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to server at {API_BASE_URL}")
        print("Please make sure the server is running with 'python run.py' before executing this script.")
    except Exception as e:
        print(f"Unexpected error: {e}")
