"""
Example script demonstrating how to use the specialized shortlisting and scheduling agents
"""
import requests
import json
from pprint import pprint
import time

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

def demonstrate_shortlisting_agent():
    """Demonstrate the specialized shortlisting agent"""
    print_section("SHORTLISTING AGENT DEMO")
    
    # First, get a job ID to work with
    # Note: Update this with an actual job ID from your system
    job_id = "py-dev-001"  # Example job ID
    
    # Demo: Shortlist candidates
    print("Shortlisting candidates for job...")
    data = {
        "job_id": job_id,
        "number_of_candidates": 3  # Shortlist top 3 candidates
    }
    
    response = requests.post(
        f"{API_BASE_URL}/specialized/shortlist",
        json=data,
        headers=HEADERS
    )
    print_response(response, "Shortlisting Candidates Response")
    
    # Poll the status API to see when it completes
    print("Polling status API to check progress...")
    
    for i in range(5):  # Poll up to 5 times
        status_response = requests.get(
            f"{API_BASE_URL}/specialized/status/{job_id}",
            headers=HEADERS
        )
        print_response(status_response, f"Status Check {i+1}")
        
        # Check if shortlisting is complete
        if status_response.status_code == 200:
            status_data = status_response.json()
            if status_data.get("shortlisting_complete"):
                print("✅ Shortlisting complete!")
                break
        
        # Wait before polling again
        if i < 4:  # Don't sleep after the last check
            print("Waiting 5 seconds before checking again...")
            time.sleep(5)
    
    return status_response.json() if status_response.status_code == 200 else None

def demonstrate_scheduling_agent(job_id):
    """Demonstrate the specialized scheduling agent"""
    print_section("SCHEDULING AGENT DEMO")
    
    # Demo: Schedule interviews
    print("Scheduling interviews for shortlisted candidates...")
    data = {
        "job_id": job_id,
        "interview_date": None,  # Use default (tomorrow)
        "number_of_rounds": 2    # Schedule 2 interview rounds
    }
    
    response = requests.post(
        f"{API_BASE_URL}/specialized/schedule",
        json=data,
        headers=HEADERS
    )
    print_response(response, "Scheduling Interviews Response")
    
    # Poll the status API to see when it completes
    print("Polling status API to check progress...")
    
    for i in range(5):  # Poll up to 5 times
        status_response = requests.get(
            f"{API_BASE_URL}/specialized/status/{job_id}",
            headers=HEADERS
        )
        print_response(status_response, f"Status Check {i+1}")
        
        # Check if scheduling is complete
        if status_response.status_code == 200:
            status_data = status_response.json()
            if status_data.get("scheduling_complete"):
                print("✅ Interview scheduling complete!")
                break
        
        # Wait before polling again
        if i < 4:  # Don't sleep after the last check
            print("Waiting 5 seconds before checking again...")
            time.sleep(5)
    
    return status_response.json() if status_response.status_code == 200 else None

def demonstrate_end_to_end_process():
    """Demonstrate the end-to-end process with specialized agents"""
    print_section("END-TO-END PROCESS DEMO")
    
    # First, get a job ID to work with
    # Note: Update this with an actual job ID from your system
    job_id = "py-dev-002"  # Example job ID
    
    # Demo: End-to-end process
    print("Starting end-to-end process (shortlist + schedule)...")
    data = {
        "job_id": job_id,
        "number_of_candidates": 2,  # Shortlist top 2 candidates
        "interview_date": None,     # Use default (tomorrow)
        "number_of_rounds": 3       # Schedule 3 interview rounds
    }
    
    response = requests.post(
        f"{API_BASE_URL}/specialized/end-to-end",
        json=data,
        headers=HEADERS
    )
    print_response(response, "End-to-End Process Response")
    
    # Poll the status API to see when it completes
    print("Polling status API to check progress...")
    
    for i in range(10):  # Poll up to 10 times (end-to-end takes longer)
        status_response = requests.get(
            f"{API_BASE_URL}/specialized/status/{job_id}",
            headers=HEADERS
        )
        print_response(status_response, f"Status Check {i+1}")
        
        # Check if both processes are complete
        if status_response.status_code == 200:
            status_data = status_response.json()
            if status_data.get("shortlisting_complete") and status_data.get("scheduling_complete"):
                print("✅ End-to-end process complete!")
                break
        
        # Wait before polling again
        if i < 9:  # Don't sleep after the last check
            print("Waiting 10 seconds before checking again...")
            time.sleep(10)
    
    return status_response.json() if status_response.status_code == 200 else None

def run_demo():
    """Run the complete specialized agents demo"""
    print_section("SPECIALIZED AGENTS DEMO")
    print("This script demonstrates the specialized agents for shortlisting and scheduling")
    
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
    
    print("Server is running. Starting specialized agents demo...")
    
    # Option 1: Run shortlisting and scheduling separately
    print("\nDEMO OPTION 1: Run shortlisting and scheduling separately")
    shortlist_result = demonstrate_shortlisting_agent()
    
    if shortlist_result and shortlist_result.get("shortlisted_count") > 0:
        job_id = shortlist_result.get("job_id")
        schedule_result = demonstrate_scheduling_agent(job_id)
    
    # Option 2: Run end-to-end process
    print("\nDEMO OPTION 2: Run end-to-end process")
    end_to_end_result = demonstrate_end_to_end_process()
    
    print_section("DEMO COMPLETED")
    print("You have now seen how the specialized agents work:")
    print("1. Shortlisting Agent - Selects top candidates based on AI fit scores")
    print("2. Scheduling Agent - Schedules interviews with calendar, meet, and email")
    print("3. End-to-End Process - Combines both agents for a complete workflow")
    
    print("\nThese agents provide a more focused approach to each step of the hiring process.")

if __name__ == "__main__":
    run_demo()
