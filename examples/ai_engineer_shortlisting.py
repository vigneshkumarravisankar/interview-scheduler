"""
Example script demonstrating how to shortlist candidates for an AI Engineer role
"""
import requests
import json
from pprint import pprint
import time
import sys

# Configuration
API_BASE_URL = "http://localhost:5000"
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

def shortlist_ai_engineer_candidates():
    """
    Demonstrates shortlisting AI Engineer candidates:
    1. First check for this role in jobs collection
    2. Retrieve job_id and then check candidates in candidates_data
    3. Match candidates with this job_id
    4. Shortlist top candidates based on AI fit score
    5. Store candidates in interview_candidates collection
    """
    print_section("SHORTLISTING AI ENGINEER CANDIDATES")
    
    # Use the specialized shortlist-by-role endpoint
    # This will:
    # 1. Find the job with role name "AI Engineer" in jobs collection
    # 2. Get candidates from candidates_data with matching job_id
    # 3. Sort by AI fit score and take top 3
    # 4. Store directly in interview_candidates collection
    
    print("Shortlisting top 3 candidates for AI Engineer role...")
    data = {
        "role_name": "AI Engineer",  # The exact role name to search for
        "number_of_candidates": 3    # Shortlist top 3 candidates
    }
    
    response = requests.post(
        f"{API_BASE_URL}/specialized/shortlist-by-role",
        json=data,
        headers=HEADERS
    )
    print_response(response, "Shortlisting Request Response")
    
    if response.status_code != 200:
        print("❌ Error starting shortlisting process")
        return
        
    role_name = response.json().get("role_name")
    
    # Poll the status API to see when shortlisting completes
    print("Polling status to check progress...")
    
    max_attempts = 10
    for attempt in range(max_attempts):
        # First we need to get jobs with this role name to find their job_ids
        print(f"Checking jobs with role name '{role_name}'...")
        
        try:
            # Use job_routes to find jobs with this role name
            jobs_response = requests.get(
                f"{API_BASE_URL}/jobs/search?role_name={role_name}",
                headers=HEADERS
            )
            
            if jobs_response.status_code != 200:
                print(f"❌ Error finding jobs: {jobs_response.status_code}")
                jobs = []
            else:
                jobs = jobs_response.json()
                print(f"Found {len(jobs)} jobs matching '{role_name}'")
        except Exception as e:
            print(f"❌ Error finding jobs: {str(e)}")
            jobs = []
            
        if not jobs:
            print(f"No jobs found with role name '{role_name}'. Waiting...")
            time.sleep(5)
            continue
            
        # Now check status for each job ID
        for job in jobs:
            job_id = job.get('id', job.get('job_id'))
            if not job_id:
                continue
                
            print(f"Checking status for job ID: {job_id}")
            status_response = requests.get(
                f"{API_BASE_URL}/specialized/status/{job_id}",
                headers=HEADERS
            )
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                print_response(status_response, f"Status Check for job {job_id}")
                
                if status_data.get("scheduled_interviews", 0) > 0:
                    print(f"✅ Shortlisting complete for job {job_id}!")
                    
                    # Now get the interview candidates
                    interviews_response = requests.get(
                        f"{API_BASE_URL}/interviews/job/{job_id}",
                        headers=HEADERS
                    )
                    
                    if interviews_response.status_code == 200:
                        interviews = interviews_response.json()
                        print(f"✅ Found {len(interviews)} interview candidates!")
                        print_response(interviews_response, "Interview Candidates")
                        return interviews
        
        # Wait before checking again
        if attempt < max_attempts - 1:
            wait_time = 5
            print(f"Waiting {wait_time} seconds before checking again... (Attempt {attempt+1}/{max_attempts})")
            time.sleep(wait_time)
    
    print("❌ Shortlisting process did not complete in the expected time")
    return None

def check_database_directly():
    """
    Check the Firebase database collections directly:
    - jobs collection for AI Engineer role
    - candidates_data collection for candidates with matching job_id
    - interview_candidates collection for shortlisted candidates
    
    This is a fallback if the API endpoints aren't working or available
    """
    print_section("CHECKING DATABASE DIRECTLY")
    print("This function would directly query Firebase collections to verify shortlisting.")
    print("Implement this if you need to bypass the API and check data directly in Firestore.")
    print("Example logic:")
    print("1. Query jobs collection for documents where job_role_name == 'AI Engineer'")
    print("2. Extract job_id from the found document")
    print("3. Query interview_candidates where job_id matches and verify top candidates are present")

def run_demo():
    """Run the AI Engineer shortlisting demo"""
    print_section("AI ENGINEER SHORTLISTING DEMO")
    print("This script demonstrates finding and shortlisting candidates for the AI Engineer role")
    
    # Check if server is running
    try:
        health_check = requests.get(f"{API_BASE_URL}/health", timeout=2)
        if health_check.status_code != 200:
            print("Server seems to be running but health check failed.")
            return
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to server at {API_BASE_URL}")
        print("Please make sure the server is running with 'python run.py' before executing this script.")
        return
    except Exception as e:
        print(f"Unexpected error: {e}")
        return
    
    print("Server is running. Starting AI Engineer shortlisting demo...")
    
    # Shortlist AI Engineer candidates
    shortlisted = shortlist_ai_engineer_candidates()
    
    if shortlisted:
        print("\n✅ Successfully shortlisted AI Engineer candidates!")
        print(f"Total candidates shortlisted: {len(shortlisted)}")
    else:
        print("\n❌ Failed to complete shortlisting process")
    
    print_section("DEMO COMPLETED")

if __name__ == "__main__":
    run_demo()
