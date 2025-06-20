"""
Example script demonstrating how to use the specialized integration agents 
for Calendar, Google Meet, and Gmail operations
"""
import requests
import json
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

def demonstrate_calendar_agent():
    """Demonstrate Calendar Agent capabilities"""
    print_section("CALENDAR AGENT DEMO")
    
    # Example 1: Find available slots
    query = "Find available time slots for interviews on June 25, 2025"
    print(f"Sending calendar query: '{query}'")
    
    data = {
        "query": query
    }
    
    response = requests.post(
        f"{API_BASE_URL}/integrations/calendar", 
        json=data,
        headers=HEADERS
    )
    print_response(response, "Calendar Agent Response - Find Available Slots")
    
    # Example 2: Schedule a meeting
    query = """
    Schedule a technical interview meeting for the Senior Python Developer role with 
    candidate John Doe (john.doe@example.com) and interviewer Sarah Tech Lead 
    (sarah@company.com) tomorrow at 3 PM for 1 hour
    """
    print(f"Sending calendar query: '{query}'")
    
    data = {
        "query": query
    }
    
    response = requests.post(
        f"{API_BASE_URL}/integrations/calendar", 
        json=data,
        headers=HEADERS
    )
    print_response(response, "Calendar Agent Response - Schedule Meeting")
    
    return response.json() if response.status_code == 200 else None

def demonstrate_meet_agent():
    """Demonstrate Google Meet Agent capabilities"""
    print_section("GOOGLE MEET AGENT DEMO")
    
    # Example 1: Create a meeting link
    query = "Create a Google Meet link for a technical interview with John Doe"
    print(f"Sending Meet query: '{query}'")
    
    data = {
        "query": query
    }
    
    response = requests.post(
        f"{API_BASE_URL}/integrations/meet", 
        json=data,
        headers=HEADERS
    )
    print_response(response, "Meet Agent Response - Create Link")
    
    # Get the meet link from the response for use in Gmail example
    meet_link = None
    if response.status_code == 200:
        response_text = response.json().get("response", "")
        import re
        match = re.search(r"Link: (https://meet\.google\.com/[a-z\-]+)", response_text)
        if match:
            meet_link = match.group(1)
    
    # Example 2: Check meeting status
    if meet_link:
        query = f"Check the status of meeting {meet_link}"
        print(f"Sending Meet query: '{query}'")
        
        data = {
            "query": query
        }
        
        response = requests.post(
            f"{API_BASE_URL}/integrations/meet", 
            json=data,
            headers=HEADERS
        )
        print_response(response, "Meet Agent Response - Check Status")
    
    return meet_link

def demonstrate_gmail_agent(meet_link=None):
    """Demonstrate Gmail Agent capabilities"""
    print_section("GMAIL AGENT DEMO")
    
    # Example: Send an interview notification
    if meet_link:
        link_text = f"using the Google Meet link {meet_link}"
    else:
        link_text = "with Google Meet link that you should create"
        
    query = f"""
    Send an interview confirmation email to john.doe@example.com for a technical
    interview on June 25, 2025 at 3 PM {link_text}. The interviewer will be 
    Sarah Tech Lead (sarah@company.com) and this is for a Senior Python Developer position.
    Include instructions for preparing for the interview.
    """
    print(f"Sending Gmail query: '{query}'")
    
    data = {
        "query": query
    }
    
    response = requests.post(
        f"{API_BASE_URL}/integrations/gmail", 
        json=data,
        headers=HEADERS
    )
    print_response(response, "Gmail Agent Response - Send Notification")
    
    return response.json() if response.status_code == 200 else None

def demonstrate_full_integration():
    """Demonstrate full integration scheduling workflow"""
    print_section("FULL INTEGRATION WORKFLOW DEMO")
    
    # This demonstrates using all three agents together through one endpoint
    print("Scheduling an interview using the combined integration agents")
    
    data = {
        "candidate_name": "John Doe",
        "candidate_email": "john.doe@example.com",
        "interviewer_name": "Sarah Tech Lead",
        "interviewer_email": "sarah@company.com",
        "job_title": "Senior Python Developer",
        "preferred_date": "2025-06-25",
        "round_number": 1,
        "round_type": "Technical",
        "notes": "Focus on system design and Python best practices"
    }
    
    print("Sending integration request with data:")
    pprint(data)
    
    response = requests.post(
        f"{API_BASE_URL}/integrations/schedule-interview", 
        json=data,
        headers=HEADERS
    )
    print_response(response, "Full Integration Response")
    
    return response.json() if response.status_code == 200 else None

def run_demo():
    """Run the complete integration agents demo"""
    print_section("INTEGRATION AGENTS DEMO")
    print("This script demonstrates the specialized integration agents for Calendar, Meet, and Gmail")
    
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
    
    print("Server is running. Starting integration agents demo...")
    
    # Run individual agent demos
    calendar_result = demonstrate_calendar_agent()
    meet_link = demonstrate_meet_agent()
    gmail_result = demonstrate_gmail_agent(meet_link)
    
    # Run combined integration demo
    integration_result = demonstrate_full_integration()
    
    print_section("DEMO COMPLETED")
    print("You have now seen how the specialized integration agents work:")
    print("1. Calendar Agent - For managing calendar events and finding available slots")
    print("2. Meet Agent - For creating and managing Google Meet links")
    print("3. Gmail Agent - For sending email notifications related to interviews")
    print("4. Combined Integration - For a complete interview scheduling workflow")
    
    print("\nYou can use these agents for natural language operations with their respective services.")

if __name__ == "__main__":
    run_demo()
