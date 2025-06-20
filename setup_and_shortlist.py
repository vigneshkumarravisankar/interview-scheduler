"""
Setup and Shortlist script

This script:
1. Creates an AI Engineer job posting if it doesn't exist
2. Creates sample candidate data for this job
3. Runs the shortlisting process
"""

import requests
import json
import time
import uuid
from datetime import datetime
from pprint import pprint
import random

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

def create_ai_engineer_job():
    """Create an AI Engineer job posting if it doesn't exist"""
    print_section("CREATING AI ENGINEER JOB")
    
    # Check if job already exists
    print("Checking if AI Engineer job already exists...")
    
    try:
        # Search for jobs with role name "AI Engineer"
        search_response = requests.get(
            f"{API_BASE_URL}/jobs/search?role_name=AI%20Engineer",
            headers=HEADERS
        )
        
        if search_response.status_code == 200:
            jobs = search_response.json()
            if jobs and len(jobs) > 0:
                print(f"✅ AI Engineer job already exists with ID: {jobs[0].get('id', jobs[0].get('job_id'))}")
                print_response(search_response, "Existing Job")
                return jobs[0]
    except Exception as e:
        print(f"Error searching for job: {str(e)}")
    
    # Create new job
    print("Creating new AI Engineer job posting...")
    job_data = {
        "job_role_name": "AI Engineer",
        "job_id": f"ai-eng-{uuid.uuid4().hex[:8]}",
        "job_description": "Experienced AI Engineer proficient in machine learning frameworks, neural network architecture, and natural language processing. Strong background in Python programming and data science required.",
        "years_of_experience_needed": "3-5"
    }
    
    try:
        create_response = requests.post(
            f"{API_BASE_URL}/jobs/",
            json=job_data,
            headers=HEADERS
        )
        
        if create_response.status_code == 200 or create_response.status_code == 201:
            print("✅ Successfully created AI Engineer job")
            print_response(create_response, "New Job")
            return create_response.json()
        else:
            print(f"❌ Failed to create job: {create_response.status_code}")
            print_response(create_response, "Error")
            return None
    except Exception as e:
        print(f"❌ Error creating job: {str(e)}")
        return None

def create_sample_candidates(job_id):
    """Create sample candidates for the AI Engineer job"""
    print_section("CREATING SAMPLE CANDIDATES")
    
    print(f"Creating sample candidates for job ID: {job_id}")
    
    # Check if candidates already exist
    try:
        candidates_response = requests.get(
            f"{API_BASE_URL}/candidates/job/{job_id}",
            headers=HEADERS
        )
        
        if candidates_response.status_code == 200:
            candidates = candidates_response.json()
            if candidates and len(candidates) >= 3:
                print(f"✅ {len(candidates)} candidates already exist for this job")
                return candidates
    except Exception as e:
        print(f"Error checking existing candidates: {str(e)}")
    
    # Sample candidate data
    sample_candidates = [
        {
            "name": "John Smith",
            "email": "john.smith@example.com",
            "phone": "555-123-4567",
            "resume_url": "https://example.com/john_smith_resume.pdf",
            "job_id": job_id,
            "total_experience_in_years": 4,
            "technical_skills": ["Python", "TensorFlow", "PyTorch", "Natural Language Processing", "Computer Vision"],
            "ai_fit_score": 92,
            "education": "M.S. in Computer Science, Stanford University",
            "previous_employers": ["Google", "Meta AI Research"]
        },
        {
            "name": "Emily Johnson",
            "email": "emily.johnson@example.com",
            "phone": "555-234-5678",
            "resume_url": "https://example.com/emily_johnson_resume.pdf",
            "job_id": job_id,
            "total_experience_in_years": 5,
            "technical_skills": ["Python", "Keras", "ML Ops", "Data Science", "Deep Learning"],
            "ai_fit_score": 88,
            "education": "Ph.D. in Machine Learning, MIT",
            "previous_employers": ["NVIDIA", "IBM Research"]
        },
        {
            "name": "Michael Chen",
            "email": "michael.chen@example.com",
            "phone": "555-345-6789",
            "resume_url": "https://example.com/michael_chen_resume.pdf",
            "job_id": job_id,
            "total_experience_in_years": 3,
            "technical_skills": ["Python", "Scikit-learn", "LLMs", "MLflow", "AWS SageMaker"],
            "ai_fit_score": 85,
            "education": "B.S. in Computer Science, UC Berkeley",
            "previous_employers": ["Amazon AWS", "Microsoft"]
        },
        {
            "name": "Sophia Rodriguez",
            "email": "sophia.rodriguez@example.com",
            "phone": "555-456-7890",
            "resume_url": "https://example.com/sophia_rodriguez_resume.pdf",
            "job_id": job_id,
            "total_experience_in_years": 4,
            "technical_skills": ["Python", "Transformers", "BERT", "GPT", "Computer Vision"],
            "ai_fit_score": 90,
            "education": "M.S. in AI, Carnegie Mellon University",
            "previous_employers": ["OpenAI", "DeepMind"]
        },
        {
            "name": "Alexander Kim",
            "email": "alexander.kim@example.com",
            "phone": "555-567-8901",
            "resume_url": "https://example.com/alexander_kim_resume.pdf",
            "job_id": job_id,
            "total_experience_in_years": 6,
            "technical_skills": ["Python", "JAX", "TensorFlow", "NLP", "Reinforcement Learning"],
            "ai_fit_score": 78,
            "education": "Ph.D. in Computer Science, Stanford University",
            "previous_employers": ["Apple", "Facebook AI Research"]
        }
    ]
    
    # Create candidates in the database
    created_candidates = []
    
    for candidate_data in sample_candidates:
        try:
            # Add unique id to each candidate
            candidate_data["id"] = f"cand-{uuid.uuid4().hex[:8]}"
            
            # Use direct database access to create the candidate
            # This is a simplified approach - in a real system you might want to use the proper API endpoint
            try:
                from app.database.firebase_db import FirestoreDB
                candidate_id = FirestoreDB.create_document("candidates_data", candidate_data)
                print(f"✅ Created candidate: {candidate_data['name']} (ID: {candidate_id})")
                created_candidates.append({**candidate_data, "id": candidate_id})
            except ImportError:
                # Fall back to API if direct database access isn't available
                create_response = requests.post(
                    f"{API_BASE_URL}/candidates/",
                    json=candidate_data,
                    headers=HEADERS
                )
                
                if create_response.status_code == 200 or create_response.status_code == 201:
                    created_candidate = create_response.json()
                    print(f"✅ Created candidate: {candidate_data['name']}")
                    created_candidates.append(created_candidate)
                else:
                    print(f"❌ Failed to create candidate {candidate_data['name']}: {create_response.status_code}")
        except Exception as e:
            print(f"❌ Error creating candidate {candidate_data['name']}: {str(e)}")
    
    print(f"✅ Created {len(created_candidates)} sample candidates")
    return created_candidates

def shortlist_candidates(job_id):
    """Shortlist candidates for the AI Engineer job"""
    print_section("SHORTLISTING CANDIDATES")
    
    print(f"Shortlisting top 3 candidates for job ID: {job_id}")
    
    # Use direct shortlisting by job_id
    data = {
        "job_id": job_id,
        "number_of_candidates": 3
    }
    
    try:
        shortlist_response = requests.post(
            f"{API_BASE_URL}/specialized/shortlist",
            json=data,
            headers=HEADERS
        )
        
        print_response(shortlist_response, "Shortlisting Response")
        
        if shortlist_response.status_code != 200:
            print("❌ Error starting shortlisting process")
            return None
        
        # Wait for shortlisting to complete
        print("Waiting for shortlisting to complete...")
        time.sleep(5)  # Give it a few seconds to process
        
        # Check status
        status_response = requests.get(
            f"{API_BASE_URL}/specialized/status/{job_id}",
            headers=HEADERS
        )
        
        print_response(status_response, "Status Check")
        
        # Get interview candidates
        interviews_response = requests.get(
            f"{API_BASE_URL}/interviews/job/{job_id}",
            headers=HEADERS
        )
        
        if interviews_response.status_code == 200:
            interviews = interviews_response.json()
            if interviews and len(interviews) > 0:
                print(f"✅ Found {len(interviews)} shortlisted candidates")
                print_response(interviews_response, "Shortlisted Candidates")
                return interviews
            else:
                print("❌ No shortlisted candidates found")
        else:
            print(f"❌ Error getting interview candidates: {interviews_response.status_code}")
            
        return None
    except Exception as e:
        print(f"❌ Error in shortlisting process: {str(e)}")
        return None

def run_setup_and_shortlist():
    """Run the complete setup and shortlisting process"""
    print_section("AI ENGINEER SHORTLISTING SETUP")
    
    # Check if server is running
    try:
        health_check = requests.get(f"{API_BASE_URL}/health", timeout=2)
        if health_check.status_code != 200:
            print("❌ Server seems to be running but health check failed.")
            return
    except requests.exceptions.ConnectionError:
        print(f"❌ Error: Could not connect to server at {API_BASE_URL}")
        print("Please make sure the server is running with 'python run.py' before executing this script.")
        return
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return
    
    print("✅ Server is running. Starting setup process...")
    
    # Step 1: Create AI Engineer job
    job = create_ai_engineer_job()
    if not job:
        print("❌ Failed to create or find AI Engineer job. Aborting.")
        return
    
    job_id = job.get('id', job.get('job_id'))
    if not job_id:
        print("❌ Could not determine job ID. Aborting.")
        return
    
    # Step 2: Create sample candidates
    candidates = create_sample_candidates(job_id)
    if not candidates or len(candidates) < 3:
        print("❌ Failed to create enough sample candidates. Aborting.")
        return
    
    # Step 3: Shortlist candidates
    shortlisted = shortlist_candidates(job_id)
    
    # Display final result
    if shortlisted and len(shortlisted) > 0:
        print_section("SHORTLISTING SUCCESSFUL")
        print(f"✅ Successfully shortlisted {len(shortlisted)} AI Engineer candidates!\n")
        
        # Show shortlisted candidates in order
        print("SHORTLISTED CANDIDATES (sorted by AI fit score):")
        for i, candidate in enumerate(shortlisted):
            print(f"\n{i+1}. {candidate.get('candidate_name', 'Unknown')}")
            print(f"   Email: {candidate.get('candidate_email', 'Unknown')}")
            print(f"   Job Role: {candidate.get('job_role', 'Unknown')}")
            print(f"   Status: {candidate.get('status', 'Unknown')}")
    else:
        print_section("SHORTLISTING FAILED")
        print("❌ Failed to shortlist AI Engineer candidates.")
        
    print_section("PROCESS COMPLETED")

if __name__ == "__main__":
    run_setup_and_shortlist()
