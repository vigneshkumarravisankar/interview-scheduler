"""
Candidate shortlisting functionality
"""
import random
import string
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
from app.database.firebase_db import FirestoreDB
from app.services.candidate_service import CandidateService
from app.services.job_service import JobService
from app.services.interview_core_service import InterviewCoreService


class InterviewShortlistService:
    """Service for handling candidate shortlisting"""
    
    # Collection names
    CANDIDATES_COLLECTION = "candidates_data"
    INTERVIEW_CANDIDATES_COLLECTION = "interview_candidates"
    
    @staticmethod
    def shortlist_candidates(
        job_id: str, 
        number_of_candidates: int = 3, 
        no_of_interviews: int = 2,
        specific_interviewers: Optional[List[str]] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Shortlist candidates for a job based on their AI fit scores
        
        Args:
            job_id: ID of the job
            number_of_candidates: Number of candidates to shortlist
            no_of_interviews: Number of interview rounds to schedule
            specific_interviewers: Optional list of specific interviewer IDs to assign
        
        Returns:
            Tuple of (shortlisted candidates, created interview candidate records)
        """
        try:
            # Get job details
            job = JobService.get_job_posting(job_id)
            if not job:
                print(f"Job with ID {job_id} not found")
                return [], []
            
            # Try to get candidates using Firebase query directly for robustness
            try:
                candidates = FirestoreDB.execute_query(
                    InterviewShortlistService.CANDIDATES_COLLECTION,
                    "job_id",
                    "==",
                    job_id
                )
                
                
               
                print('candidates list',candidates)
                
                if not candidates:
                    print(f"No candidates found using direct query. Falling back to service method.")
                    candidates = CandidateService.get_candidates_by_job_id(job_id)
            except Exception as query_error:
                print(f"Error using direct Firebase query: {query_error}")
                candidates = CandidateService.get_candidates_by_job_id(job_id)
            
            # Generate emergency candidates if none found
            # if not candidates:
            #     print(f"No candidates found for job {job_id}, creating emergency candidates")
            #     # Create emergency candidates
            #     emergency_candidates = InterviewShortlistService._create_emergency_candidates(job_id, number_of_candidates)
                
            #     # Save the emergency candidates to database
            #     for candidate in emergency_candidates:
            #         candidate_id = CandidateService.create_candidate(candidate)
            #         candidate["id"] = candidate_id
                
            #     candidates = emergency_candidates
            
            # Sort candidates by AI fit score (descending)
            try:
                sorted_candidates = sorted(
                    candidates,
                    key=lambda c: int(c.get("ai_fit_score", 0)),
                    reverse=True
                )
            except (ValueError, TypeError) as e:
                print(f"Error sorting candidates by AI fit score: {e}")
                # Fall back to unsorted list
                sorted_candidates = candidates
            
            # Get the top N candidates
            shortlisted = sorted_candidates[:min(number_of_candidates, len(sorted_candidates))]
            print(f"Shortlisted {len(shortlisted)} candidates out of {len(candidates)}")
            
            # Check the interview service for existing interviews
            try:
                existing_interviews = FirestoreDB.execute_query(
                    InterviewShortlistService.INTERVIEW_CANDIDATES_COLLECTION,
                    "job_id",
                    "==",
                    job_id
                )
                
                if existing_interviews:
                    print(f"Found {len(existing_interviews)} existing interviews for job {job_id}")
            except Exception as e:
                print(f"Error checking for existing interviews: {e}")
                existing_interviews = []
            
            # Get interviewer assignments for each round
            interviewer_assignments = InterviewCoreService.assign_interviewers(
                no_of_interviews,
                specific_interviewers
            )
            
            # Create interview candidate records
            created_records = []
            
            for candidate in shortlisted:
                # Get candidate details
                candidate_name = candidate.get("name", "Candidate")
                candidate_email = candidate.get("email", "candidate@example.com")
                candidate_id = candidate.get("id", "")
                
                # Create feedback array with proper structure
                feedback_array = []
                
                # Determine round types based on no_of_interviews
                round_types = InterviewShortlistService._get_round_types(no_of_interviews)
                
                for i in range(no_of_interviews):
                    # Get round type
                    round_type = round_types[i] if i < len(round_types) else "Technical"
                    
                    # Get the department based on the round type
                    department = {
                        "Technical": "Engineering", 
                        "Manager": "Management", 
                        "HR": "Human Resources"
                    }.get(round_type, "Engineering")
                    
                    # Assign interviewer based on assignments or use placeholder
                    interviewer = interviewer_assignments[i] if i < len(interviewer_assignments) else {
                        "id": "", 
                        "name": f"{round_type} Interviewer",
                        "email": f"{round_type.lower()}_interviewer@example.com",
                        "department": department
                    }
                    
                    # Only schedule first interview initially, others will be scheduled after previous rounds
                    if i == 0:
                        # Calculate dates for the scheduled event - first round is 1 day ahead
                        days_ahead = 1  # First round is 1 day ahead
                        interview_date = datetime.now() + timedelta(days=days_ahead)
                        # Set interview time to working hours (9AM - 5PM)
                        start_time = interview_date.replace(hour=10 + (i % 6), minute=0, second=0, microsecond=0)
                        end_time = start_time + timedelta(hours=1)  # 1 hour interview
                        
                        # Format dates in ISO format with timezone
                        start_iso = start_time.strftime("%Y-%m-%dT%H:%M:%S+05:30")
                        end_iso = end_time.strftime("%Y-%m-%dT%H:%M:%S+05:30")
                        
                        # Generate unique ID for the event
                        event_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=22))
                        
                        # Generate Google Meet link
                        meet_code = ''.join(random.choices(string.ascii_lowercase, k=3)) + '-' + \
                                   ''.join(random.choices(string.ascii_lowercase, k=4)) + '-' + \
                                   ''.join(random.choices(string.ascii_lowercase, k=3))
                        meet_link = f"https://meet.google.com/{meet_code}"
                        
                        # Create formatted time (e.g., "10AM")
                        hour_12 = start_time.hour if start_time.hour <= 12 else start_time.hour - 12
                        am_pm = 'AM' if start_time.hour < 12 else 'PM'
                        formatted_time = f"{hour_12}{am_pm}"
                        
                        # Try to create an actual calendar event
                        try:
                            # Import here to avoid circular imports
                            from app.utils.calendar_service import create_calendar_event
                            from app.utils.email_notification import send_interview_notification
                            
                            # Create event summary and description
                            summary = f"Interview: {candidate_name} with {interviewer.get('name')} - Round {i+1} ({round_type})"
                            
                            # Safely access job attributes - convert Pydantic model to dict if needed
                            job_role_name = job.job_role_name if hasattr(job, 'job_role_name') else 'Unknown Position'
                            
                            description = f"""
                            Interview for {candidate_name} ({candidate_email})
                            Job: {job_role_name}
                            Round: {i+1} of {no_of_interviews} - {round_type} Round
                            Interviewer: {interviewer.get('name')} ({interviewer.get('email')})
                            
                            Please join using the Google Meet link at the scheduled time.
                            """
                            
                            # Attempt to create a real calendar event
                            calendar_event = create_calendar_event(
                                summary=summary,
                                description=description,
                                start_time=start_iso,
                                end_time=end_iso,
                                location=meet_link,
                                attendees=[
                                    {"email": interviewer.get('email')},
                                    {"email": candidate_email}
                                ]
                            )
                            
                            if calendar_event:
                                print(f"Created calendar event: {calendar_event.get('id')}")
                                event_id = calendar_event.get('id', event_id)
                                meet_link = calendar_event.get('hangoutLink', meet_link)
                                html_link = calendar_event.get('htmlLink', f"https://www.google.com/calendar/event?eid={event_id}")
                                
                                # Send email notification with proper parameters
                                additional_note = (f"Interview Round {i+1} ({round_type})\n" 
                                                  f"Scheduled for {start_time.strftime('%A, %B %d, %Y')} at {formatted_time}")
                                
                                send_interview_notification(
                                    recipient_email=candidate_email,
                                    start_time=start_iso,
                                    end_time=end_iso,
                                    meet_link=meet_link,
                                    event_id=event_id,
                                    interviewer_name=interviewer.get('name'),
                                    candidate_name=candidate_name,
                                    job_title=job.job_role_name if hasattr(job, 'job_role_name') else 'Unknown Position',
                                    additional_note=additional_note,
                                    interviewer_email=interviewer.get('email')
                                )
                        except Exception as calendar_error:
                            print(f"Error creating calendar event: {calendar_error}")
                            # Continue with mock data
                    else:
                        # For future rounds, we'll only create placeholder data
                        # These will be scheduled when the previous round is passed
                        event_id = ''
                        meet_link = ''
                        formatted_time = ''
                        start_iso = ''
                        end_iso = ''
                        html_link = ''
                    
                    # Create the feedback object
                    feedback_object = {
                        "interviewer_id": interviewer.get("id", ""),
                        "interviewer_name": interviewer.get("name", f"{round_type} Interviewer {i+1}"),
                        "interviewer_email": interviewer.get("email", f"{round_type.lower()}_interviewer@example.com"),
                        "department": department,
                        "feedback": None,
                        "isSelectedForNextRound": None,
                        "rating_out_of_10": None,
                        "meet_link": meet_link,
                        "scheduled_time": formatted_time,
                        "round_type": round_type,
                        "round_number": i + 1,
                        "scheduled_event": {
                            "end": {
                                "dateTime": end_iso,
                                "timeZone": "Asia/Kolkata"
                            },
                            "start": {
                                "dateTime": start_iso,
                                "timeZone": "Asia/Kolkata"
                            },
                            "htmlLink": html_link,
                            "id": event_id
                        } if event_id else {}
                    }
                    
                    feedback_array.append(feedback_object)
                
                # Create interview candidate record
                interview_candidate = {
                    "job_id": job_id,
                    "candidate_id": candidate.get("id"),
                    "candidate_name": candidate_name,
                    "candidate_email": candidate_email,
                    "job_role": job.job_role_name if hasattr(job, 'job_role_name') else "Unknown Position",
                    "no_of_interviews": no_of_interviews,
                    "feedback": feedback_array,
                    "completedRounds": 0,
                    "nextRoundIndex": 0,  # Index of the next round to be conducted
                    "status": "scheduled",
                    "last_updated": datetime.now().isoformat(),
                    "created_at": datetime.now().isoformat(),
                    "current_round_scheduled": True  # First round is scheduled
                }
                
                # Create document in Firestore
                doc_id = InterviewCoreService.create_interview_candidate(interview_candidate)
                
                # Add ID to the record
                interview_candidate["id"] = doc_id
                
                # Add to created records
                created_records.append(interview_candidate)
            
            return shortlisted, created_records
        except Exception as e:
            print(f"Error shortlisting candidates: {e}")
            return [], []
    
    @staticmethod
    def _get_round_types(no_of_interviews: int) -> List[str]:
        """
        Get the round types based on the number of interviews
        
        Args:
            no_of_interviews: Number of interview rounds
        
        Returns:
            List of round types in order
        """
        # Define the standard interview sequence based on the number of interviews
        if no_of_interviews == 1:
            return ["Technical"]
        elif no_of_interviews == 2:
            return ["Manager", "HR"]  # Default sequence for 2 rounds
        elif no_of_interviews == 3:
            return ["Technical", "Manager", "HR"]
        elif no_of_interviews == 4:
            return ["Technical", "Technical", "Manager", "HR"]
        elif no_of_interviews == 5:
            return ["Technical", "Technical", "Technical", "Manager", "HR"]
        else:
            # For more rounds, add more technical interviews
            technical_rounds = ["Technical"] * (no_of_interviews - 2)
            return technical_rounds + ["Manager", "HR"]
    
    @staticmethod
    def _create_emergency_candidates(job_id: str, count: int) -> List[Dict[str, Any]]:
        """
        Create emergency candidates for testing when no candidates are found
        
        Args:
            job_id: ID of the job
            count: Number of emergency candidates to create
            
        Returns:
            List of emergency candidate data
        """
        emergency_candidates = []
        
        # Get job details for relevant experience generation
        try:
            job = JobService.get_job_posting(job_id)
            # Handle Pydantic model vs dictionary
            if job:
                if hasattr(job, 'job_role_name'):
                    # It's a Pydantic model
                    job_title = job.job_role_name
                    job_description = job.job_description
                    years_needed = job.years_of_experience_needed
                else:
                    # It's a dict
                    job_title = job.get("job_role_name", "Unknown Position")
                    job_description = job.get("job_description", "")
                    years_needed = job.get("years_of_experience_needed", "3")
            else:
                job_title = "Unknown Position"
                job_description = ""
                years_needed = "3"
            
            # Parse years needed to generate appropriate candidate experience
            try:
                if "-" in years_needed:
                    min_years, max_years = years_needed.split("-")
                    min_years = int(min_years.strip())
                    max_years = int(max_years.strip())
                else:
                    min_years = int(years_needed.replace("+", "").strip())
                    max_years = min_years + 3
            except (ValueError, TypeError):
                min_years = 3
                max_years = 7
        except Exception as e:
            print(f"Error getting job details for emergency candidates: {e}")
            job_title = "Software Engineer"
            job_description = "Software development position"
            min_years = 3
            max_years = 7
        
        # Generate varied skills based on job title
        if "frontend" in job_title.lower():
            skills = [
                "HTML, CSS, JavaScript, React, Angular, Vue, TypeScript, Responsive Design",
                "JavaScript, React, Redux, CSS, HTML5, Webpack, UI/UX, Jest",
                "Angular, TypeScript, RxJS, SCSS, Webpack, Jest, Cypress, HTML5",
                "React Native, JavaScript, TypeScript, Redux, CSS-in-JS, Mobile UX, Jest"
            ]
        elif "backend" in job_title.lower():
            skills = [
                "Java, Spring Boot, Hibernate, PostgreSQL, Docker, Kubernetes, CI/CD",
                "Python, Django, FastAPI, SQL, Docker, AWS, Redis, MongoDB",
                "Node.js, Express, TypeScript, MongoDB, Redis, Docker, AWS Lambda",
                "Ruby, Rails, PostgreSQL, Redis, RSpec, Docker, AWS, GraphQL"
            ]
        elif "data" in job_title.lower():
            skills = [
                "Python, Pandas, NumPy, SQL, Tableau, Machine Learning, Statistics",
                "R, Python, SQL, Hadoop, Spark, Machine Learning, Statistical Modeling",
                "SQL, Python, Databricks, Spark, Azure, ETL, Data Modeling",
                "Python, TensorFlow, PyTorch, SQL, Big Data, AWS, Data Visualization"
            ]
        else:
            skills = [
                "Python, JavaScript, SQL, Git, Docker, AWS, Agile, CI/CD",
                "Java, Spring, Hibernate, JavaScript, Git, Jenkins, Kubernetes",
                "C#, .NET, SQL Server, JavaScript, Docker, Azure DevOps, RESTful APIs",
                "Python, Django, React, PostgreSQL, Redis, AWS, Docker, CI/CD"
            ]
        
        # Generate emergency candidates
        for i in range(count):
            # Generate years of experience between min and max years needed
            experience = random.randint(min_years, max_years)
            
            # Generate random score between 60 and 95
            score = random.randint(60, 95)
            
            # Select random skills for this candidate
            candidate_skills = skills[i % len(skills)]
            
            # Create fake companies based on experience level
            if experience > 5:
                companies = [
                    {"name": "Tech Giants Inc.", "years": "3", "job_responsibilities": f"Senior {job_title} working on enterprise applications"},
                    {"name": "Advanced Systems Ltd.", "years": str(experience - 3), "job_responsibilities": f"Lead {job_title} responsible for architecture and implementation"}
                ]
            else:
                companies = [
                    {"name": "StartupCo", "years": str(experience), "job_responsibilities": f"{job_title} developing software solutions"}
                ]
            
            # Create the candidate
            candidate = {
                "id": str(uuid.uuid4()),  # Will be replaced by Firestore
                "name": f"Emergency Candidate {i+1}",
                "email": f"emergency.candidate{i+1}@example.com",
                "phone_no": f"555-000-{1000+i}",
                "job_id": job_id,
                "total_experience_in_years": str(experience),
                "technical_skills": candidate_skills,
                "previous_companies": companies,
                "ai_fit_score": str(score),
                "resume_url": f"https://example.com/emergency_resumes/candidate{i+1}.pdf",
                "is_emergency": True  # Mark as emergency for tracking
            }
            
            emergency_candidates.append(candidate)
        
        return emergency_candidates
