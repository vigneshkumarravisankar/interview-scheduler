"""
Core interview candidate and interviewer management functionality
"""
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from app.database.firebase_db import FirestoreDB


class InterviewCoreService:
    """Core service for interview candidate and interviewer management"""
    
    COLLECTION_NAME = "interview_candidates"
    INTERVIEWERS_COLLECTION = "interviewers"
    
    @staticmethod
    def create_interview_candidate(candidate_data: Dict[str, Any]) -> str:
        """
        Create a new interview candidate document in Firestore
        
        Args:
            candidate_data: Dictionary with interview candidate information
        
        Returns:
            ID of the created document
        """
        try:
            # Generate a unique ID if not provided
            if 'id' not in candidate_data:
                candidate_data['id'] = str(uuid.uuid4())
            
            # Add the document to the collection
            doc_id = FirestoreDB.create_document(
                InterviewCoreService.COLLECTION_NAME,
                candidate_data
            )
            
            return doc_id
        except Exception as e:
            print(f"Error creating interview candidate: {e}")
            raise
    
    @staticmethod
    def get_interview_candidate(candidate_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an interview candidate by ID
        
        Args:
            candidate_id: ID of the interview candidate
        
        Returns:
            Interview candidate data or None if not found
        """
        return FirestoreDB.get_document(InterviewCoreService.COLLECTION_NAME, candidate_id)
    
    @staticmethod
    def get_all_interview_candidates() -> List[Dict[str, Any]]:
        """
        Get all interview candidates
        
        Returns:
            List of all interview candidates
        """
        return FirestoreDB.get_all_documents(InterviewCoreService.COLLECTION_NAME)
    
    @staticmethod
    def get_interview_candidates_by_job_id(job_id: str) -> List[Dict[str, Any]]:
        """
        Get interview candidates for a specific job
        
        Args:
            job_id: ID of the job
        
        Returns:
            List of interview candidates for the job
        """
        all_candidates = InterviewCoreService.get_all_interview_candidates()
        return [c for c in all_candidates if c.get('job_id') == job_id]
    
    @staticmethod
    def update_interview_candidate(candidate_id: str, data: Dict[str, Any]) -> None:
        """
        Update an interview candidate
        
        Args:
            candidate_id: ID of the interview candidate
            data: New data to update
        """
        FirestoreDB.update_document(InterviewCoreService.COLLECTION_NAME, candidate_id, data)
    
    @staticmethod
    def delete_interview_candidate(candidate_id: str) -> None:
        """
        Delete an interview candidate
        
        Args:
            candidate_id: ID of the interview candidate
        """
        FirestoreDB.delete_document(InterviewCoreService.COLLECTION_NAME, candidate_id)
    
    @staticmethod
    def get_all_interviewers() -> List[Dict[str, Any]]:
        """
        Get all interviewers from the interviewers collection
        
        Returns:
            List of all interviewers
        """
        return FirestoreDB.get_all_documents(InterviewCoreService.INTERVIEWERS_COLLECTION)
    
    @staticmethod
    def get_interviewers_by_expertise(expertise: str) -> List[Dict[str, Any]]:
        """
        Get interviewers filtered by expertise
        
        Args:
            expertise: Expertise area to filter by (e.g., "Engineering", "HR", "Management")
        
        Returns:
            List of interviewers with the specified expertise
        """
        all_interviewers = InterviewCoreService.get_all_interviewers()
        matching_interviewers = []
        
        for interviewer in all_interviewers:
            expertise_list = interviewer.get('expertise', [])
            # Handle both string and array formats for expertise
            if isinstance(expertise_list, list):
                if any(exp.lower() == expertise.lower() for exp in expertise_list if exp):
                    matching_interviewers.append(interviewer)
            elif isinstance(expertise_list, str) and expertise_list.lower() == expertise.lower():
                matching_interviewers.append(interviewer)
        
        return matching_interviewers
    
    @staticmethod
    def _get_technical_interviewers(available_interviewers: List[Dict[str, Any]], job_skills: Optional[List[str]] = None, job_role: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get technical interviewers matched to the specific job role and skills
        
        Args:
            available_interviewers: List of all available interviewers
            job_skills: Optional list of job skills to match against interviewer expertise
            job_role: Optional job role name for role-specific matching
        
        Returns:
            List of technical interviewers sorted by role and skill match relevance
        """
        technical_interviewers = []
        
        # Define role-specific expertise mappings
        role_expertise_map = {
            'frontend': ['frontend', 'react', 'angular', 'vue', 'javascript', 'typescript', 'html', 'css', 'ui/ux'],
            'backend': ['backend', 'api', 'server', 'database', 'java', 'python', 'node.js', 'spring', 'django'],
            'fullstack': ['fullstack', 'full-stack', 'frontend', 'backend', 'javascript', 'react', 'node.js'],
            'mobile': ['mobile', 'android', 'ios', 'react native', 'flutter', 'swift', 'kotlin'],
            'devops': ['devops', 'cloud', 'aws', 'azure', 'docker', 'kubernetes', 'ci/cd', 'infrastructure'],
            'data': ['data science', 'machine learning', 'ai', 'python', 'r', 'sql', 'analytics', 'big data'],
            'qa': ['qa', 'testing', 'automation', 'selenium', 'quality assurance', 'test'],
            'security': ['security', 'cybersecurity', 'penetration testing', 'encryption', 'compliance'],
        }
        
        # Extract job role category
        job_role_category = None
        if job_role:
            job_role_lower = job_role.lower()
            for category, keywords in role_expertise_map.items():
                if any(keyword in job_role_lower for keyword in keywords[:3]):  # Check first 3 main keywords
                    job_role_category = category
                    break
        
        print(f"Job role: {job_role}, Category: {job_role_category}")
        
        for interviewer in available_interviewers:
            expertise_list = interviewer.get('expertise', [])
            department = interviewer.get('department', '')
            
            # Check if interviewer has technical expertise
            is_technical = False
            skill_matches = 0
            role_matches = 0
            
            # Handle both string and array formats for expertise
            if isinstance(expertise_list, list):
                for exp in expertise_list:
                    exp_lower = exp.lower() if exp else ""
                    
                    # Check for general technical expertise
                    if exp_lower in ['engineering', 'technical', 'developer', 'software', 'programming']:
                        is_technical = True
                    
                    # Count role-specific matches
                    if job_role_category and job_role_category in role_expertise_map:
                        role_keywords = role_expertise_map[job_role_category]
                        for keyword in role_keywords:
                            if keyword in exp_lower:
                                role_matches += 1
                                is_technical = True
                    
                    # Count general skill matches if job_skills provided
                    if job_skills:
                        for skill in job_skills:
                            if skill.lower() in exp_lower:
                                skill_matches += 1
                                
            elif isinstance(expertise_list, str):
                exp_lower = expertise_list.lower()
                
                # Check for general technical expertise
                if exp_lower in ['engineering', 'technical', 'developer', 'software', 'programming']:
                    is_technical = True
                
                # Count role-specific matches
                if job_role_category and job_role_category in role_expertise_map:
                    role_keywords = role_expertise_map[job_role_category]
                    for keyword in role_keywords:
                        if keyword in exp_lower:
                            role_matches += 1
                            is_technical = True
                
                # Count general skill matches if job_skills provided
                if job_skills:
                    for skill in job_skills:
                        if skill.lower() in exp_lower:
                            skill_matches += 1
            
            # Fall back to department if no relevant expertise is found
            if not is_technical and department:
                dept_lower = department.lower()
                if dept_lower in ['engineering', 'technical', 'development', 'software']:
                    is_technical = True
            
            if is_technical:
                # Add match scores for sorting (role matches weighted higher)
                interviewer_copy = interviewer.copy()
                interviewer_copy['_role_match_score'] = role_matches
                interviewer_copy['_skill_match_score'] = skill_matches
                interviewer_copy['_total_match_score'] = (role_matches * 3) + skill_matches  # Role matches weighted 3x
                technical_interviewers.append(interviewer_copy)
        
        # Sort by total match score (role + skill matches) - highest first
        technical_interviewers.sort(key=lambda x: x.get('_total_match_score', 0), reverse=True)
        
        return technical_interviewers
    
    @staticmethod
    def _get_manager_interviewers(available_interviewers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Get manager/management interviewers
        
        Args:
            available_interviewers: List of all available interviewers
        
        Returns:
            List of manager interviewers
        """
        manager_interviewers = []
        
        for interviewer in available_interviewers:
            expertise_list = interviewer.get('expertise', [])
            department = interviewer.get('department', '')
            
            # Check if interviewer has management expertise
            is_manager = False
            
            # Handle both string and array formats for expertise
            if isinstance(expertise_list, list):
                for exp in expertise_list:
                    exp_lower = exp.lower() if exp else ""
                    if exp_lower in ['management', 'manager', 'lead', 'director', 'supervisor']:
                        is_manager = True
                        break
            elif isinstance(expertise_list, str):
                exp_lower = expertise_list.lower()
                if exp_lower in ['management', 'manager', 'lead', 'director', 'supervisor']:
                    is_manager = True
            
            # Fall back to department if no relevant expertise is found
            if not is_manager and department:
                dept_lower = department.lower()
                if dept_lower in ['management', 'leadership', 'executive']:
                    is_manager = True
            
            if is_manager:
                manager_interviewers.append(interviewer)
        
        return manager_interviewers
    
    @staticmethod
    def _get_hr_interviewers(available_interviewers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Get HR/Human Resources interviewers
        
        Args:
            available_interviewers: List of all available interviewers
        
        Returns:
            List of HR interviewers
        """
        hr_interviewers = []
        
        for interviewer in available_interviewers:
            expertise_list = interviewer.get('expertise', [])
            department = interviewer.get('department', '')
            
            # Check if interviewer has HR expertise
            is_hr = False
            
            # Handle both string and array formats for expertise
            if isinstance(expertise_list, list):
                for exp in expertise_list:
                    exp_lower = exp.lower() if exp else ""
                    if exp_lower in ['hr', 'human resources', 'people', 'recruiting', 'talent']:
                        is_hr = True
                        break
            elif isinstance(expertise_list, str):
                exp_lower = expertise_list.lower()
                if exp_lower in ['hr', 'human resources', 'people', 'recruiting', 'talent']:
                    is_hr = True
            
            # Fall back to department if no relevant expertise is found
            if not is_hr and department:
                dept_lower = department.lower()
                if dept_lower in ['hr', 'human resources', 'people', 'recruiting']:
                    is_hr = True
            
            if is_hr:
                hr_interviewers.append(interviewer)
        
        return hr_interviewers
    
    @staticmethod
    def _create_interviewer_assignment(interviewer: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a standardized interviewer assignment object
        
        Args:
            interviewer: Interviewer data from Firebase
        
        Returns:
            Formatted interviewer assignment
        """
        return {
            "interviewer_id": interviewer.get("id"),
            "interviewer_email": interviewer.get("email"),
            "interviewer_name": interviewer.get("name"),
            "expertise": interviewer.get("expertise") or interviewer.get("department"),
            "isSelectedForNextRound": None,
            "feedback": None,
            "rating_out_of_10": None
        }
    
    @staticmethod
    def assign_interviewers(no_of_interviews: int, specific_interviewers: Optional[List[str]] = None, job_skills: Optional[List[str]] = None, job_role: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Assign interviewers for each interview round following specific rules:
        - Technical rounds: Match based on job skills/role requirements with interviewer expertise
        - Manager rounds: Assign management experts
        - HR rounds: Assign HR experts
        - Only use interviewers from the Firebase interviewers collection
        
        Args:
            no_of_interviews: Number of interview rounds
            specific_interviewers: Optional list of interviewer IDs to use
            job_skills: Optional list of job skills/technologies for technical interviewer matching
        
        Returns:
            List of interviewer assignments, one per round
        """
        try:
            # Get all available interviewers from Firebase
            available_interviewers = InterviewCoreService.get_all_interviewers()
            
            # If no interviewers found, return empty list (don't create sample data)
            if not available_interviewers:
                print("❌ No interviewers found in Firebase collection. Please add interviewers to the system.")
                return []
            
            # Create a dictionary of interviewers by ID
            interviewers_by_id = {i.get('id'): i for i in available_interviewers}
            
            # Filter and match interviewers by expertise and skills
            technical_interviewers = InterviewCoreService._get_technical_interviewers(available_interviewers, job_skills, job_role)
            manager_interviewers = InterviewCoreService._get_manager_interviewers(available_interviewers)
            hr_interviewers = InterviewCoreService._get_hr_interviewers(available_interviewers)
            
            print(f"Found {len(technical_interviewers)} technical, {len(manager_interviewers)} manager, {len(hr_interviewers)} HR interviewers")
            
            # If no interviewers found for required categories, return empty list
            if not manager_interviewers and not hr_interviewers and not technical_interviewers:
                print("❌ No suitable interviewers found for any category. Please ensure interviewers are properly categorized.")
                return []
            
            # Assign interviewers for each round based on rules
            interviewer_assignments = []
            
            # If specific interviewers are provided, use them
            if specific_interviewers and len(specific_interviewers) >= no_of_interviews:
                print(f"Using specific interviewers: {specific_interviewers}")
                for i in range(no_of_interviews):
                    interviewer_id = specific_interviewers[i]
                    interviewer = interviewers_by_id.get(interviewer_id)
                    if interviewer:
                        interviewer_assignments.append(InterviewCoreService._create_interviewer_assignment(interviewer))
                    else:
                        print(f"❌ Interviewer with ID {interviewer_id} not found")
                        return []
            else:
                # Follow the standard interview pattern based on number of rounds
                # Validate no_of_interviews
                if no_of_interviews < 2:
                    no_of_interviews = 2  # Minimum 2 rounds
                if no_of_interviews > 4:
                    no_of_interviews = 4  # Maximum 4 rounds
                
                if no_of_interviews == 2:
                    # Round 1: Manager
                    if manager_interviewers:
                        manager = manager_interviewers[0]
                        interviewer_assignments.append(InterviewCoreService._create_interviewer_assignment(manager))
                    else:
                        print("❌ No manager interviewers available for Round 1")
                        return []
                    
                    # Round 2: HR
                    if hr_interviewers:
                        hr = hr_interviewers[0]
                        interviewer_assignments.append(InterviewCoreService._create_interviewer_assignment(hr))
                    else:
                        print("❌ No HR interviewers available for Round 2")
                        return []
                
                elif no_of_interviews == 3:
                    # Round 1: Technical (skill-matched)
                    if technical_interviewers:
                        tech = technical_interviewers[0]
                        interviewer_assignments.append(InterviewCoreService._create_interviewer_assignment(tech))
                    else:
                        print("❌ No technical interviewers available for Round 1")
                        return []
                    
                    # Round 2: Manager
                    if manager_interviewers:
                        manager = manager_interviewers[0]
                        interviewer_assignments.append(InterviewCoreService._create_interviewer_assignment(manager))
                    else:
                        print("❌ No manager interviewers available for Round 2")
                        return []
                    
                    # Round 3: HR
                    if hr_interviewers:
                        hr = hr_interviewers[0]
                        interviewer_assignments.append(InterviewCoreService._create_interviewer_assignment(hr))
                    else:
                        print("❌ No HR interviewers available for Round 3")
                        return []
                    
                elif no_of_interviews == 4:
                    # Round 1: Technical 1 (best skill match)
                    if technical_interviewers:
                        tech1 = technical_interviewers[0]
                        interviewer_assignments.append(InterviewCoreService._create_interviewer_assignment(tech1))
                    else:
                        print("❌ No technical interviewers available for Round 1")
                        return []
                    
                    # Round 2: Technical 2 (second best skill match or different interviewer)
                    if len(technical_interviewers) > 1:
                        tech2 = technical_interviewers[1]
                        interviewer_assignments.append(InterviewCoreService._create_interviewer_assignment(tech2))
                    elif technical_interviewers:
                        # Use same technical interviewer if only one available
                        tech2 = technical_interviewers[0]
                        interviewer_assignments.append(InterviewCoreService._create_interviewer_assignment(tech2))
                    else:
                        print("❌ No technical interviewers available for Round 2")
                        return []
                    
                    # Round 3: Manager
                    if manager_interviewers:
                        manager = manager_interviewers[0]
                        interviewer_assignments.append(InterviewCoreService._create_interviewer_assignment(manager))
                    else:
                        print("❌ No manager interviewers available for Round 3")
                        return []
                    
                    # Round 4: HR
                    if hr_interviewers:
                        hr = hr_interviewers[0]
                        interviewer_assignments.append(InterviewCoreService._create_interviewer_assignment(hr))
                    else:
                        print("❌ No HR interviewers available for Round 4")
                        return []
            
            return interviewer_assignments
        except Exception as e:
            print(f"Error assigning interviewers: {e}")
            return []
    
    @staticmethod
    def update_interview_feedback(
        interview_candidate_id: str, 
        round_index: int, 
        feedback: str, 
        rating: int, 
        is_selected_for_next_round: str,
        interviewer_notes: Optional[str] = None
    ) -> bool:
        """
        Update feedback for a specific interview round
        
        Args:
            interview_candidate_id: ID of the interview candidate
            round_index: Index of the interview round (0-based)
            feedback: Interview feedback text
            rating: Rating out of 10
            is_selected_for_next_round: "yes", "no", or "pending"
            interviewer_notes: Optional additional notes from interviewer
        
        Returns:
            True if update was successful, False otherwise
        """
        try:
            # Get the interview candidate record
            candidate_record = InterviewCoreService.get_interview_candidate(interview_candidate_id)
            if not candidate_record:
                print(f"Interview candidate with ID {interview_candidate_id} not found")
                return False
            
            # Get feedback array
            feedback_array = candidate_record.get("feedback", [])
            
            # Validate round index
            if round_index >= len(feedback_array) or round_index < 0:
                print(f"Invalid round index {round_index}. Available rounds: 0-{len(feedback_array)-1}")
                return False
            
            # Update feedback for the specified round
            feedback_array[round_index].update({
                "feedback": feedback,
                "rating_out_of_10": rating,
                "isSelectedForNextRound": is_selected_for_next_round,
                "interviewer_notes": interviewer_notes,
                "feedback_updated_at": datetime.now().isoformat()
            })
            
            # Update completed rounds and status
            completed_rounds = sum(1 for f in feedback_array if f.get("feedback") is not None)
            
            # Determine overall status
            if is_selected_for_next_round == "no":
                status = "rejected"
            elif completed_rounds == len(feedback_array):
                # All rounds completed
                if all(f.get("isSelectedForNextRound") == "yes" for f in feedback_array if f.get("isSelectedForNextRound") is not None):
                    status = "selected"
                else:
                    status = "completed"
            else:
                status = "in_progress"
            
            # Update the document
            update_data = {
                "feedback": feedback_array,
                "completedRounds": completed_rounds,
                "status": status,
                "last_updated": datetime.now().isoformat()
            }
            
            # If selected for next round, schedule it
            if is_selected_for_next_round == "yes" and round_index + 1 < len(feedback_array):
                from app.services.interview_schedule_service import InterviewScheduleService
                InterviewScheduleService.schedule_next_round(interview_candidate_id)
            
            InterviewCoreService.update_interview_candidate(interview_candidate_id, update_data)
            
            print(f"✅ Feedback updated for round {round_index + 1} of interview candidate {interview_candidate_id}")
            return True
            
        except Exception as e:
            print(f"❌ Error updating interview feedback: {e}")
            return False
    
    @staticmethod
    def get_interview_feedback(interview_candidate_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get all feedback for an interview candidate
        
        Args:
            interview_candidate_id: ID of the interview candidate
        
        Returns:
            List of feedback records or None if not found
        """
        try:
            candidate_record = InterviewCoreService.get_interview_candidate(interview_candidate_id)
            if candidate_record:
                return candidate_record.get("feedback", [])
            return None
        except Exception as e:
            print(f"❌ Error getting interview feedback: {e}")
            return None
    
    @staticmethod
    def get_round_feedback(interview_candidate_id: str, round_index: int) -> Optional[Dict[str, Any]]:
        """
        Get feedback for a specific round
        
        Args:
            interview_candidate_id: ID of the interview candidate
            round_index: Index of the interview round (0-based)
        
        Returns:
            Feedback record for the specified round or None if not found
        """
        try:
            feedback_array = InterviewCoreService.get_interview_feedback(interview_candidate_id)
            if feedback_array and 0 <= round_index < len(feedback_array):
                return feedback_array[round_index]
            return None
        except Exception as e:
            print(f"❌ Error getting round feedback: {e}")
            return None
    
    @staticmethod
    def bulk_update_feedback(feedback_updates: List[Dict[str, Any]]) -> List[bool]:
        """
        Update feedback for multiple interview candidates/rounds
        
        Args:
            feedback_updates: List of feedback update dictionaries containing:
                - interview_candidate_id: str
                - round_index: int
                - feedback: str
                - rating: int
                - is_selected_for_next_round: str
                - interviewer_notes: Optional[str]
        
        Returns:
            List of boolean results for each update
        """
        results = []
        for update in feedback_updates:
            try:
                result = InterviewCoreService.update_interview_feedback(
                    interview_candidate_id=update.get("interview_candidate_id"),
                    round_index=update.get("round_index"),
                    feedback=update.get("feedback"),
                    rating=update.get("rating"),
                    is_selected_for_next_round=update.get("is_selected_for_next_round"),
                    interviewer_notes=update.get("interviewer_notes")
                )
                results.append(result)
            except Exception as e:
                print(f"❌ Error in bulk update for {update.get('interview_candidate_id')}: {e}")
                results.append(False)
        
        return results
    
    @staticmethod
    def get_candidates_by_status(status: str) -> List[Dict[str, Any]]:
        """
        Get interview candidates by their current status
        
        Args:
            status: Status to filter by ("scheduled", "in_progress", "completed", "selected", "rejected")
        
        Returns:
            List of interview candidates with the specified status
        """
        try:
            all_candidates = InterviewCoreService.get_all_interview_candidates()
            return [c for c in all_candidates if c.get('status') == status]
        except Exception as e:
            print(f"❌ Error getting candidates by status: {e}")
            return []
    
    @staticmethod
    def get_interviewer_feedback_summary(interviewer_id: str) -> Dict[str, Any]:
        """
        Get feedback summary for a specific interviewer
        
        Args:
            interviewer_id: ID of the interviewer
        
        Returns:
            Summary of feedback statistics for the interviewer
        """
        try:
            all_candidates = InterviewCoreService.get_all_interview_candidates()
            
            total_interviews = 0
            total_rating = 0
            selections = 0
            rejections = 0
            
            for candidate in all_candidates:
                feedback_array = candidate.get("feedback", [])
                for feedback in feedback_array:
                    if feedback.get("interviewer_id") == interviewer_id and feedback.get("feedback"):
                        total_interviews += 1
                        rating = feedback.get("rating_out_of_10", 0)
                        if rating:
                            total_rating += int(rating)
                        
                        selection = feedback.get("isSelectedForNextRound")
                        if selection == "yes":
                            selections += 1
                        elif selection == "no":
                            rejections += 1
            
            average_rating = total_rating / total_interviews if total_interviews > 0 else 0
            
            return {
                "interviewer_id": interviewer_id,
                "total_interviews": total_interviews,
                "average_rating": round(average_rating, 2),
                "selections": selections,
                "rejections": rejections,
                "selection_rate": round((selections / total_interviews * 100), 2) if total_interviews > 0 else 0
            }
            
        except Exception as e:
            print(f"❌ Error getting interviewer feedback summary: {e}")
            return {}
    
    @staticmethod
    def update_feedback_by_natural_input(
        candidate_name: str,
        job_role_name: str, 
        round_number: int,
        is_selected_for_next_round: str,
        rating_out_of_10: int,
        feedback_text: str
    ) -> bool:
        """
        Update interview feedback using natural language input
        
        Args:
            candidate_name: Name of the candidate
            job_role_name: Job role name 
            round_number: Round number (1-based, e.g., 1, 2, 3, 4)
            is_selected_for_next_round: "yes", "no", or "pending"
            rating_out_of_10: Rating from 1-10
            feedback_text: Feedback in natural language sentence
        
        Returns:
            True if update was successful, False otherwise
        """
        try:
            # Get all interview candidates
            all_candidates = InterviewCoreService.get_all_interview_candidates()
            
            # Find candidate by name and job role
            matching_candidate = None
            for candidate in all_candidates:
                candidate_name_match = candidate.get("candidate_name", "").lower() == candidate_name.lower()
                job_role_match = candidate.get("job_role", "").lower() == job_role_name.lower()
                
                if candidate_name_match and job_role_match:
                    matching_candidate = candidate
                    break
            
            if not matching_candidate:
                print(f"❌ No candidate found with name '{candidate_name}' and job role '{job_role_name}'")
                return False
            
            # Validate round number (convert from 1-based to 0-based)
            round_index = round_number - 1
            feedback_array = matching_candidate.get("feedback", [])
            
            if round_index < 0 or round_index >= len(feedback_array):
                print(f"❌ Invalid round number {round_number}. Available rounds: 1-{len(feedback_array)}")
                return False
            
            # Validate rating
            if rating_out_of_10 < 1 or rating_out_of_10 > 10:
                print(f"❌ Invalid rating {rating_out_of_10}. Must be between 1-10")
                return False
            
            # Validate selection status
            valid_selections = ["yes", "no", "pending"]
            if is_selected_for_next_round.lower() not in valid_selections:
                print(f"❌ Invalid selection status '{is_selected_for_next_round}'. Must be: {valid_selections}")
                return False
            
            # Update the feedback for the specified round
            feedback_array[round_index].update({
                "feedback": feedback_text,
                "rating_out_of_10": rating_out_of_10,
                "isSelectedForNextRound": is_selected_for_next_round.lower(),
                "feedback_updated_at": datetime.now().isoformat()
            })
            
            # Calculate completed rounds
            completed_rounds = sum(1 for f in feedback_array if f.get("feedback") is not None)
            
            # Determine overall status
            if is_selected_for_next_round.lower() == "no":
                status = "rejected"
            elif completed_rounds == len(feedback_array):
                # All rounds completed - check if all selected
                all_selected = all(
                    f.get("isSelectedForNextRound") == "yes" 
                    for f in feedback_array 
                    if f.get("isSelectedForNextRound") is not None
                )
                status = "selected" if all_selected else "completed"
            else:
                status = "in_progress"
            
            # Update next round index
            next_round_index = completed_rounds if completed_rounds < len(feedback_array) else len(feedback_array)
            
            # Prepare update data
            update_data = {
                "feedback": feedback_array,
                "completedRounds": completed_rounds,
                "nextRoundIndex": next_round_index,
                "status": status,
                "last_updated": datetime.now().isoformat()
            }
            
            # Update current_round_scheduled based on status
            if is_selected_for_next_round.lower() == "yes" and next_round_index < len(feedback_array):
                update_data["current_round_scheduled"] = False  # Next round needs to be scheduled
                
                # Trigger next round scheduling
                try:
                    from app.services.interview_schedule_service import InterviewScheduleService
                    InterviewScheduleService.schedule_next_round(matching_candidate.get("id"))
                    update_data["current_round_scheduled"] = True
                except Exception as schedule_error:
                    print(f"⚠️ Warning: Could not schedule next round: {schedule_error}")
            
            # Update the document in Firebase
            InterviewCoreService.update_interview_candidate(matching_candidate.get("id"), update_data)
            
            print(f"✅ Feedback updated for {candidate_name} - {job_role_name} - Round {round_number}")
            print(f"   Rating: {rating_out_of_10}/10")
            print(f"   Selection: {is_selected_for_next_round}")
            print(f"   Status: {status}")
            print(f"   Completed Rounds: {completed_rounds}/{len(feedback_array)}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error updating feedback by natural input: {e}")
            return False
    
    @staticmethod
    def get_candidate_by_name_and_role(candidate_name: str, job_role_name: str) -> Optional[Dict[str, Any]]:
        """
        Get interview candidate by name and job role
        
        Args:
            candidate_name: Name of the candidate
            job_role_name: Job role name
        
        Returns:
            Interview candidate data or None if not found
        """
        try:
            all_candidates = InterviewCoreService.get_all_interview_candidates()
            
            for candidate in all_candidates:
                candidate_name_match = candidate.get("candidate_name", "").lower() == candidate_name.lower()
                job_role_match = candidate.get("job_role", "").lower() == job_role_name.lower()
                
                if candidate_name_match and job_role_match:
                    return candidate
            
            return None
            
        except Exception as e:
            print(f"❌ Error getting candidate by name and role: {e}")
            return None
    
    @staticmethod
    def list_candidates_for_feedback() -> List[Dict[str, Any]]:
        """
        List all candidates with their current feedback status for easy reference
        
        Returns:
            List of candidate summaries with feedback status
        """
        try:
            all_candidates = InterviewCoreService.get_all_interview_candidates()
            candidate_summaries = []
            
            for candidate in all_candidates:
                feedback_array = candidate.get("feedback", [])
                completed_rounds = sum(1 for f in feedback_array if f.get("feedback") is not None)
                
                summary = {
                    "candidate_name": candidate.get("candidate_name"),
                    "job_role": candidate.get("job_role"),
                    "status": candidate.get("status"),
                    "completed_rounds": f"{completed_rounds}/{len(feedback_array)}",
                    "total_rounds": len(feedback_array),
                    "id": candidate.get("id"),
                    "next_round": completed_rounds + 1 if completed_rounds < len(feedback_array) else "All completed"
                }
                candidate_summaries.append(summary)
            
            return candidate_summaries
            
        except Exception as e:
            print(f"❌ Error listing candidates for feedback: {e}")
            return []
