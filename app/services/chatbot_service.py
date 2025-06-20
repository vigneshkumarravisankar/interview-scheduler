"""
Service for handling chatbot interactions using LangChain and OpenAI
"""
import os
import json
import uuid
import re
import logging
import time
from typing import Dict, Any, List, Optional, Tuple

# Updated imports for latest LangChain versions
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI  # Updated import
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain.memory import ConversationBufferMemory

import openai
from fastapi import HTTPException
from dotenv import load_dotenv

# Load environment variables for OpenAI API key
load_dotenv()

# Get API key from environment variable or use a default for testing
api_key = os.environ.get("OPENAI_API_KEY", "your_openai_api_key_here")

# Import standard libraries
import os
import re
import json
import logging
import uuid
import time
from typing import Dict, Any, List, Optional, Tuple, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Log to console
        logging.FileHandler("chatbot_debug.log")  # Also log to file
    ]
)
logger = logging.getLogger(__name__)

# Define valid user roles and their permissions
ROLES = {
    "HR": {
        "view_all_feedback": True,
        "add_feedback_all": True,
        "decide_next_round": True,
        "schedule_interview": True
    },
    "Recruiter": {
        "view_all_feedback": True, 
        "add_feedback_all": True,
        "decide_next_round": False,
        "schedule_interview": True
    },
    "Interviewer": {
        "view_all_feedback": False,  # Can only view their own feedback
        "add_feedback_all": False,   # Can only add feedback for assigned candidates
        "decide_next_round": False,
        "schedule_interview": False
    }
}

class RolePermissionError(Exception):
    """Exception raised for permission errors related to user roles"""

    def __init__(self, role: str, required_permission: str, message: str = None):
        self.role = role
        self.required_permission = required_permission
        self.message = message or f"Role '{role}' does not have permission to {required_permission.replace('_', ' ')}"
        super().__init__(self.message)

# Mock implementation of FirestoreDB for testing
class MockDB:
    """In-memory database for testing"""
    _data = {}  # Collection -> {doc_id -> doc_data}

    @classmethod
    def reset(cls):
        """Clear all data"""
        cls._data = {}

    @classmethod
    def collection_exists(cls, collection_name: str) -> bool:
        """Check if a collection exists"""
        return collection_name in cls._data

    @classmethod
    def create_document(cls, collection_name: str, document_data: Dict[str, Any]) -> str:
        """Create a document in a collection"""
        # Initialize the collection if it doesn't exist
        if collection_name not in cls._data:
            cls._data[collection_name] = {}

        # Get or generate the document ID
        doc_id = document_data.get("id", str(uuid.uuid4()))

        # Store a copy of the document data
        doc_data = document_data.copy()
        if "id" not in doc_data:
            doc_data["id"] = doc_id

        # Add timestamp if not present
        if "timestamp" not in doc_data:
            doc_data["timestamp"] = time.time()

        # Store the document
        cls._data[collection_name][doc_id] = doc_data

        return doc_id

    @classmethod
    def get_document(cls, collection_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID"""
        if collection_name not in cls._data or doc_id not in cls._data[collection_name]:
            return None
        return cls._data[collection_name][doc_id].copy()

    @classmethod
    def get_all_documents(cls, collection_name: str) -> List[Dict[str, Any]]:
        """Get all documents in a collection"""
        if collection_name not in cls._data:
            return []
        return [doc.copy() for doc in cls._data[collection_name].values()]

    @classmethod
    def update_document(cls, collection_name: str, doc_id: str, data: Dict[str, Any]) -> None:
        """Update a document"""
        if collection_name not in cls._data or doc_id not in cls._data[collection_name]:
            return None

        # Update existing document
        for key, value in data.items():
            cls._data[collection_name][doc_id][key] = value

        return doc_id

    @classmethod
    def delete_document(cls, collection_name: str, doc_id: str) -> None:
        """Delete a document"""
        if collection_name not in cls._data or doc_id not in cls._data[collection_name]:
            return None

        del cls._data[collection_name][doc_id]
        return doc_id

class FirestoreDB:
    """Wrapper for Firestore operations with MockDB implementation"""

    @staticmethod
    def get_server_timestamp():
        """Return a server timestamp"""
        return time.time()

    @staticmethod
    def add_document(collection_name, document_data, doc_id=None):
        """Add a document to a collection, optionally with a specific ID"""
        if doc_id:
            document_data["id"] = doc_id
        return MockDB.create_document(collection_name, document_data)

    @staticmethod
    def get_document(collection_name, doc_id):
        """Get a document by its ID"""
        return MockDB.get_document(collection_name, doc_id)

    @staticmethod
    def get_all_documents(collection_name):
        """Get all documents in a collection"""
        return MockDB.get_all_documents(collection_name)

    @staticmethod
    def update_document(collection_name, doc_id, data):
        """Update a document"""
        return MockDB.update_document(collection_name, doc_id, data)

    @staticmethod
    def delete_document(collection_name, doc_id):
        """Delete a document"""
        return MockDB.delete_document(collection_name, doc_id)

    @staticmethod
    def create_document(collection_name, document_data):
        """Create a new document (legacy method)"""
        # Generate a document ID based on collection type
        if collection_name == "jobs":
            doc_id = document_data.get("job_id", str(uuid.uuid4()))
        elif collection_name == "candidates_data":
            doc_id = str(uuid.uuid4())
        else:
            doc_id = document_data.get("id", str(uuid.uuid4()))

        # Ensure the ID is included in the document data
        doc_data = document_data.copy()
        if "id" not in doc_data:
            doc_data["id"] = doc_id

        # Call the add_document method
        return FirestoreDB.add_document(collection_name, doc_data, doc_id)

# Mock service classes for testing
class JobService:
    @staticmethod
    def get_all_jobs():
        return [{"job_id": "job1", "title": "Software Engineer"}, {"job_id": "job2", "title": "Data Scientist"}]

    @staticmethod
    def get_all_job_postings():
        return [{"job_id": "job1", "title": "Software Engineer"}, {"job_id": "job2", "title": "Data Scientist"}]

    @staticmethod
    def get_job_by_id(job_id):
        jobs = {"job1": {"job_id": "job1", "title": "Software Engineer"}, 
                "job2": {"job_id": "job2", "title": "Data Scientist"}}
        return jobs.get(job_id)

    @staticmethod
    def get_job_posting(job_id):
        jobs = {"job1": {"job_id": "job1", "title": "Software Engineer", "description": "Software engineering position"}, 
                "job2": {"job_id": "job2", "title": "Data Scientist", "description": "Data science position"}}
        return jobs.get(job_id)

    @staticmethod
    def create_job_posting(job_data):
        """Mock method for creating a job posting"""
        job_id = str(uuid.uuid4())
        return {"job_id": job_id, **job_data}

    @staticmethod
    def search_jobs(query):
        return [{"job_id": "job1", "title": "Software Engineer"}, {"job_id": "job2", "title": "Data Scientist"}]

class CandidateService:
    @staticmethod
    def get_all_candidates():
        return [
            {"id": "c1", "name": "John Doe", "job_id": "job1", "status": "scheduled"},
            {"id": "c2", "name": "Jane Smith", "job_id": "job1", "status": "completed"},
            {"id": "c3", "name": "Bob Johnson", "job_id": "job2", "status": "scheduled"},
            {"id": "c4", "name": "Alice Williams", "job_id": "job2", "status": "pending"}
        ]

    @staticmethod
    def get_candidates_by_job_id(job_id):
        candidates = {
            "job1": [
                {"id": "c1", "name": "John Doe", "status": "scheduled", "resume": "experience in Python and JavaScript"},
                {"id": "c2", "name": "Jane Smith", "status": "completed", "resume": "expert in React and Node.js"}
            ],
            "job2": [
                {"id": "c3", "name": "Bob Johnson", "status": "scheduled", "resume": "experience in data science and ML"},
                {"id": "c4", "name": "Alice Williams", "status": "pending", "resume": "background in statistics and Python"}
            ]
        }
        return candidates.get(job_id, [])

    @staticmethod
    def get_candidate(candidate_id):
        candidates = {
            "c1": {"id": "c1", "name": "John Doe", "job_id": "job1", "status": "scheduled", "resume": "experience in Python and JavaScript"},
            "c2": {"id": "c2", "name": "Jane Smith", "job_id": "job1", "status": "completed", "resume": "expert in React and Node.js"},
            "c3": {"id": "c3", "name": "Bob Johnson", "job_id": "job2", "status": "scheduled", "resume": "experience in data science and ML"},
            "c4": {"id": "c4", "name": "Alice Williams", "job_id": "job2", "status": "pending", "resume": "background in statistics and Python"}
        }
        return candidates.get(candidate_id)

    @staticmethod
    def update_candidate_status(candidate_id, status):
        return {
            "id": candidate_id,
            "status": status,
            "updated_at": time.time()
        }

def extract_resume_data(job_id, job_data=None):
    """Process resumes for a job"""
    if job_id == "job1":
        return [
            {"name": "John Doe", "id": "c1", "resume_score": 85, "skills": ["Python", "JavaScript", "React"]},
            {"name": "Jane Smith", "id": "c2", "resume_score": 92, "skills": ["React", "Node.js", "TypeScript"]}
        ]
    elif job_id == "job2":
        return [
            {"name": "Bob Johnson", "id": "c3", "resume_score": 78, "skills": ["Python", "Machine Learning", "Statistics"]},
            {"name": "Alice Williams", "id": "c4", "resume_score": 88, "skills": ["R", "Python", "Data Science"]}
        ]
    else:
        return []

class InterviewService:
    @staticmethod
    def get_all_interviews():
        return [{"id": "i1", "candidate_id": "c1", "job_id": "job1", "date": "2023-06-01"}]

    @staticmethod
    def get_interview_candidates_by_job_id(job_id):
        """Get candidates for a specific job ID"""
        candidates = {
            "job1": [
                {"id": "c1", "name": "John Doe", "status": "scheduled", "feedback": "Good communication skills"},
                {"id": "c2", "name": "Jane Smith", "status": "completed", "feedback": "Strong technical background"}
            ],
            "job2": [
                {"id": "c3", "name": "Bob Johnson", "status": "scheduled", "feedback": None},
                {"id": "c4", "name": "Alice Williams", "status": "pending", "feedback": None}
            ]
        }
        return candidates.get(job_id, [])

    @staticmethod
    def get_interview_candidate(candidate_id):
        """Get a specific interview candidate by ID"""
        candidates = {
            "c1": {"id": "c1", "name": "John Doe", "status": "scheduled", "feedback": "Good communication skills"},
            "c2": {"id": "c2", "name": "Jane Smith", "status": "completed", "feedback": "Strong technical background"},
            "c3": {"id": "c3", "name": "Bob Johnson", "status": "scheduled", "feedback": None},
            "c4": {"id": "c4", "name": "Alice Williams", "status": "pending", "feedback": None}
        }
        return candidates.get(candidate_id)

    @staticmethod
    def submit_feedback(interview_id, feedback, interviewer_id=None):
        """Submit feedback for an interview"""
        return {
            "interview_id": interview_id,
            "feedback": feedback,
            "interviewer_id": interviewer_id or "default_interviewer",
            "timestamp": time.time()
        }

    @staticmethod
    def update_interview_status(interview_id, status):
        """Update the status of an interview"""
        return {
            "interview_id": interview_id,
            "status": status,
            "updated_at": time.time()
        }

    @staticmethod
    def schedule_interview(candidate_id, job_id, date, interviewer_id=None):
        """Schedule a new interview"""
        return {
            "id": str(uuid.uuid4()),
            "candidate_id": candidate_id,
            "job_id": job_id,
            "date": date,
            "interviewer_id": interviewer_id or "default_interviewer",
            "status": "scheduled"        }

    @staticmethod
    def get_candidate_feedback(candidate_id):
        """Get all feedback for a candidate"""
        feedbacks = {
            "c1": [
                {"interview_id": "i1", "feedback": "Good communication skills", "interviewer_id": "interviewer1"},
                {"interview_id": "i2", "feedback": "Strong problem-solving abilities", "interviewer_id": "interviewer2"}
            ],
            "c2": [
                {"interview_id": "i3", "feedback": "Excellent technical knowledge", "interviewer_id": "interviewer1"}
            ]
        }
        return feedbacks.get(candidate_id, [])

    @staticmethod
    def initialize_feedback_array(interview_id, num_rounds=2):
        """Initialize the feedback structure for an interview candidate"""
        feedback_array = []
        for i in range(num_rounds):
            feedback_array.append({
                "round_number": i + 1,
                "feedback": "",
                "rating": 0,
                "interviewer_id": "",
                "date": "",
                "status": "pending"
            })
        return feedback_array

    @staticmethod
    def get_tracking_statistics_by_job(job_id):
        """Get statistics about interview candidates for a job"""
        statistics = {
            "job1": {
                "total_candidates": 10,
                "pending": 3,
                "scheduled": 4,
                "completed": 2,
                "rejected": 1
            },
            "job2": {
                "total_candidates": 5,
                "pending": 1,
                "scheduled": 3,
                "completed": 1,
                "rejected": 0
            }
        }
        return statistics.get(job_id, {
            "total_candidates": 0,
            "pending": 0,
            "scheduled": 0,
            "completed": 0,
            "rejected": 0
        })

class InterviewShortlistService:
    @staticmethod
    def shortlist_candidates(candidates, job_id):
        return [c for c in candidates]

class FinalSelectionService:
    @staticmethod
    def make_final_selection(candidate_id, job_id):
        """Make a final selection for a candidate"""
        return {"status": "selected", "candidate_id": candidate_id, "job_id": job_id}

    @staticmethod
    def get_candidate_selection_status(candidate_id):
        """Get the selection status for a candidate"""
        statuses = {
            "c1": "selected",
            "c2": "rejected",
            "c3": "in_progress",
            "c4": "pending"
        }
        return {"candidate_id": candidate_id, "status": statuses.get(candidate_id, "unknown")}

    @staticmethod
    def finalize_candidate(candidate_id, job_id, status="selected"):
        """Finalize a candidate's selection status"""
        return {"candidate_id": candidate_id, "job_id": job_id, "status": status, "timestamp": time.time()}

    @staticmethod
    def generate_offer_letter(candidate_id, job_id, salary=None, start_date=None):
        """Generate an offer letter for a selected candidate"""
        return {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "offer_letter_id": str(uuid.uuid4()),
            "status": "generated",
            "salary": salary or "120000",
            "start_date": start_date or "2023-07-01",
            "generated_at": time.time()
        }

    @staticmethod
    def update_offer_status(offer_id, status):
        """Update the status of an offer letter"""
        return {
            "offer_id": offer_id,
            "status": status,
            "updated_at": time.time()
        }

    @staticmethod
    def get_selected_candidates_by_job(job_id):
        """Get all selected candidates for a job"""
        selections = {
            "job1": [
                {"candidate_id": "c1", "status": "selected", "offer_status": "accepted"},
                {"candidate_id": "c2", "status": "selected", "offer_status": "pending"}
            ],
            "job2": [
                {"candidate_id": "c3", "status": "selected", "offer_status": "generated"}
            ]
        }
        return selections.get(job_id, [])


class ChatbotService:
    """Service for handling chatbot interactions"""

    # Collection for storing chat histories
    COLLECTION_NAME = "chat_histories"

    @staticmethod
    def _get_api_registry() -> List[Dict[str, Any]]:
        """
        Get a registry of all API endpoints that the chatbot can use

        Returns:
            List of API endpoint definitions
        """
        def safely_serializable(func):
            """Wrapper to make a function safely serializable"""
            return {
                "function": func,
                "_serializable_str": str(func)
            }

        return [
            # Job API endpoints
            {
                "path": "/jobs",
                "method": "GET",
                "description": "Get all job postings",
                "function": JobService.get_all_job_postings,
                "params": {}
            },
            {
                "path": "/jobs/{job_id}",
                "method": "GET",
                "description": "Get a specific job posting by ID",
                "function": JobService.get_job_posting,
                "params": {"job_id": "string"}
            },
            {
                "path": "/jobs",
                "method": "POST",
                "description": "Create a new job posting",
                "function": JobService.create_job_posting,
                "params": {
                    "job_posting": "object"
                }
            },

            # Candidate API endpoints
            {
                "path": "/candidates",
                "method": "GET",
                "description": "Get all candidates",
                "function": CandidateService.get_all_candidates,
                "params": {}
            },
            {
                "path": "/candidates/job/{job_id}",
                "method": "GET",
                "description": "Get candidates for a specific job with job details included",
                "function": lambda job_id: {
                    "job": JobService.get_job_posting(job_id),
                    "candidates": CandidateService.get_candidates_by_job_id(job_id)
                },
                "params": {"job_id": "string"}
            },
            {
                "path": "/candidates/process/{job_id}",
                "method": "POST",
                "description": "Process resumes for a job",
                "function": extract_resume_data,
                "params": {"job_id": "string", "job_data": "dict"}
            },

            # Interview API endpoints
            {
                "path": "/interviews/shortlist",
                "method": "POST",
                "description": "Shortlist candidates for interviews",
                "function": InterviewShortlistService.shortlist_candidates,
                "params": {
                    "job_id": "string", 
                    "number_of_candidates": "integer", 
                    "no_of_interviews": "integer"
                }
            },
            {
                "path": "/interviews/job/{job_id}",
                "method": "GET",
                "description": "Get all interview candidates for a job",
                "function": InterviewService.get_interview_candidates_by_job_id,
                "params": {"job_id": "string"}
            },
            {
                "path": "/interviews/{interview_id}",
                "method": "GET",
                "description": "Get details of a specific interview candidate",
                "function": InterviewService.get_interview_candidate,
                "params": {"interview_id": "string"}
            },
            {
                "path": "/interviews/{interview_id}/feedback",
                "method": "PUT",
                "description": "Update feedback for a specific interview round",
                "function": InterviewService.submit_feedback,
                "params": {
                    "interview_id": "string",
                    "round_index": "integer",
                    "feedback": "string",
                    "rating_out_of_10": "integer",
                    "isSelectedForNextRound": "string"
                }
            },            {
                "path": "/interviews/{interview_id}/initialize-feedback",
                "method": "POST",
                "description": "Initialize the feedback structure for an interview candidate",
                "function": lambda interview_id, num_rounds=2: {
                    "result": InterviewService.initialize_feedback_array(interview_id, num_rounds),
                    "interview": InterviewService.get_interview_candidate(interview_id)
                },
                "params": {"interview_id": "string", "num_rounds": "integer"}
            },
            {
                "path": "/interviews/job/{job_id}/statistics",
                "method": "GET",
                "description": "Get statistics about interview candidates for a job",
                "function": InterviewService.get_tracking_statistics_by_job,
                "params": {"job_id": "string"}
            },
            {
                "path": "/interviews/submit-feedback",
                "method": "POST",
                "description": "Submit feedback for an interview",
                "function": InterviewService.submit_feedback,
                "params": {"interview_id": "string", "feedback": "string", "interviewer_id": "string"}
            },
            {
                "path": "/interviews/{interview_id}/status",
                "method": "PUT",
                "description": "Update status of an interview",
                "function": InterviewService.update_interview_status,
                "params": {"interview_id": "string", "status": "string"}
            },
            {
                "path": "/interviews/schedule",
                "method": "POST",
                "description": "Schedule a new interview",
                "function": InterviewService.schedule_interview,
                "params": {"candidate_id": "string", "job_id": "string", "date": "string", "interviewer_id": "string"}
            },
            {
                "path": "/interviews/candidate/{candidate_id}/feedback",
                "method": "GET",
                "description": "Get all feedback for a candidate",
                "function": InterviewService.get_candidate_feedback,
                "params": {"candidate_id": "string"}
            },
            {
                "path": "/selections/job/{job_id}/candidates",
                "method": "GET",
                "description": "Get selected candidates for a job",
                "function": FinalSelectionService.get_selected_candidates_by_job,
                "params": {"job_id": "string"}
            },
            {
                "path": "/selections/candidate/{candidate_id}/status",
                "method": "GET",
                "description": "Get selection status for a candidate",
                "function": FinalSelectionService.get_candidate_selection_status,
                "params": {"candidate_id": "string"}
            },
            {
                "path": "/selections/finalize",
                "method": "POST",
                "description": "Finalize a candidate's selection",
                "function": FinalSelectionService.finalize_candidate,
                "params": {"candidate_id": "string", "job_id": "string", "status": "string"}
            },
            {
                "path": "/selections/offer-letter",
                "method": "POST",
                "description": "Generate offer letter for a candidate",
                "function": FinalSelectionService.generate_offer_letter,
                "params": {"candidate_id": "string", "job_id": "string", "salary": "string", "start_date": "string"}
            },
            {
                "path": "/selections/offer/{offer_id}/status",
                "method": "PUT",
                "description": "Update status of an offer",
                "function": FinalSelectionService.update_offer_status,
                "params": {"offer_id": "string", "status": "string"}
            }
        ]

    @staticmethod
    def _get_system_prompt() -> str:
        """
        Get the system prompt for the chatbot

        Returns:
            System prompt string
        """
        # Get API registry but create a serializable version of it
        registry = ChatbotService._get_api_registry()

        # Generate detailed documentation for each API
        detailed_docs = []

        for endpoint in registry:
            # Basic endpoint info
            endpoint_doc = f"""
            ## {endpoint['method']} {endpoint['path']}

            **Description:** {endpoint['description']}

            **Parameters:**
            """

            # Add parameter details
            if not endpoint['params']:
                endpoint_doc += "\n- None (No parameters required)"
            else:
                for param_name, param_type in endpoint['params'].items():
                    # Get default value info
                    default_info = ""
                    if param_name == "job_id":
                        default_info = " (Will use first available job if not specified)"
                    elif param_type == "integer":
                        default_info = " (Default: 0)"
                    elif param_type == "string":
                        default_info = f" (Default: 'default_{param_name}')"

                    endpoint_doc += f"\n- `{param_name}`: {param_type}{default_info}"

            # Add example usage
            endpoint_doc += "\n\n**Example Usage:**\n"

            if endpoint['method'] == "GET" and not endpoint['params']:
                # Simple GET with no params
                endpoint_doc += f"""
                "List all {endpoint['path'].strip('/')}"
                "Get {endpoint['path'].strip('/')}"
                "Show me {endpoint['path'].strip('/')}"
                """
            elif endpoint['method'] == "GET" and "job_id" in endpoint['params']:
                # GET with job_id param
                # Create a plain string for the path replacement to avoid f-string nesting issues
                path_with_id = endpoint['path'].replace("{job_id}", "SOFTWARE_ENGINEER_123")
                endpoint_doc += f"""
                "Get {path_with_id}"
                "Show me {endpoint['description'].lower()} for job SOFTWARE_ENGINEER_123"
                """
            elif endpoint['method'] == "POST" and "job_id" in endpoint['params']:
                # POST with job_id param - avoid f-string issues by using plain text description
                description = endpoint['description']
                endpoint_doc += f"""
                "{description} for job SOFTWARE_ENGINEER_123"
                """
            elif endpoint['method'] == "POST" and endpoint['path'] == "/jobs":
                # Job creation - use plain string to avoid f-string issues
                endpoint_doc += """
                "Create a new job posting for Software Engineer with 3-5 years experience"
                "Add a job for Frontend Developer with job description: 'Experienced frontend developer needed'"
                "Add a new job in New York for Senior Python Developer requiring 3-5 years experience"
                "Post a Remote job for UI/UX Designer with 2 years experience needed, status: open"
                """
            elif endpoint['method'] == "PUT" and "feedback" in endpoint['params']:
                # Feedback submission - use plain string to avoid f-string issues
                endpoint_doc += """
                "Submit feedback for interview ABC123, round 1 with rating 8: 'Candidate showed excellent problem solving skills'"
                """
            else:
                # Generic example - store path and description variables for use in f-string
                path = endpoint['path']
                description = endpoint['description']
                endpoint_doc += f"""
                "Use the {path} endpoint"
                "{description}"
                """

            detailed_docs.append(endpoint_doc)        
        combined_docs = "\n\n".join(detailed_docs)

        system_prompt = f"""You are an AI assistant that helps users interact with an Interview Scheduler API.
Your job is to understand what the user is trying to do, and then execute the appropriate API call based on their role permissions.

# DETAILED API DOCUMENTATION

{combined_docs}

# ROLE-BASED PERMISSIONS

Our system has the following roles with different permissions:

1. HR Role:
   - Can view feedback from all interviewers
   - Can add feedback for any candidate
   - Can decide if a candidate proceeds to the next round
   - Can schedule interviews

2. Recruiter Role:
   - Can view feedback from all interviewers
   - Can add feedback for any candidate
   - Cannot decide if a candidate proceeds to the next round
   - Can schedule interviews

3. Interviewer Role:
   - Can only view their own feedback (not others')
   - Can only add feedback for candidates they are interviewing
   - Cannot decide if a candidate proceeds to the next round
   - Cannot schedule interviews

# REQUEST HANDLING INSTRUCTIONS

For each user message:
1. Check the user's role and permissions
2. Analyze what the user wants to do
3. Determine if the user has permission to perform the requested action
4. If permitted, determine which API endpoint from the documentation above would fulfill this request
5. Extract all required parameters from the user's message
6. Execute the API call with the extracted parameters
7. Return the results in a friendly, helpful way, keeping role-based restrictions in mind
8. Suggest next steps the user might want to take based on their role

# IMPORTANT RULES

- Only use the API endpoints listed in the documentation above. Don't make up new endpoints.
- Check permissions before processing requests - inform users if they lack permissions.
- If you don't have enough information, ask the user for clarification.
- If the request is outside the scope of managing interviews, job postings, and candidates, politely inform the user.
- If an API call fails, explain the error and suggest how to fix it.
- Always return the executed API call and its results for transparency.
- ONLY discuss and retrieve information relevant to this Interview Scheduling system.
- When a user doesn't have permission for an action, politely explain why and suggest alternatives.

# PARAMETER HANDLING GUIDELINES

- When a parameter is not explicitly provided by the user:
  * For job_id: Use the first available job if possible
  * For integer values: Use 0 as default
  * For string values: Use a placeholder with format default_param_name
  * For object/dict values: Use an empty object

# JOB POSTING GUIDELINES

When creating a job posting, extract the following fields:
- job_role_name (required): Title of the job position
- job_description (required): Description of the job responsibilities
- years_of_experience_needed (required): Experience requirement for the position
- status (optional): Status of the job posting (open/closed), defaults to "open"
- location (optional): Where the job is located (remote or city name), defaults to "remote"
"""

        system_prompt += """
- Ensure all required parameters are included in your API call, even if you need to use defaults
- When using API endpoints with path parameters (e.g. "/jobs/{job_id}"), replace the parameter with the actual value

You are now ready to help users interact with the Interview Scheduler API using natural language!
"""
        return system_prompt

    @staticmethod
    def create_llm_chain(temperature: float = 0.2):
        """
        Create a LangChain chain for processing chat messages using updated LangChain patterns

        Args:
            temperature: Temperature parameter for the OpenAI model

        Returns:
            Runnable chain object
        """
        # Create prompt template
        system_prompt = ChatbotService._get_system_prompt()
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            HumanMessage(content="{input}")
        ])

        # Create LLM with updated import
        llm = ChatOpenAI(
            model_name="gpt-4o", 
            temperature=temperature,
            api_key=api_key
        )

        # Create memory with updated import
        memory = ConversationBufferMemory(return_messages=True, input_key="input", memory_key="chat_history")

        # Create a parser
        parser = StrOutputParser()

        # Create chain using the updated pattern
        chain = prompt | llm | parser

        # Add memory to the chain
        memory_dict = {"chat_history": memory.load_memory_variables({})["chat_history"]}

        # Create a class to hold the chain and memory for use
    class ChainWithMemory:
        def __init__(self, chain, memory):
            self.chain = chain
            self.memory = memory

        def run(self, input_text):
            # Get chat history
            chat_history = self.memory.load_memory_variables({}).get("chat_history", [])

            # Debug log the input
            logging.debug(f"ChainWithMemory input: {input_text}")
            logging.debug(f"ChainWithMemory chat history: {chat_history}")

            # Run the chain with correct input format
            result = self.chain.invoke({"input": input_text, "chat_history": chat_history})

            # Update memory
            self.memory.save_context({"input": input_text}, {"output": result})

            # Debug log the result
            logging.debug(f"ChainWithMemory result: {result}")

            return result

    @staticmethod
    def _get_database_schema() -> str:
        """
        Get a description of the database schema (collections and their structure)

        Returns:
            String describing the database schema
        """
        return """
# DATABASE COLLECTIONS OVERVIEW

1. jobs
   - job_id: Unique identifier for the job
   - job_role_name: Name of the job role
   - job_description: Description of the job
   - years_of_experience_needed: Years of experience required
   - status: Status of the job (open/closed)
   - location: Location of the job (remote/city name)

2. candidates_data
   - id: Unique identifier for the candidate
   - name: Candidate's name
   - email: Candidate's email
   - phone: Candidate's phone number
   - job_id: ID of the job they applied for
   - resume_url: URL to their resume
   - ai_fit_score: AI-generated score showing how well they fit the job

3. interview_candidates
   - id: Unique identifier for the interview process
   - candidate_id: ID of the candidate
   - job_id: ID of the job
   - rounds: Array of interview rounds with feedback
   - status: Current status of the candidate in the interview process
   - is_selected: Whether the candidate is selected for the next round
   - final_selection: Whether the candidate received a final offer

4. final_candidates
   - id: Unique identifier for the final selection
   - interview_id: ID of the interview process
   - candidate_id: ID of the candidate
   - job_id: ID of the job
   - offer_letter_sent: Whether the offer letter was sent
   - offer_accepted: Whether the candidate accepted the offer
   - joining_date: When the candidate is scheduled to join
   - status: Current status of the final offer process

These collections are related: jobs → candidates_data → interview_candidates → final_candidates
"""

    @staticmethod
    def _fetch_relevant_data(message: str) -> Dict[str, Any]:
        """
        Fetch relevant data based on the user's message using service methods

        Args:
            message: The user's message

        Returns:
            Dictionary with relevant data
        """
        data = {}

        try:
            # Extract job_id from the message if present
            job_id_match = re.search(r'job id[:\s-]*([a-zA-Z0-9-]+)', message, re.IGNORECASE)
            job_id = job_id_match.group(1) if job_id_match else None

            # Extract candidate_id from the message if present
            candidate_id_match = re.search(r'candidate id[:\s-]*([a-zA-Z0-9-]+)', message, re.IGNORECASE)
            candidate_id = candidate_id_match.group(1) if candidate_id_match else None

            # Extract interview_id from the message if present
            interview_id_match = re.search(r'interview id[:\s-]*([a-zA-Z0-9-]+)', message, re.IGNORECASE)
            interview_id = interview_id_match.group(1) if interview_id_match else None

            # If a specific job ID is mentioned, get job details
            if job_id and "job" not in data:
                job = JobService.get_job_posting(job_id)
                if job:
                    data["job"] = ChatbotService._make_serializable(job)

            # If the message mentions "final offer" or related terms, fetch final candidates data
            if any(term in message.lower() for term in ["final offer", "offer letter", "selected", "hiring"]) and job_id:
                try:
                    # Get final candidates for the job using service
                    final_candidates = FinalSelectionService.get_selected_candidates_by_job(job_id)
                    if final_candidates:
                        data["final_candidates"] = ChatbotService._make_serializable(final_candidates)

                    # Get interview candidates for the job
                    interview_candidates = InterviewService.get_interview_candidates_by_job_id(job_id)
                    if interview_candidates:
                        data["interview_candidates"] = ChatbotService._make_serializable(interview_candidates)

                        # Get candidate details from interview candidates
                        for interview in interview_candidates:
                            candidate_id = getattr(interview, "candidate_id", None)
                            if candidate_id and "candidates" not in data:
                                data["candidates"] = []

                            if candidate_id:
                                candidate = CandidateService.get_candidate(candidate_id)
                                if candidate:
                                    if "candidates" not in data:
                                        data["candidates"] = []
                                    data["candidates"].append(ChatbotService._make_serializable(candidate))
                except Exception as service_error:
                    logging.error(f"Error fetching final candidates data: {service_error}")

            # If the message is about statistics or performance
            if any(term in message.lower() for term in ["statistics", "performance", "metrics", "tracking"]) and job_id:
                try:
                    # Get interview statistics using service
                    statistics = InterviewService.get_tracking_statistics_by_job(job_id)
                    if statistics:
                        data["interview_statistics"] = ChatbotService._make_serializable(statistics)
                except Exception as stats_error:
                    logging.error(f"Error fetching interview statistics: {stats_error}")

            # If a specific candidate ID is mentioned
            if candidate_id:
                try:
                    candidate = CandidateService.get_candidate(candidate_id)
                    if candidate:
                        data["candidate"] = ChatbotService._make_serializable(candidate)
                except Exception as candidate_error:
                    logging.error(f"Error fetching candidate: {candidate_error}")

            # If a specific interview ID is mentioned
            if interview_id:
                try:
                    interview = InterviewService.get_interview_candidate(interview_id)
                    if interview:
                        data["interview"] = ChatbotService._make_serializable(interview)
                          # Get candidate for this interview
                        candidate_id = getattr(interview, "candidate_id", None)
                        if candidate_id:
                            candidate = CandidateService.get_candidate(candidate_id)
                            if candidate:
                                data["candidate"] = ChatbotService._make_serializable(candidate)
                except Exception as interview_error:
                    logging.error(f"Error fetching interview: {interview_error}")

        except Exception as e:
            logging.error(f"Error fetching relevant data: {str(e)}")

        return data

    @staticmethod
    def generate_response(
        message: str, 
        conversation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        user_role: Optional[str] = "HR"  # Default role is HR
    ) -> Dict[str, Any]:
        """
        Generate a response using the chatbot
        """
        logger.info(f"[CHATBOT] Generating response for user role: {user_role}")
        logger.info(f"[CHATBOT] Message: {message}")
        logger.info(f"[CHATBOT] Conversation ID: {conversation_id}")

        try:
            # Initialize conversation ID if not provided
            if not conversation_id:
                conversation_id = str(uuid.uuid4())

            # Fetch relevant data
            db_context = ChatbotService._fetch_relevant_data(message)

            # Prepare the system prompt
            system_prompt = ChatbotService._get_system_prompt()

            # Include all context
            input_text = message
            context_parts = []

            # Add role information and permissions
            role_info = {
                "current_role": user_role,
                "permissions": ROLES.get(user_role, {}),
                "can_view_all_feedback": ChatbotService.check_permission(user_role, "view_all_feedback"),
                "can_add_feedback_all": ChatbotService.check_permission(user_role, "add_feedback_all"),
                "can_decide_next_round": ChatbotService.check_permission(user_role, "decide_next_round"),
                "can_schedule_interview": ChatbotService.check_permission(user_role, "schedule_interview")
            }

            context_parts.append("USER ROLE AND PERMISSIONS:\n" + json.dumps(role_info, indent=2))
            context_parts.append("DATABASE SCHEMA:\n" + ChatbotService._get_database_schema())

            if db_context:
                context_parts.append("RELEVANT DATA FROM DATABASE:\n" + json.dumps(db_context, indent=2))

            if context:
                context_parts.append("ADDITIONAL CONTEXT:\n" + json.dumps(context, indent=2))

            # Add combined context if any context parts exist
            if context_parts:
                context_text = "\n\n".join(context_parts)
            else:
                context_text = ""

            # Create messages for OpenAI API
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{input_text}\n\n{context_text}"}
            ]

            # Call OpenAI API directly
            logger.info("Calling OpenAI API for response")
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.2
            )

            # Extract the response text
            full_response_text = response.choices[0].message.content

            # Trim content if needed
            response_text = full_response_text

            # Parse the response to extract any API calls
            api_call_info = ChatbotService._extract_api_call_info(response_text)
            executed_action = None

            # Execute the API call if identified
            if api_call_info:
                executed_action = ChatbotService._execute_api_call(api_call_info, message, user_role)

            return {
                "response": response_text,
                "conversation_id": conversation_id,
                "executed_action": executed_action,
                "action_result": executed_action.get("result") if executed_action else None
            }

        except Exception as e:
            logging.error(f"Error generating chatbot response: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error generating response: {str(e)}")

    @staticmethod
    def _extract_api_call_info(response_text: str) -> Optional[Dict[str, Any]]:
        """
        Extract API call information from the response text

        Args:
            response_text: Response text from the LLM

        Returns:
            Dictionary with API call information or None if no API call was made
        """
        # This is a simple implementation that can be improved
        api_calls = []
        registry = ChatbotService._get_api_registry()

        for endpoint in registry:
            path = endpoint['path']
            method = endpoint['method']

            # Check if the API path is mentioned in the response
            if path in response_text and method in response_text:
                api_calls.append({
                    "path": path,
                    "method": method,
                    "endpoint": endpoint,
                    "position": response_text.find(path)  # To determine which API call was mentioned first
                })

        if not api_calls:
            return None

        # Choose the API call that was mentioned first
        api_calls.sort(key=lambda x: x['position'])
        return api_calls[0]    

    @staticmethod
    def _execute_api_call(api_call_info: Dict[str, Any], user_message: str, user_role: str = "HR") -> Dict[str, Any]:
        """
        Execute an API call based on extracted information

        Args:
            api_call_info: Dictionary with API call information
            user_message: The user's message to extract parameters from
            user_role: The role of the user (HR, Recruiter, Interviewer)

        Returns:
            Dictionary with API call results
        """
        try:
            endpoint = api_call_info['endpoint']
            function = endpoint['function']
            params = endpoint['params']

            # Check permissions based on the endpoint
            endpoint_path = endpoint['path']
            endpoint_method = endpoint['method']
              # Define permissions required for each endpoint
            permission_required = None

            # Interview feedback endpoints
            if "/interviews" in endpoint_path and "feedback" in endpoint_path:
                if endpoint_method == "GET":
                    permission_required = "view_all_feedback"
                elif endpoint_method == "PUT" or endpoint_method == "POST":
                    permission_required = "add_feedback_all"

            # Interview scheduling endpoints
            elif "/interviews" in endpoint_path and any(kw in endpoint_path for kw in ["schedule", "shortlist"]):
                permission_required = "schedule_interview"

            # Next round decision endpoints
            elif "/interviews" in endpoint_path and "round" in endpoint_path:
                permission_required = "decide_next_round"

            # Interview status update
            elif "/interviews" in endpoint_path and "status" in endpoint_path:
                permission_required = "decide_next_round"

            # Submit feedback 
            elif "/interviews/submit-feedback" in endpoint_path:
                permission_required = "add_feedback_all"

            # Final selection endpoints
            elif "/selections/finalize" in endpoint_path or "/selections/offer" in endpoint_path:
                permission_required = "decide_next_round"            # Check permission if required
            if permission_required:
                logger.info(f"[API] Checking permission for endpoint {endpoint_path} ({endpoint_method}), role: {user_role}, permission required: {permission_required}")

                if not ChatbotService.check_permission(user_role, permission_required):
                    logger.warning(f"[API] PERMISSION DENIED: {user_role} attempting to access {endpoint_path} ({endpoint_method})")
                    # This will be checked in chatbot_routes.py to return a 403 status
                    return {
                        "path": endpoint_path,
                        "method": endpoint_method,
                        "error": f"Permission denied: Your role '{user_role}' does not have permission to {permission_required.replace('_', ' ')}",
                        "status": "permission_denied"
                    }
                else:
                    logger.info(f"[API] Permission GRANTED: {user_role} accessing {endpoint_path} ({endpoint_method})")

            # Extract parameter values from the user's message
            param_values = {}

            # Check if the message mentions job_role_name instead of job_id
            job_role_mentioned = False
            job_role_name = None

            # Keywords that might indicate job role names in the message
            job_role_keywords = [
                "developer", "engineer", "manager", "designer", "analyst", 
                "scientist", "specialist", "coordinator", "associate", "lead"
            ]

            # Check for job role patterns
            if "job" in user_message.lower():
                for keyword in job_role_keywords:
                    pattern = rf'(?:job|position|role)\s+(?:for|as)\s+(?:a|an)?\s*([A-Za-z\s]*{keyword}[A-Za-z\s]*)'
                    match = re.search(pattern, user_message, re.IGNORECASE)
                    if match:
                        job_role_name = match.group(1).strip()
                        job_role_mentioned = True
                        break

                # If no match with the keywords, try more generic pattern
                if not job_role_mentioned:
                    generic_pattern = r'(?:job|position|role)\s+(?:for|as)\s+(?:a|an)?\s*([A-Za-z\s]+)'
                    match = re.search(generic_pattern, user_message, re.IGNORECASE)
                    if match:
                        potential_role = match.group(1).strip()
                        # Exclude common non-role text following "job for"
                        if len(potential_role) > 3 and potential_role.lower() not in ["the", "this", "that"]:
                            job_role_name = potential_role
                            job_role_mentioned = True

            # Use OpenAI to extract parameters from the user message
            prompt = f"""
            Extract parameters from the user message for the API call:

            API: {api_call_info['path']} ({api_call_info['method']})
            Required parameters: {json.dumps(params)}
            User message: "{user_message}"

            Return ONLY a JSON object with parameter names as keys and extracted values.
            """
              # Get parameter extraction from OpenAI using the new API format (>=1.0.0)
            client = openai.OpenAI(api_key=api_key)  # Create a client instance with API key
            extraction_response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )

            # Parse the extraction result - updated for new OpenAI API response format
            try:
                extraction_text = extraction_response.choices[0].message.content
                # Extract JSON content from the response
                json_match = re.search(r'```json\s*([\s\S]*?)\s*```|({[\s\S]*?})', extraction_text)
                if json_match:
                    json_content = json_match.group(1) or json_match.group(2)
                    param_values = json.loads(json_content)
                else:
                    param_values = json.loads(extraction_text)

                # Verify all required parameters are present
                for param_name, param_type in params.items():
                    if param_name not in param_values:
                        # Parameter wasn't extracted - provide a default value based on type
                        if param_name == "job_id":
                            # If job_role_name was found, try to get job_id from it
                            if job_role_mentioned and job_role_name:
                                try:
                                    print(f"Looking for job with role name: '{job_role_name}'")
                                    # Get all jobs and find matching role
                                    all_jobs = JobService.get_all_job_postings()

                                    # Find job with matching role name
                                    for job in all_jobs:
                                        job_role = None
                                        if hasattr(job, "job_role_name"):
                                            job_role = job.job_role_name
                                        elif isinstance(job, dict) and "job_role_name" in job:
                                            job_role = job["job_role_name"]

                                        # Check if this job's role name contains our search term
                                        if job_role and job_role_name.lower() in job_role.lower():
                                            # Found a matching job
                                            if hasattr(job, "job_id"):
                                                param_values["job_id"] = job.job_id
                                                print(f"Found job with ID {job.job_id} matching '{job_role_name}'")
                                                break
                                            elif hasattr(job, "id"):
                                                param_values["job_id"] = job.id
                                                print(f"Found job with ID {job.id} matching '{job_role_name}'")
                                                break
                                            elif isinstance(job, dict) and "job_id" in job:
                                                param_values["job_id"] = job["job_id"]
                                                print(f"Found job with ID {job['job_id']} matching '{job_role_name}'")
                                                break
                                            elif isinstance(job, dict) and "id" in job:
                                                param_values["job_id"] = job["id"]
                                                print(f"Found job with ID {job['id']} matching '{job_role_name}'")
                                                break

                                    # If no matching job found, fall back to first job
                                    if "job_id" not in param_values and all_jobs and len(all_jobs) > 0:
                                        first_job = all_jobs[0]
                                        print("No exact match found, using first available job")
                                        if hasattr(first_job, "job_id"):
                                            param_values["job_id"] = first_job.job_id
                                        elif hasattr(first_job, "id"):
                                            param_values["job_id"] = first_job.id
                                        elif isinstance(first_job, dict) and "job_id" in first_job:
                                            param_values["job_id"] = first_job["job_id"]
                                        elif isinstance(first_job, dict) and "id" in first_job:
                                            param_values["job_id"] = first_job["id"]
                                        else:
                                            param_values["job_id"] = "default_job_id"
                                except Exception as e:
                                    print(f"Error finding job by role name: {e}")
                                    param_values["job_id"] = "default_job_id"
                            else:
                                # Fall back to default behavior if no job role mentioned
                                try:
                                    all_jobs = JobService.get_all_job_postings()
                                    if all_jobs and len(all_jobs) > 0:
                                        first_job = all_jobs[0]
                                        if hasattr(first_job, "job_id"):
                                            param_values["job_id"] = first_job.job_id
                                        elif hasattr(first_job, "id"):
                                            param_values["job_id"] = first_job.id
                                        elif isinstance(first_job, dict) and "job_id" in first_job:
                                            param_values["job_id"] = first_job["job_id"]
                                        elif isinstance(first_job, dict) and "id" in first_job:
                                            param_values["job_id"] = first_job["id"]
                                        else:
                                            param_values["job_id"] = "default_job_id"
                                    else:
                                        param_values["job_id"] = "default_job_id"
                                except Exception as e:
                                    param_values["job_id"] = "default_job_id"
                                    print(f"Error getting default job_id: {e}")
                        else:
                            # Generic handling for other parameters
                            if param_type == "string":
                                param_values[param_name] = f"default_{param_name}"
                            elif param_type == "integer":
                                param_values[param_name] = 0
                            elif param_type == "dict":
                                param_values[param_name] = {}
                            else:
                                param_values[param_name] = None
            except Exception as parse_error:
                # Fallback to using placeholders if parsing fails
                logging.error(f"Parameter extraction failed: {parse_error}")
                for param_name, param_type in params.items():
                    # Provide type-appropriate default values
                    if param_type == "string":
                        param_values[param_name] = f"default_{param_name}"
                    elif param_type == "integer":
                        param_values[param_name] = 0
                    elif param_type == "dict":
                        param_values[param_name] = {}
                    else:
                        param_values[param_name] = None

            # Special handling for specific endpoints
            if api_call_info['path'] == "/candidates/process/{job_id}" and "job_id" in param_values:
                # For process_resume, get the job data from the job ID
                job_id = param_values.get("job_id")
                job_data = JobService.get_job_posting(job_id)
                if job_data:
                    # Convert to dict if needed
                    job_dict = job_data
                    if hasattr(job_data, "dict"):
                        job_dict = job_data.dict()
                    param_values["job_data"] = job_dict

            # Special handling for job creation
            if api_call_info['path'] == "/jobs" and api_call_info['method'] == "POST":
                # For testing purposes, create a simple dict instead of importing the schema
                # In a real implementation, you would import the proper schema

                # Extract job posting details from the message
                job_role_name = None
                job_description = None
                years_of_experience = None
                status = "open"  # default
                location = "remote"  # default

                # Extract job details from the parameters or the message
                if "job_role_name" in param_values:
                    job_role_name = param_values["job_role_name"]
                if "job_description" in param_values:
                    job_description = param_values["job_description"]
                if "years_of_experience_needed" in param_values:
                    years_of_experience = param_values["years_of_experience_needed"]
                if "status" in param_values:
                    status = param_values["status"]
                if "location" in param_values:
                    location = param_values["location"]

                # Get additional details from OpenAI if needed
                if not job_role_name or not job_description or not years_of_experience:
                    job_prompt = f"""
                    Extract the following job details from this message: "{user_message}"

                    Return ONLY a JSON object with these fields:
                    - job_role_name: The name/title of the job position
                    - job_description: A brief description of the job
                    - years_of_experience_needed: Required years of experience
                    - status: Job status (open/closed), default to "open" if not specified
                    - location: Job location (remote or city name), default to "remote" if not specified
                    """

                    try:
                        job_extraction = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[{"role": "user", "content": job_prompt}],
                            temperature=0.1
                        )

                        job_extraction_text = job_extraction.choices[0].message.content
                        json_match = re.search(r'```json\s*([\s\S]*?)\s*```|({[\s\S]*?})', job_extraction_text)
                        if json_match:
                            json_content = json_match.group(1) or json_match.group(2)
                            job_data = json.loads(json_content)
                        else:
                            job_data = json.loads(job_extraction_text)

                        job_role_name = job_data.get("job_role_name") or job_role_name or "Default Job Title"
                        job_description = job_data.get("job_description") or job_description or "Default job description"
                        years_of_experience = job_data.get("years_of_experience_needed") or years_of_experience or "0-1 years"
                        status = job_data.get("status") or status
                        location = job_data.get("location") or location
                    except Exception as e:
                        logging.error(f"Error extracting job details: {str(e)}")

                # Ensure years_of_experience is a string
                if isinstance(years_of_experience, int):
                    years_of_experience = f"{years_of_experience}+ years"

                # Create job posting dict
                job_posting = {
                    "job_role_name": job_role_name or "Default Job Title",
                    "job_description": job_description or "Default job description",
                    "years_of_experience_needed": str(years_of_experience),
                    "status": status,
                    "location": location
                }

                # Replace parameters
                param_values = {"job_posting": job_posting}

            # Execute the function with the extracted parameters
            result = function(**param_values)

            # Make the result JSON serializable
            json_serializable_result = ChatbotService._make_serializable(result)

            return {
                "path": api_call_info['path'],
                "method": api_call_info['method'],
                "params": param_values,
                "result": json_serializable_result
            }

        except Exception as e:
            logging.error(f"Error executing API call: {str(e)}")
            return {
                "path": api_call_info['path'],
                "method": api_call_info['method'],
                "error": str(e)
            }

    @staticmethod
    def _make_serializable(obj):
        """
        Make an object JSON serializable

        Args:
            obj: Any Python object

        Returns:
            JSON serializable version of the object
        """
        if hasattr(obj, "dict") and callable(obj.dict):
            # Convert Pydantic models to dict
            return obj.dict()
        elif hasattr(obj, "model_dump") and callable(obj.model_dump):
            # For newer Pydantic v2 models
            return obj.model_dump()
        elif hasattr(obj, "__dict__") and not callable(obj):
            # For custom classes
            return {k: ChatbotService._make_serializable(v) for k, v in obj.__dict__.items() 
                   if not k.startswith('_') and not callable(v)}
        elif isinstance(obj, dict):
            # Process each item in dictionaries
            return {k: ChatbotService._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            # Process each item in lists
            return [ChatbotService._make_serializable(i) for i in obj]
        elif isinstance(obj, (str, int, float, bool, type(None))):
            # Basic types are already serializable
            return obj
        elif callable(obj):
            # Handle functions and other callables
            return f"<Function: {obj.__name__ if hasattr(obj, '__name__') else 'anonymous'}>"
        else:
            # For other types, convert to string
            try:
                return str(obj)
            except Exception as e:
                return f"<Object of type {type(obj).__name__} (not serializable): {str(e)}>"

    @staticmethod
    def _suggest_next_steps(response_text: str) -> List[str]:
        """
        Extract suggested next steps from the response text

        Args:
            response_text: Response text from the LLM

        Returns:
            List of suggested next steps
        """
        # This is a simplified implementation
        suggestions = []

        # Look for phrases like "You can now..." or "Next, you might want to..."
        indicators = [
            "you can now", "next", "you might want to", 
            "you could", "try", "consider", "suggested next"
        ]

        lines = response_text.split("\n")
        for line in lines:
            line = line.strip().lower()
            if any(indicator in line for indicator in indicators) and len(line) > 10:
                suggestions.append(line)

        # If no suggestions found, provide generic ones
        if not suggestions:
            suggestions = [
                "Ask about job postings",
                "Check candidate status",
                "Schedule interviews",
                "Get interview statistics"
            ]

        return suggestions[:3]  # Limit to 3 suggestions    

    @staticmethod
    def check_permission(role: str, permission: str) -> bool:
        """
        Check if a role has a specific permission

        Args:
            role: User role (HR, Recruiter, Interviewer)
            permission: Permission to check

        Returns:
            True if the role has the permission, False otherwise
        """
        if role not in ROLES:
            logger.warning(f"[RBAC] Unknown role requested: {role}")
            return False

        has_permission = ROLES[role].get(permission, False)
        logger.info(f"[RBAC] Permission check: role={role}, permission={permission}, result={'GRANTED' if has_permission else 'DENIED'}")
        return has_permission

    @staticmethod
    def validate_role_permission(role: str, permission: str) -> None:
        """
        Validate that a role has the required permission

        Args:
            role: User role (HR, Recruiter, Interviewer)
            permission: Required permission

        Raises:
            RolePermissionError: If the role doesn't have the permission
        """
        if not ChatbotService.check_permission(role, permission):
            raise RolePermissionError(role, permission)