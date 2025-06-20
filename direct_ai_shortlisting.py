"""
Direct AI Shortlisting and Scheduling Script

This script directly uses the CrewAI agents to:
1. Find a job by role name using FindJobByRoleTool
2. Shortlist candidates using ShortlistCandidatesByRoleTool
3. Schedule interviews for the shortlisted candidates
"""

import sys
import os
import logging
import json
from pprint import pprint

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the project directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import CrewAI components
try:
    from crewai import Agent, Task, Crew, Process
    from app.agents.specialized_agents import (
        shortlisting_agent, scheduling_agent,
        FindJobByRoleTool, ShortlistCandidatesByRoleTool, ScheduleInterviewTool
    )
except ImportError as e:
    logger.error(f"Failed to import CrewAI components: {e}")
    logger.error("Make sure you've installed all required packages and are running from the project root.")
    sys.exit(1)

def print_section(title):
    """Print a section title"""
    print("\n" + "="*80)
    print(f" {title} ".center(80, "="))
    print("="*80 + "\n")

def direct_shortlist_and_schedule(role_name="AI Engineer", number_of_candidates=3, number_of_rounds=2):
    """
    Directly use CrewAI agents to:
    1. Find a job by role name
    2. Shortlist candidates
    3. Schedule interviews
    """
    print_section(f"DIRECT SHORTLISTING AND SCHEDULING FOR: {role_name}")
    
    try:
        # Create a shortlisting task
        shortlisting_task = Task(
            description=f"""
            Shortlist the top {number_of_candidates} candidates for the role: "{role_name}".
            
            Steps:
            1. Use FindJobByRoleTool to find the job with role name "{role_name}" in the jobs collection
            2. Use ShortlistCandidatesByRoleTool to shortlist the top {number_of_candidates} candidates 
               based on AI fit scores and store them in the interview_candidates collection
               
            Be sure to use the exact role name "{role_name}" in your search.
            """,
            expected_output=f"List of top {number_of_candidates} candidates for role '{role_name}', sorted by AI fit score",
            agent=shortlisting_agent
        )
        
        # Create a scheduling task
        scheduling_task = Task(
            description=f"""
            Schedule interviews for the shortlisted candidates for role: "{role_name}".
            
            Steps:
            1. Get the job ID for the role "{role_name}" (if not already known from previous task)
            2. For each shortlisted candidate, use ScheduleInterviewTool to schedule interviews with {number_of_rounds} rounds
            3. Ensure calendar events are created and email notifications are sent
            
            Include all details about the scheduled interviews in your response.
            """,
            expected_output=f"Interview schedules for all shortlisted candidates for role '{role_name}'",
            agent=scheduling_agent,
            context=[shortlisting_task]  # Pass the shortlisting task as context
        )
        
        # Create the combined crew
        crew = Crew(
            agents=[shortlisting_agent, scheduling_agent],
            tasks=[shortlisting_task, scheduling_task],
            verbose=True,
            process=Process.sequential
        )
        
        print(f"Starting CrewAI process for shortlisting and scheduling {role_name} interviews...")
        result = crew.kickoff()
        
        print_section("CREW RESULT")
        print(f"Result: {result}")
        return result
        
    except Exception as e:
        print(f"❌ Error in CrewAI process: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None

def direct_shortlist_only(role_name="AI Engineer", number_of_candidates=3):
    """
    Directly use CrewAI shortlisting agent to:
    1. Find a job by role name
    2. Shortlist candidates
    """
    print_section(f"DIRECT SHORTLISTING FOR: {role_name}")
    
    try:
        # Create a specialized task for just using ShortlistCandidatesByRoleTool
        shortlisting_task = Task(
            description=f"""
            Your task is to shortlist the top {number_of_candidates} candidates for the role: "{role_name}".
            
            Follow these steps exactly:
            1. First, use the FindJobByRoleTool to find the job with role name "{role_name}" in the jobs collection
               - This will give you the job_id you need for the next step
            
            2. After you have the job_id, use the ShortlistCandidatesByRoleTool to:
               - Shortlist the top {number_of_candidates} candidates based on AI fit scores
               - Store them directly in the interview_candidates collection
               
            Important: Make sure to use the exact role name "{role_name}" when searching.
            """,
            expected_output=f"Detailed list of the top {number_of_candidates} candidates that have been shortlisted for role '{role_name}'",
            agent=shortlisting_agent  # This agent has access to FindJobByRoleTool and ShortlistCandidatesByRoleTool
        )
        
        # Create a simple crew with just this task
        crew = Crew(
            agents=[shortlisting_agent],
            tasks=[shortlisting_task],
            verbose=True,
            process=Process.sequential
        )
        
        print(f"Starting CrewAI process for shortlisting {role_name} candidates...")
        print("This will use FindJobByRoleTool and ShortlistCandidatesByRoleTool sequentially...")
        result = crew.kickoff()
        
        print_section("CREW RESULT")
        print(f"Result: {result}")
        return result
        
    except Exception as e:
        print(f"❌ Error in CrewAI process: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None

if __name__ == "__main__":
    print_section("DIRECT CREWAI AGENT EXECUTION")
    print("This script directly executes the CrewAI agents for shortlisting and scheduling")
    
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
            
    print(f"Role name: {role_name}")
    print(f"Number of candidates to shortlist: {number_of_candidates}")
    print(f"Number of interview rounds: {number_of_rounds}")
    
    # First run shortlisting only
    shortlist_result = direct_shortlist_only(role_name, number_of_candidates)
    
    if shortlist_result:
        print_section("SHORTLISTING SUCCESSFUL")
        
        # Ask if user wants to continue with scheduling
        response = input("\nDo you want to schedule interviews for these candidates? (y/n): ")
        if response.lower() == 'y':
            # Run full process including scheduling
            full_result = direct_shortlist_and_schedule(role_name, number_of_candidates, number_of_rounds)
            
            if full_result:
                print_section("PROCESS COMPLETED SUCCESSFULLY")
                print("✅ Candidates have been shortlisted and interviews scheduled!")
            else:
                print_section("SCHEDULING FAILED")
                print("❌ Scheduling process failed. Please check the logs for details.")
        else:
            print_section("PROCESS COMPLETED")
            print("✅ Shortlisting completed. Scheduling skipped as requested.")
    else:
        print_section("SHORTLISTING FAILED")
        print("❌ Shortlisting process failed. Please check the logs for details.")
