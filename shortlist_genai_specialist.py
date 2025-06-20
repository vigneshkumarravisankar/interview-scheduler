"""
Script to shortlist top 2 candidates for GenAI Specialist role

This script uses the specialized agents API to:
1. Find a job with the role name "GenAI Specialist"
2. Shortlist the top 2 candidates based on AI fit score
3. Return the results
"""
import requests
import json
import time
from pprint import pprint

# API Configuration
API_BASE_URL = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}

def create_genai_specialist_job():
    """Create a GenAI Specialist job if it doesn't exist"""
    print("Checking if GenAI Specialist job already exists...")
    
    try:
        # Search for jobs with role name "GenAI Specialist"
        search_response = requests.get(
            f"{API_BASE_URL}/jobs/search?role_name=GenAI%20Specialist",
            headers=HEADERS
        )
        
        if search_response.status_code == 200:
            jobs = search_response.json()
            if jobs and len(jobs) > 0:
                print(f"✅ GenAI Specialist job already exists with ID: {jobs[0].get('id', jobs[0].get('job_id'))}")
                return jobs[0]
    except Exception as e:
        print(f"Error searching for job: {str(e)}")
    
    # Create a new GenAI Specialist job
    print("Creating new GenAI Specialist job...")
    
    import uuid
    job_data = {
        "job_role_name": "GenAI Specialist",
        "job_id": f"genai-{uuid.uuid4().hex[:8]}",
        "job_description": """
        Looking for a GenAI Specialist with extensive experience in large language models, 
        prompt engineering, RAG systems, and fine-tuning. The ideal candidate should have 
        hands-on experience with models like GPT-4, Claude, and open-source LLMs. 
        Must be proficient in Python and have knowledge of ML frameworks.
        """,
        "years_of_experience_needed": "2-5"
    }
    
    try:
        create_response = requests.post(
            f"{API_BASE_URL}/jobs/",
            json=job_data,
            headers=HEADERS
        )
        
        if create_response.status_code == 200 or create_response.status_code == 201:
            print("✅ Successfully created GenAI Specialist job")
            return create_response.json()
        else:
            print(f"❌ Failed to create job: {create_response.status_code}")
            print(create_response.text)
            return None
    except Exception as e:
        print(f"❌ Error creating job: {str(e)}")
        return None

def create_sample_candidates(job_id):
    """Create sample GenAI Specialist candidates"""
    print(f"Creating sample candidates for GenAI Specialist job ID: {job_id}")
    
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
    
    # Sample GenAI Specialist candidate data
    sample_candidates = [
        {
            "name": "David Kumar",
            "email": "david.kumar@example.com",
            "phone": "555-123-4567",
            "resume_url": "https://example.com/david_kumar_resume.pdf",
            "job_id": job_id,
            "total_experience_in_years": 4,
            "technical_skills": ["Python", "PyTorch", "LLMOps", "Prompt Engineering", "RAG", "Langchain"],
            "ai_fit_score": 95,
            "education": "M.S. in AI, Stanford University",
            "previous_companies": [
                {"name": "OpenAI", "years": "2", "job_responsibilities": "Worked on fine-tuning LLMs for specialized domains"},
                {"name": "Google Research", "years": "2", "job_responsibilities": "Developed RAG systems for information retrieval"}
            ]
        },
        {
            "name": "Priya Sharma",
            "email": "priya.sharma@example.com",
            "phone": "555-234-5678",
            "resume_url": "https://example.com/priya_sharma_resume.pdf",
            "job_id": job_id,
            "total_experience_in_years": 3,
            "technical_skills": ["Python", "Transformers", "HuggingFace", "LLM Fine-tuning", "Vector Databases", "GenAI"],
            "ai_fit_score": 92,
            "education": "Ph.D. in NLP, MIT",
            "previous_companies": [
                {"name": "Anthropic", "years": "1.5", "job_responsibilities": "Specialized in responsible AI and safety alignment"},
                {"name": "Microsoft Research", "years": "1.5", "job_responsibilities": "Built multimodal AI systems"}
            ]
        },
        {
            "name": "Alex Johnson",
            "email": "alex.johnson@example.com",
            "phone": "555-345-6789",
            "resume_url": "https://example.com/alex_johnson_resume.pdf",
            "job_id": job_id,
            "total_experience_in_years": 2,
            "technical_skills": ["Python", "LangChain", "LlamaIndex", "GenAI Applications", "MLOps", "AI Ethics"],
            "ai_fit_score": 88,
            "education": "B.S. in Computer Science, UC Berkeley",
            "previous_companies": [
                {"name": "Meta AI", "years": "2", "job_responsibilities": "Developed GenAI applications for content generation"}
            ]
        },
        {
            "name": "Mei Lin",
            "email": "mei.lin@example.com",
            "phone": "555-456-7890",
            "resume_url": "https://example.com/mei_lin_resume.pdf",
            "job_id": job_id,
            "total_experience_in_years": 5,
            "technical_skills": ["Python", "LLM Deployment", "Prompt Engineering", "Model Evaluation", "Vector Search"],
            "ai_fit_score": 91,
            "education": "M.S. in Machine Learning, Carnegie Mellon",
            "previous_companies": [
                {"name": "Cohere", "years": "3", "job_responsibilities": "Led embeddings team for enterprise applications"},
                {"name": "NVIDIA", "years": "2", "job_responsibilities": "Optimized LLM inference for cloud and edge"}
            ]
        },
        {
            "name": "James Wilson",
            "email": "james.wilson@example.com",
            "phone": "555-567-8901",
            "resume_url": "https://example.com/james_wilson_resume.pdf",
            "job_id": job_id,
            "total_experience_in_years": 3,
            "technical_skills": ["Python", "Fine-tuning", "RLHF", "MLOps", "Web App Development"],
            "ai_fit_score": 82,
            "education": "B.S. in AI, Stanford University",
            "previous_companies": [
                {"name": "Stability AI", "years": "1", "job_responsibilities": "Worked on text-to-image models"},
                {"name": "Hugging Face", "years": "2", "job_responsibilities": "Contributed to open-source LLM tools"}
            ]
        }
    ]
    
    # Create candidates in the database
    created_candidates = []
    
    for candidate_data in sample_candidates:
        try:
            # Add unique id to each candidate
            import uuid
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

def shortlist_by_role(role_name="GenAI Specialist", number_of_candidates=2):
    """Shortlist candidates by role name using the specialized agent"""
    print(f"Shortlisting top {number_of_candidates} candidates for {role_name} role...")
    
    shortlist_data = {
        "role_name": role_name,
        "number_of_candidates": number_of_candidates
    }
    
    try:
        # First try the specialized route that directly uses the CrewAI agent
        shortlist_response = requests.post(
            f"{API_BASE_URL}/specialized/shortlist-by-role",
            json=shortlist_data,
            headers=HEADERS
        )
        
        if shortlist_response.status_code == 200:
            print("✅ Shortlisting process started using specialized agent")
            print("\nResponse from specialized agent:")
            pprint(shortlist_response.json())
            
            # Give the background task time to complete
            print("\nWaiting for the shortlisting process to complete (30 seconds)...")
            time.sleep(30)
            
            # Now check for shortlisted candidates by looking for the job first
            # Find job ID for this role
            search_response = requests.get(
                f"{API_BASE_URL}/jobs/search?role_name={role_name.replace(' ', '%20')}",
                headers=HEADERS
            )
            
            if search_response.status_code == 200:
                jobs = search_response.json()
                if jobs and len(jobs) > 0:
                    job_id = jobs[0].get('id', jobs[0].get('job_id'))
                    
                    # Check for shortlisted candidates using job ID
                    interviews_response = requests.get(
                        f"{API_BASE_URL}/interviews/job/{job_id}",
                        headers=HEADERS
                    )
                    
                    if interviews_response.status_code == 200:
                        interviews = interviews_response.json()
                        if interviews and len(interviews) > 0:
                            print(f"\n✅ Successfully shortlisted {len(interviews)} candidates")
                            print("\nShortlisted Candidates:")
                            
                            for i, interview in enumerate(interviews, 1):
                                print(f"\n{i}. {interview.get('candidate_name', 'Unknown')}")
                                print(f"   Email: {interview.get('candidate_email', 'Unknown')}")
                                print(f"   Status: {interview.get('status', 'Unknown')}")
                            
                            return interviews
                        else:
                            print("\n❌ No shortlisted candidates found in interview_candidates collection")
                    else:
                        print(f"\n❌ Error getting interview candidates: {interviews_response.status_code}")
                else:
                    print(f"\n❌ No job found with role name '{role_name}'")
            else:
                print(f"\n❌ Error searching for job: {search_response.status_code}")
                
            return None
        else:
            print(f"❌ Error starting shortlisting process: {shortlist_response.status_code}")
            print(shortlist_response.text)
            
            # Try alternative method if the specialized agent failed
            print("\nTrying alternative shortlisting method...")
            return shortlist_by_direct_service(role_name, number_of_candidates)
            
    except Exception as e:
        print(f"❌ Error in shortlisting process: {str(e)}")
        # Try alternative method if the specialized agent failed
        print("\nTrying alternative shortlisting method...")
        return shortlist_by_direct_service(role_name, number_of_candidates)

def shortlist_by_direct_service(role_name="GenAI Specialist", number_of_candidates=2):
    """Shortlist candidates using the direct service instead of the agent"""
    print(f"Shortlisting using direct service for {role_name}...")
    
    try:
        # First find the job ID for this role
        search_response = requests.get(
            f"{API_BASE_URL}/jobs/search?role_name={role_name.replace(' ', '%20')}",
            headers=HEADERS
        )
        
        if search_response.status_code == 200:
            jobs = search_response.json()
            if jobs and len(jobs) > 0:
                job_id = jobs[0].get('id', jobs[0].get('job_id'))
                
                # Use the regular shortlist endpoint
                shortlist_data = {
                    "job_id": job_id,
                    "number_of_candidates": number_of_candidates
                }
                
                shortlist_response = requests.post(
                    f"{API_BASE_URL}/shortlist/",
                    json=shortlist_data,
                    headers=HEADERS
                )
                
                if shortlist_response.status_code == 200:
                    result = shortlist_response.json()
                    print("\n✅ Direct shortlisting completed")
                    print("\nShortlisted Candidates:")
                    
                    for i, candidate in enumerate(result.get('candidates', []), 1):
                        print(f"\n{i}. {candidate.get('name', 'Unknown')}")
                        print(f"   Email: {candidate.get('email', 'Unknown')}")
                        print(f"   AI Fit Score: {candidate.get('ai_fit_score', 'Unknown')}")
                    
                    print(f"\nCreated {len(result.get('interview_records', []))} interview records")
                    return result
                else:
                    print(f"\n❌ Error with direct shortlisting: {shortlist_response.status_code}")
                    print(shortlist_response.text)
            else:
                print(f"\n❌ No job found with role name '{role_name}'")
        else:
            print(f"\n❌ Error searching for job: {search_response.status_code}")
            
        return None
    except Exception as e:
        print(f"❌ Error in direct shortlisting: {str(e)}")
        return None

def main():
    """Main function to set up and shortlist GenAI Specialist candidates"""
    print("\n" + "=" * 80)
    print(" SHORTLISTING GENAI SPECIALIST CANDIDATES ".center(80, "="))
    print("=" * 80 + "\n")
    
    # Step 1: Create or get GenAI Specialist job
    job = create_genai_specialist_job()
    if not job:
        print("❌ Failed to create or find GenAI Specialist job. Aborting.")
        return
    
    job_id = job.get('id', job.get('job_id'))
    if not job_id:
        print("❌ Could not determine job ID. Aborting.")
        return
    
    # Step 2: Create sample candidates if needed
    candidates = create_sample_candidates(job_id)
    if not candidates or len(candidates) < 3:
        print("❌ Failed to create enough sample candidates. Aborting.")
        return
    
    # Step 3: Shortlist candidates by role name
    shortlisted = shortlist_by_role("GenAI Specialist", 2)
    
    # Display final result
    if shortlisted:
        print("\n" + "=" * 80)
        print(" SHORTLISTING SUCCESSFUL ".center(80, "="))
        print("=" * 80)
        print("\n✅ Successfully shortlisted GenAI Specialist candidates!")
    else:
        print("\n" + "=" * 80)
        print(" SHORTLISTING FAILED ".center(80, "="))
        print("=" * 80)
        print("\n❌ Failed to shortlist GenAI Specialist candidates.")
    
    print("\n" + "=" * 80)
    print(" PROCESS COMPLETED ".center(80, "="))
    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()
