"""
End-to-End Interview Agent Process

This script properly sequences the agents:
1. First the shortlisting_agent - Uses FindJobByRoleTool and ShortlistCandidatesByRoleTool
2. Then the scheduling_agent - Uses ScheduleInterviewTool with calendar MCP server integration
"""

import sys
import os
import logging
import json
import time
import requests
from pprint import pprint
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the project directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# MCP server configuration 
MCP_SERVER_URL = "http://localhost:8501"  # Default port for calendar-mcp-server.py

def print_section(title):
    """Print a section title"""
    print("\n" + "="*80)
    print(f" {title} ".center(80, "="))
    print("="*80 + "\n")

def check_mcp_server():
    """Check if the Calendar MCP Server is running"""
    try:
        response = requests.get(f"{MCP_SERVER_URL}/", timeout=2)
        return response.status_code == 200
    except Exception:
        return False

def run_shortlisting_agent(role_name, number_of_candidates):
    """
    Run the shortlisting agent which:
    1. Finds job by role name with FindJobByRoleTool
    2. Shortlists candidates with ShortlistCandidatesByRoleTool
    """
    print_section(f"RUNNING SHORTLISTING AGENT FOR: {role_name}")
    
    try:
        # Import CrewAI components here to ensure path is set up properly
        from crewai import Agent, Task, Crew, Process
        from app.agents.specialized_agents import shortlisting_agent
        
        # Create a shortlisting task
        shortlisting_task = Task(
            description=f"""
            You are tasked with shortlisting the top {number_of_candidates} candidates for the role: "{role_name}".
            
            Follow these steps EXACTLY in this order:
            1. FIRST, use the FindJobByRoleTool to find the job with role name "{role_name}" in the jobs collection.
               - This will return job details including the job_id.
               - Report the exact job_id you found.
            
            2. SECOND, once you have the job_id, use the ShortlistCandidatesByRoleTool with:
               - role_name="{role_name}"
               - number_of_candidates={number_of_candidates}
               
            Be sure to follow this exact sequence and report your findings after each step.
            """,
            expected_output=f"Detailed report of the job ID found and the {number_of_candidates} candidates shortlisted for '{role_name}'",
            agent=shortlisting_agent
        )
        
        # Create a crew with just the shortlisting agent
        shortlisting_crew = Crew(
            agents=[shortlisting_agent],
            tasks=[shortlisting_task],
            verbose=True,
            process=Process.sequential
        )
        
        print(f"Executing shortlisting agent for role: {role_name}")
        shortlisting_result = shortlisting_crew.kickoff()
        
        print_section("SHORTLISTING RESULT")
        print(shortlisting_result)
        return shortlisting_result
    except ImportError as e:
        print(f"❌ Failed to import required components: {e}")
        print("Make sure you've installed all required packages and are running from the project root.")
        return None
    except Exception as e:
        print(f"❌ Error running shortlisting agent: {e}")
        import traceback
        print(traceback.format_exc())
        return None

def run_scheduling_agent(role_name, number_of_rounds):
    """
    Run the scheduling agent which:
    1. Gets shortlisted candidates
    2. Schedules interviews using Calendar MCP
    3. Sends email notifications
    """
    print_section(f"RUNNING SCHEDULING AGENT FOR: {role_name}")
    
    try:
        # Import CrewAI components here to ensure path is set up properly
        from crewai import Agent, Task, Crew, Process
        from app.agents.specialized_agents import scheduling_agent
        
        # Create a scheduling task
        scheduling_task = Task(
            description=f"""
            You are tasked with scheduling interviews for the recently shortlisted candidates for the role: "{role_name}".
            
            Follow these steps:
            1. Find the job_id for role "{role_name}" if you don't already have it.
            2. Get the shortlisted candidates from the interview_candidates collection.
            3. For each candidate, use ScheduleInterviewTool to:
               - Schedule {number_of_rounds} interview rounds
               - Create Google Calendar events with Google Meet links
               - Send email notifications
               
            The ScheduleInterviewTool will:
            - Create calendar events through the Calendar MCP Server
            - Generate Google Meet links for each interview
            - Send email notifications to candidates and interviewers
            - Store all event details in Firebase
            
            Report details of all scheduled interviews with dates, times, and Google Meet links.
            """,
            expected_output=f"Complete report of scheduled interviews for all shortlisted '{role_name}' candidates",
            agent=scheduling_agent
        )
        
        # Create a crew with just the scheduling agent
        scheduling_crew = Crew(
            agents=[scheduling_agent],
            tasks=[scheduling_task],
            verbose=True,
            process=Process.sequential
        )
        
        print(f"Executing scheduling agent for role: {role_name}")
        scheduling_result = scheduling_crew.kickoff()
        
        print_section("SCHEDULING RESULT")
        print(scheduling_result)
        return scheduling_result
    except ImportError as e:
        print(f"❌ Failed to import required components: {e}")
        print("Make sure you've installed all required packages and are running from the project root.")
        return None
    except Exception as e:
        print(f"❌ Error running scheduling agent: {e}")
        import traceback
        print(traceback.format_exc())
        return None

def run_end_to_end_process(role_name="AI Engineer", number_of_candidates=3, number_of_rounds=2):
    """
    Run the complete end-to-end process:
    1. First the shortlisting agent
    2. Then the scheduling agent
    """
    print_section("END-TO-END INTERVIEW PROCESS")
    print(f"Role name: {role_name}")
    print(f"Number of candidates to shortlist: {number_of_candidates}")
    print(f"Number of interview rounds: {number_of_rounds}")
    
    # First check Calendar MCP Server
    if not check_mcp_server():
        print("⚠️ Warning: Calendar MCP Server doesn't appear to be running.")
        print(f"Make sure the server is running at {MCP_SERVER_URL}")
        print("You can start it with: python calendar-mcp-server.py")
        
        response = input("\nDo you want to continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Process aborted.")
            return
    
    # Step 1: Run the shortlisting agent
    shortlisting_result = run_shortlisting_agent(role_name, number_of_candidates)
    
    if not shortlisting_result:
        print("❌ Shortlisting failed. Cannot proceed with scheduling.")
        return
        
    print("\n✅ Shortlisting completed successfully!")
    
    # Ask if the user wants to proceed with scheduling
    response = input("\nDo you want to schedule interviews for these candidates now? (y/n): ")
    if response.lower() != 'y':
        print("Scheduling skipped. Process completed.")
        return
        
    # Step 2: Run the scheduling agent
    scheduling_result = run_scheduling_agent(role_name, number_of_rounds)
    
    if not scheduling_result:
        print("❌ Scheduling failed.")
        return
        
    print("\n✅ Scheduling completed successfully!")
    
    # Display final results
    print_section("PROCESS COMPLETED SUCCESSFULLY")
    print("The end-to-end interview process has been completed:")
    print(f"1. Top {number_of_candidates} candidates for {role_name} have been shortlisted")
    print(f"2. {number_of_rounds} interview rounds have been scheduled for each candidate")
    print(f"3. Calendar events have been created with Google Meet links")
    print(f"4. Email notifications have been sent to candidates and interviewers")
    print("\nAll information has been stored in Firebase.")

def get_job_info_from_shortlisting_result(shortlisting_result):
    """Extract job ID from the shortlisting result text (helper function)"""
    # This is a simplified example - in a real system, you might want to parse the result more carefully
    if not shortlisting_result:
        return None
        
    # Look for patterns like "job ID: xyz" or "job_id: xyz" in the result
    import re
    job_id_match = re.search(r'job(?:_| )id:?\s*([a-zA-Z0-9_-]+)', shortlisting_result.lower())
    if job_id_match:
        return job_id_match.group(1)
    return None

if __name__ == "__main__":
    print_section("END-TO-END INTERVIEW AGENT PROCESS")
    print("This script runs the interview agents in proper sequence:")
    print("1. Shortlisting Agent: Find job by role name and shortlist candidates")
    print("2. Scheduling Agent: Create calendar events and send notifications")
    
    # Default parameters
    role_name = "AI Engineer"
    number_of_candidates = 3
    number_of_rounds = 2
    
    # Parse command-line arguments if provided
    if len(sys.argv) > 1:
        role_name = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            number_of_candidates = int(sys.argv[2])
        except ValueError:
            print(f"Invalid number of candidates: {sys.argv[2]}. Using default: 3")
    if len(sys.argv) > 3:
        try:
            number_of_rounds = int(sys.argv[3])
        except ValueError:
            print(f"Invalid number of rounds: {sys.argv[3]}. Using default: 2")
    
    # Run the end-to-end process
    run_end_to_end_process(role_name, number_of_candidates, number_of_rounds)
