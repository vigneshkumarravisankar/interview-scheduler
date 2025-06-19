"""
Core interview candidate and interviewer management functionality
"""
import uuid
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
    def assign_interviewers(no_of_interviews: int, specific_interviewers: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Assign interviewers for each interview round following specific rules:
        - Minimum 2 rounds: Manager, then HR
        - Maximum 4 rounds: 2 Technical rounds, then Manager, then HR
        - If specific interviewers are provided, use them in the given order
        
        Args:
            no_of_interviews: Number of interview rounds
            specific_interviewers: Optional list of interviewer IDs to use
        
        Returns:
            List of interviewer assignments, one per round
        """
        try:
            # Get all available interviewers
            available_interviewers = InterviewCoreService.get_all_interviewers()
            
            # If no interviewers found, create some sample interviewers
            if not available_interviewers:
                print("No interviewers found, using sample interviewers")
                sample_interviewers = [
                    {
                        "id": str(uuid.uuid4()),
                        "name": "John Smith",
                        "email": "john.smith@example.com",
                        "designation": "Technical Lead",
                        "expertise": ["Engineering"]
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Sarah Johnson",
                        "email": "sarah.johnson@example.com",
                        "designation": "HR Manager",
                        "expertise": ["Human Resources"]
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Michael Chen",
                        "email": "michael.chen@example.com",
                        "designation": "Senior Developer",
                        "expertise": ["Engineering"]
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Priya Patel",
                        "email": "priya.patel@example.com",
                        "designation": "Product Manager",
                        "expertise": ["Management"]
                    }
                ]
                
                # Save the sample interviewers to the database
                for interviewer in sample_interviewers:
                    FirestoreDB.create_document(InterviewCoreService.INTERVIEWERS_COLLECTION, interviewer)
                
                available_interviewers = sample_interviewers
            
            # Create a dictionary of interviewers by ID
            interviewers_by_id = {i.get('id'): i for i in available_interviewers}
            
            # Filter interviewers by expertise
            technical_interviewers = []
            manager_interviewers = []
            hr_interviewers = []
            
            for interviewer in available_interviewers:
                expertise_list = interviewer.get('expertise', [])
                # Handle both string and array formats for expertise
                if isinstance(expertise_list, list):
                    # Check each expertise in the list
                    for exp in expertise_list:
                        exp_lower = exp.lower() if exp else ""
                        if exp_lower in ['engineering', 'technical']:
                            technical_interviewers.append(interviewer)
                            break
                        elif exp_lower in ['management', 'manager']:
                            manager_interviewers.append(interviewer)
                            break
                        elif exp_lower in ['hr', 'human resources']:
                            hr_interviewers.append(interviewer)
                            break
                elif isinstance(expertise_list, str):
                    # Handle string format
                    exp_lower = expertise_list.lower()
                    if exp_lower in ['engineering', 'technical']:
                        technical_interviewers.append(interviewer)
                    elif exp_lower in ['management', 'manager']:
                        manager_interviewers.append(interviewer)
                    elif exp_lower in ['hr', 'human resources']:
                        hr_interviewers.append(interviewer)
                
                # Fall back to department if no relevant expertise is found
                elif interviewer.get('department'):
                    dept_lower = interviewer.get('department').lower()
                    if dept_lower in ['engineering', 'technical']:
                        technical_interviewers.append(interviewer)
                    elif dept_lower in ['management', 'manager']:
                        manager_interviewers.append(interviewer)
            
            print("---------------------",manager_interviewers, hr_interviewers, technical_interviewers)
            
            
            if not manager_interviewers:
                manager_interviewers = available_interviewers[0:1] if available_interviewers else []
                
            
            if not hr_interviewers:
                hr_interviewers = available_interviewers[-1:] if available_interviewers else []
            
            # Assign interviewers for each round based on rules
            interviewer_assignments = []
            
            # If specific interviewers are provided, use them
            print(specific_interviewers)
            if specific_interviewers and len(specific_interviewers) >= no_of_interviews:
                for i in range(no_of_interviews):
                    interviewer_id = specific_interviewers[i]
                    interviewer = interviewers_by_id.get(interviewer_id, available_interviewers[i % len(available_interviewers)])
                    interviewer_assignments.append({
                        "interviewer_id": interviewer.get("id"),
                        "interviewer_email": interviewer.get("email"),
                        "interviewer_name": interviewer.get("name"),
                        "expertise": interviewer.get("expertise"),
                        "isSelectedForNextRound": None,
                        "feedback": None,
                        "rating_out_of_10": None
                    })
            else:
                # Follow the standard interview pattern based on number of rounds
                # Minimum 2 rounds: Manager, then HR
                # Maximum 4 rounds: 2 Technical rounds, then Manager, then HR
                
                # Validate no_of_interviews
                if no_of_interviews < 2:
                    print(no_of_interviews)
                    no_of_interviews = 2  # Minimum 2 rounds
                if no_of_interviews > 4:
                    no_of_interviews = 4  # Maximum 4 rounds
                
                if no_of_interviews == 2:
                # Round 1: Manager (with empty list check)
                    if not manager_interviewers:
                        print("No manager interviewers available, using first available interviewer")
                        manager = available_interviewers[0] if available_interviewers else {
                            "id": str(uuid.uuid4()),
                            "name": "Default Manager",
                            "email": "manager@example.com",
                            "expertise": ["Management"]
                        }
                    else:
                        manager = manager_interviewers[0]
                    interviewer_assignments.append({
                        "interviewer_id": manager.get("id"),
                        "interviewer_email": manager.get("email"),
                        "interviewer_name": manager.get("name"),
                        "expertise": manager.get("expertise") or manager.get("department"),
                        "isSelectedForNextRound": None,
                        "feedback": None,
                        "rating_out_of_10": None
                    })
                    
                    # Round 2: HR (with empty list check)
                    if not hr_interviewers:
                        print("No HR interviewers available, using last available interviewer or default")
                        hr = available_interviewers[-1] if available_interviewers else {
                            "id": str(uuid.uuid4()),
                            "name": "Default HR",
                            "email": "hr@example.com",
                            "expertise": ["Human Resources"]
                        }
                    else:
                        hr = hr_interviewers[0]
                    interviewer_assignments.append({
                        "interviewer_id": hr.get("id"),
                        "interviewer_email": hr.get("email"),
                        "interviewer_name": hr.get("name"),
                        "expertise": hr.get("expertise") or hr.get("department"),
                        "isSelectedForNextRound": None,
                        "feedback": None,
                        "rating_out_of_10": None
                    })
                
                elif no_of_interviews == 3:
                    # Round 1: Technical
                    tech = technical_interviewers[0]
                    interviewer_assignments.append({
                        "interviewer_id": tech.get("id"),
                        "interviewer_email": tech.get("email"),
                        "interviewer_name": tech.get("name"),
                        "expertise": tech.get("expertise") or tech.get("department"),
                        "isSelectedForNextRound": None,
                        "feedback": None,
                        "rating_out_of_10": None
                    })
                    
                    # Round 2: Manager
                    manager = manager_interviewers[0]
                    interviewer_assignments.append({
                        "interviewer_id": manager.get("id"),
                        "interviewer_email": manager.get("email"),
                        "interviewer_name": manager.get("name"),
                        "expertise": manager.get("expertise") or manager.get("department"),
                        "isSelectedForNextRound": None,
                        "feedback": None,
                        "rating_out_of_10": None
                    })
                    
                    # Round 3: HR
                    hr = hr_interviewers[0]
                    interviewer_assignments.append({
                        "interviewer_id": hr.get("id"),
                        "interviewer_email": hr.get("email"),
                        "interviewer_name": hr.get("name"),
                        "expertise": hr.get("expertise") or hr.get("department"),
                        "isSelectedForNextRound": None,
                        "feedback": None,
                        "rating_out_of_10": None
                    })
                    
                elif no_of_interviews == 4:
                    # Round 1: Technical 1
                    tech1 = technical_interviewers[0]
                    interviewer_assignments.append({
                        "interviewer_id": tech1.get("id"),
                        "interviewer_email": tech1.get("email"),
                        "interviewer_name": tech1.get("name"),
                        "expertise": tech1.get("expertise") or tech1.get("department"),
                        "isSelectedForNextRound": None,
                        "feedback": None,
                        "rating_out_of_10": None
                    })
                    
                    # Round 2: Technical 2 (different interviewer if possible)
                    tech2 = technical_interviewers[1] if len(technical_interviewers) > 1 else technical_interviewers[0]
                    interviewer_assignments.append({
                        "interviewer_id": tech2.get("id"),
                        "interviewer_email": tech2.get("email"),
                        "interviewer_name": tech2.get("name"),
                        "expertise": tech2.get("expertise") or tech2.get("department"),
                        "isSelectedForNextRound": None,
                        "feedback": None,
                        "rating_out_of_10": None
                    })
                    
                    # Round 3: Manager
                    manager = manager_interviewers[0]
                    interviewer_assignments.append({
                        "interviewer_id": manager.get("id"),
                        "interviewer_email": manager.get("email"),
                        "interviewer_name": manager.get("name"),
                        "expertise": manager.get("expertise") or manager.get("department"),
                        "isSelectedForNextRound": None,
                        "feedback": None,
                        "rating_out_of_10": None
                    })
                    
                    # Round 4: HR
                    hr = hr_interviewers[0]
                    interviewer_assignments.append({
                        "interviewer_id": hr.get("id"),
                        "interviewer_email": hr.get("email"),
                        "interviewer_name": hr.get("name"),
                        "expertise": hr.get("expertise") or hr.get("department"),
                        "isSelectedForNextRound": None,
                        "feedback": None,
                        "rating_out_of_10": None
                    })
            
            return interviewer_assignments
        except Exception as e:
            print(f"Error assigning interviewers: {e}")
            return []
