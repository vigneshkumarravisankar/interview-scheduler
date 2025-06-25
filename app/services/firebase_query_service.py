"""
Service for handling natural language queries to Firebase
Handles all database operations through natural language
"""
import json
import uuid
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

import openai
from fastapi import HTTPException

from app.database.chroma_db import FirestoreDB, ChromaVectorDB, db
from app.services.job_service import JobService
from app.services.candidate_service import CandidateService
from app.services.interview_service import InterviewService
from app.services.final_selection_service import FinalSelectionService


class FirebaseQueryService:
    """Service for handling natural language queries to Firebase"""

    # Collection for storing chat histories
    CHAT_HISTORY_COLLECTION = "firebase_nl_query_history"

    @staticmethod
    def _get_system_prompt() -> str:
        """
        Get the system prompt for the Firebase query LLM
        
        Returns:
            System prompt string
        """
        return """You are an AI assistant specialized in translating natural language queries into Firebase database operations and providing informative responses about interview processes.

# DATABASE SCHEMA

## Collections

1. jobs
   - id: Unique identifier for the job
   - job_id: Duplicate identifier (sometimes used instead of id)
   - job_role_name: Name of the job role (e.g., "Software Engineer")
   - job_description: Detailed description of the job
   - years_of_experience_needed: Experience required in years
   - status: Status of the job posting (e.g., "open", "closed")
   - location: Location of the job (e.g., "remote", "New York")

2. candidates_data
   - id: Unique identifier for the candidate
   - name: Candidate's name
   - email: Candidate's email address
   - phone_no: Candidate's phone number
   - job_id: ID of the job they applied for
   - job_role_name: Name of the job role they applied for
   - ai_fit_score: AI-generated score showing how well they fit the job
   - technical_skills: Skills the candidate possesses
   - total_experience_in_years: Candidate's total experience in years
   - previous_companies: Array of previous employment information
   - resume_url: URL to their resume
   - created_at: Timestamp when record was created
   - updated_at: Timestamp when record was last updated

3. interview_candidates
   - id: Unique identifier for the interview process
   - candidate_id: ID of the candidate
   - candidate_name: Name of the candidate
   - candidate_email: Email of the candidate
   - job_id: ID of the job
   - job_role: Name of the job role
   - no_of_interviews: Number of planned interview rounds
   - feedback: Array of feedback from each interview round
     - interviewer_name: Name of the interviewer
     - interviewer_email: Email of the interviewer
     - round_number: Interview round number
     - round_type: Type of interview (e.g., "Technical", "HR", "Manager")
     - feedback: Detailed feedback from the interviewer
     - isSelectedForNextRound: Whether candidate was selected for next round
     - rating_out_of_10: Numerical rating given by interviewer
     - meet_link: Link to video meeting
   - completedRounds: Number of completed interview rounds
   - nextRoundIndex: Index of the next round to be conducted
   - status: Current status of the candidate in the process (e.g., "shortlisted", "scheduled", "rejected")
   - current_round_scheduled: Whether the next round is scheduled
   - created_at: Timestamp when record was created
   - last_updated: Timestamp when record was last updated

4. final_candidates
   - id: Unique identifier for the final selection
   - candidate_id: ID of the selected candidate
   - candidate_name: Name of the selected candidate
   - email: Email of the selected candidate
   - job_id: ID of the job they were selected for
   - job_role: Name of the job role they were selected for
   - compensation_offered: Salary/compensation package offered
   - hr_name: Name of the HR representative handling the offer
   - hr_email: Email of the HR representative
   - status: Status of the offer process (e.g., "offer_created", "offered", "accepted", "rejected")

# PROCESS FLOW

The interview process follows this sequence:
1. Jobs are created in the 'jobs' collection
2. Resumes are processed for a particular job, creating entries in 'candidates_data'
3. Top candidates are shortlisted and scheduled for interviews, creating entries in 'interview_candidates'
4. Interview feedback is recorded in the 'feedback' array for each candidate
5. Candidates with positive feedback (isSelectedForNextRound = 'yes' and high rating_out_of_10) move to the next round
6. After all rounds are complete, top candidates are moved to 'final_candidates' with offers

# YOUR CAPABILITIES

You can:
1. QUERY data from any collection based on natural language requests
2. UPDATE documents with new information
3. ANALYZE and summarize information across collections
4. EXPLAIN the interview process status for candidates or jobs

# RESPONSE FORMAT

Always respond with:
1. A brief explanation of what you understood from the query
2. The Firebase operation you executed (show actual collection and field names)
3. The results or confirmation of the operation
4. Any relevant insights or next steps

For complex data, organize your response into clear sections with headings.
"""

    @staticmethod
    def _generate_openai_response(messages: List[Dict[str, str]]) -> str:
        """
        Generate a response using OpenAI's API
        
        Args:
            messages: List of message dictionaries with role and content
            
        Returns:
            Response text from OpenAI
        """
        try:
            # Create a client instance
            client = openai.OpenAI()
            
            # Make the API call
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.2
            )
            
            # Return the response text
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"Error generating OpenAI response: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error with OpenAI: {str(e)}")
    
    @staticmethod
    def _execute_query(collection_name: str, field_path: str, operator: str, value: Any) -> List[Dict[str, Any]]:
        """
        Execute a simple query on a collection
        
        Args:
            collection_name: Name of the collection to query
            field_path: Field path to query on
            operator: Operator for the query ('==', '!=', '>', '<', '>=', '<=', 'array_contains', 'in')
            value: Value to compare against
            
        Returns:
            List of documents matching the query
        """
        return FirestoreDB.execute_query(collection_name, field_path, operator, value)
    
    @staticmethod
    def _execute_complex_query(collection_name: str, conditions: List[Tuple[str, str, Any]], 
                              order_by: Optional[List[Tuple[str, str]]] = None) -> List[Dict[str, Any]]:
        """
        Execute a complex query with multiple conditions
        
        Args:
            collection_name: Name of the collection to query
            conditions: List of tuples with (field_path, operator, value)
            order_by: Optional list of tuples with (field_path, direction)
            
        Returns:
            List of documents matching the query
        """
        return FirestoreDB.execute_complex_query(collection_name, conditions, order_by)
    
    @staticmethod
    def _get_all_documents(collection_name: str) -> List[Dict[str, Any]]:
        """
        Get all documents in a collection
        
        Args:
            collection_name: Name of the collection to query
            
        Returns:
            List of all documents in the collection
        """
        return FirestoreDB.get_all_documents(collection_name)

    @staticmethod
    def _update_document(collection_name: str, doc_id: str, field_updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update specific fields in a document
        
        Args:
            collection_name: Name of the collection containing the document
            doc_id: ID of the document to update
            field_updates: Dictionary of fields and values to update
            
        Returns:
            Dictionary with operation status and details
        """
        try:
            # Add timestamp for last_updated
            update_data = field_updates.copy()
            update_data["last_updated"] = datetime.now().isoformat()
            
            # Perform the update
            FirestoreDB.update_document(collection_name, doc_id, update_data)
            
            # Get the updated document
            updated_doc = FirestoreDB.get_document(collection_name, doc_id)
            
            return {
                "status": "success",
                "message": f"Document {doc_id} updated successfully",
                "document": updated_doc
            }
        except Exception as e:
            logging.error(f"Error updating document: {e}")
            return {
                "status": "error",
                "message": f"Failed to update document: {str(e)}"
            }
    
    @staticmethod
    def _parse_query(query_text: str) -> Dict[str, Any]:
        """
        Parse a natural language query into structured query parameters
        
        Args:
            query_text: Natural language query from user
            
        Returns:
            Dictionary with parsed query parameters
        """
        # Use OpenAI to parse the query
        messages = [
            {"role": "system", "content": """You are a specialized AI that translates natural language queries into structured database query parameters. Extract key search information from the query.
            
Return a JSON object with these fields:
- collection: The Firebase collection to query (jobs, candidates_data, interview_candidates, or final_candidates)
- operation: The operation to perform (query, update, analyze)
- conditions: Array of search conditions, each with field_path, operator, and value
- updates: For update operations, fields to update with new values
- order_by: Optional sorting instructions
- limit: Optional maximum number of results to return

Respond ONLY with the JSON object and nothing else."""},
            {"role": "user", "content": query_text}
        ]
        
        try:
            # Get the parsed parameters from OpenAI
            response = FirebaseQueryService._generate_openai_response(messages)
            
            # Extract JSON content
            json_content = response
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
            if match:
                json_content = match.group(1)
            
            # Parse and return
            parsed = json.loads(json_content)
            return parsed
        except Exception as e:
            logging.error(f"Error parsing query: {e}")
            # Return a default structure if parsing fails
            return {
                "collection": "unknown",
                "operation": "query",
                "conditions": [],
                "updates": {},
                "order_by": None,
                "limit": 10
            }

    @staticmethod
    def _enhance_response(query_results: Dict[str, Any], query_text: str) -> str:
        """
        Enhance the raw query results into a natural language response
        
        Args:
            query_results: Raw results from Firebase query
            query_text: Original natural language query
            
        Returns:
            Enhanced natural language response
        """
        # Use OpenAI to generate an enhanced response
        messages = [
            {"role": "system", "content": FirebaseQueryService._get_system_prompt()},
            {"role": "user", "content": f"Query: {query_text}\n\nDatabase results: {json.dumps(query_results, indent=2)}"}
        ]
        
        try:
            # Get the enhanced response from OpenAI
            return FirebaseQueryService._generate_openai_response(messages)
        except Exception as e:
            logging.error(f"Error enhancing response: {e}")
            # Return a basic response if enhancement fails
            if isinstance(query_results, list):
                return f"Found {len(query_results)} results for your query about {query_text}."
            else:
                return f"Completed the operation based on your request: {query_text}"
    
    @staticmethod
    def process_query(query_text: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a natural language query and execute the appropriate Firebase operation
        
        Args:
            query_text: Natural language query text from user
            conversation_id: Optional conversation ID for context
            
        Returns:
            Dictionary with response and metadata
        """
        try:
            # Generate a new conversation ID if not provided
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
            
            # Parse the query
            parsed_query = FirebaseQueryService._parse_query(query_text)
            
            # Execute the appropriate operation
            operation_result = None
            collection_name = parsed_query.get("collection", "jobs")  # Default to jobs collection
            
            if parsed_query["operation"] == "update":
                # Handle update operation
                if "doc_id" in parsed_query and parsed_query["updates"]:
                    operation_result = FirebaseQueryService._update_document(
                        collection_name, 
                        parsed_query["doc_id"], 
                        parsed_query["updates"]
                    )
                else:
                    operation_result = {"error": "Update operation requires doc_id and updates fields"}
            
            elif parsed_query["operation"] == "query":
                # Handle query operation
                conditions = parsed_query.get("conditions", [])
                
                if not conditions:
                    # No conditions, get all documents
                    operation_result = FirebaseQueryService._get_all_documents(collection_name)
                elif len(conditions) == 1:
                    # Simple query with one condition
                    condition = conditions[0]
                    operation_result = FirebaseQueryService._execute_query(
                        collection_name, 
                        condition["field_path"], 
                        condition["operator"], 
                        condition["value"]
                    )
                else:
                    # Complex query with multiple conditions
                    formatted_conditions = [(c["field_path"], c["operator"], c["value"]) for c in conditions]
                    order_by = None
                    if parsed_query.get("order_by"):
                        order_by = [(o["field"], o["direction"]) for o in parsed_query["order_by"]]
                    
                    operation_result = FirebaseQueryService._execute_complex_query(
                        collection_name, 
                        formatted_conditions, 
                        order_by
                    )
                    
                # Apply limit if specified
                if "limit" in parsed_query and isinstance(operation_result, list):
                    operation_result = operation_result[:parsed_query["limit"]]
            
            elif parsed_query["operation"] == "analyze":
                # For analysis, we need to get the data first
                if collection_name == "interview_candidates":
                    # Special handling for interview analysis
                    job_id = None
                    for condition in parsed_query.get("conditions", []):
                        if condition["field_path"] == "job_id":
                            job_id = condition["value"]
                            break
                            
                    if job_id:
                        # Get job details
                        job = JobService.get_job_posting(job_id)
                        
                        # Get all interview candidates for this job
                        interviews = InterviewService.get_interview_candidates_by_job_id(job_id)
                        
                        # Format the results
                        operation_result = {
                            "job": job,
                            "interviews": interviews,
                            "statistics": InterviewService.get_tracking_statistics_by_job(job_id)
                        }
                    else:
                        # No job ID, get overall statistics
                        all_interviews = FirebaseQueryService._get_all_documents("interview_candidates")
                        operation_result = {
                            "total_interviews": len(all_interviews),
                            "interviews": all_interviews
                        }
                elif collection_name == "final_candidates":
                    # Analysis of final selections
                    all_final = FirebaseQueryService._get_all_documents("final_candidates")
                    operation_result = {
                        "total_offers": len(all_final),
                        "offers": all_final
                    }
                else:
                    # General analysis of the collection
                    all_docs = FirebaseQueryService._get_all_documents(collection_name)
                    operation_result = {
                        "total_documents": len(all_docs),
                        "documents": all_docs
                    }
            else:
                operation_result = {"error": f"Unknown operation: {parsed_query['operation']}"}
            
            # Enhance the response
            enhanced_response = FirebaseQueryService._enhance_response(operation_result, query_text)
            
            # Save conversation history if needed
            # Implement conversation history storage here
            
            return {
                "response": enhanced_response,
                "conversation_id": conversation_id,
                "parsed_query": parsed_query,
                "raw_result": operation_result
            }
        
        except Exception as e:
            logging.error(f"Error processing query: {str(e)}")
            return {
                "response": f"I encountered an error processing your request: {str(e)}",
                "conversation_id": conversation_id or str(uuid.uuid4()),
                "error": str(e)
            }
    
    @staticmethod
    def update_interview_feedback(interview_id: str, round_index: int, feedback: str, 
                                 rating: int, selected_for_next: str) -> Dict[str, Any]:
        """
        Update the feedback for a specific interview round
        
        Args:
            interview_id: ID of the interview candidate document
            round_index: Index of the interview round (0-based)
            feedback: Feedback text from the interviewer
            rating: Rating out of 10
            selected_for_next: 'yes' or 'no' indicating if candidate moves to next round
            
        Returns:
            Dictionary with update status and details
        """
        try:
            # Get the current interview document
            interview_doc = FirestoreDB.get_document("interview_candidates", interview_id)
            
            if not interview_doc:
                return {"error": f"Interview candidate with ID {interview_id} not found"}
            
            # Get the feedback array
            feedback_array = interview_doc.get("feedback", [])
            
            # Check if the round_index is valid
            if round_index < 0 or round_index >= len(feedback_array):
                return {"error": f"Invalid round index {round_index}. Available rounds: 0-{len(feedback_array)-1}"}
            
            # Update the feedback for this round
            feedback_array[round_index]["feedback"] = feedback
            feedback_array[round_index]["rating_out_of_10"] = rating
            feedback_array[round_index]["isSelectedForNextRound"] = selected_for_next
            
            # Update completedRounds if this is the current round
            next_round_index = interview_doc.get("nextRoundIndex", 0)
            if round_index == next_round_index:
                interview_doc["nextRoundIndex"] = next_round_index + 1
                interview_doc["completedRounds"] = interview_doc.get("completedRounds", 0) + 1
                
                # Update current_round_scheduled status
                interview_doc["current_round_scheduled"] = False
            
            # Update the document
            update_data = {
                "feedback": feedback_array,
                "nextRoundIndex": interview_doc.get("nextRoundIndex", 0),
                "completedRounds": interview_doc.get("completedRounds", 0),
                "current_round_scheduled": interview_doc.get("current_round_scheduled", False),
                "last_updated": datetime.now().isoformat()
            }
            
            # Determine if all rounds are complete
            if interview_doc.get("completedRounds", 0) >= interview_doc.get("no_of_interviews", 1):
                # All rounds complete, update status
                update_data["status"] = "completed"
                
                # Check if candidate was selected in all rounds
                all_selected = True
                total_rating = 0
                for round_feedback in feedback_array:
                    if round_feedback.get("isSelectedForNextRound") != "yes":
                        all_selected = False
                        break
                    total_rating += round_feedback.get("rating_out_of_10", 0)
                
                # If selected in all rounds, move to final candidates
                if all_selected:
                    update_data["status"] = "selected"
                    
                    # Create entry in final_candidates collection
                    final_candidate = {
                        "candidate_id": interview_doc.get("candidate_id"),
                        "candidate_name": interview_doc.get("candidate_name"),
                        "email": interview_doc.get("candidate_email"),
                        "job_id": interview_doc.get("job_id"),
                        "job_role": interview_doc.get("job_role"),
                        "status": "selected",
                        "average_rating": total_rating / len(feedback_array),
                        "created_at": datetime.now().isoformat()
                    }
                    
                    # Create the final candidate document
                    final_id = FirestoreDB.create_document("final_candidates", final_candidate)
                    
                    # Add the final_candidate_id to the update
                    update_data["final_candidate_id"] = final_id
            
            # Perform the update
            FirestoreDB.update_document("interview_candidates", interview_id, update_data)
            
            # Get the updated document
            updated_doc = FirestoreDB.get_document("interview_candidates", interview_id)
            
            return {
                "status": "success",
                "message": f"Feedback for interview {interview_id}, round {round_index} updated successfully",
                "document": updated_doc
            }
        except Exception as e:
            logging.error(f"Error updating interview feedback: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to update feedback: {str(e)}"
            }
    
    @staticmethod
    def get_conversation_history(conversation_id: str) -> List[Dict[str, Any]]:
        """
        Get the conversation history for a specific conversation
        
        Args:
            conversation_id: ID of the conversation
            
        Returns:
            List of conversation messages
        """
        try:
            # Query the history collection for this conversation
            history_docs = FirestoreDB.execute_query(
                FirebaseQueryService.CHAT_HISTORY_COLLECTION,
                "conversation_id",
                "==",
                conversation_id
            )
            
            # Sort by timestamp
            sorted_history = sorted(history_docs, key=lambda x: x.get("timestamp", ""))
            
            return sorted_history
        except Exception as e:
            logging.error(f"Error retrieving conversation history: {str(e)}")
            return []
    
    @staticmethod
    def add_to_conversation_history(conversation_id: str, query: str, response: str) -> bool:
        """
        Add a query-response pair to the conversation history
        
        Args:
            conversation_id: ID of the conversation
            query: User's query text
            response: Assistant's response text
            
        Returns:
            Boolean indicating success
        """
        try:
            # Create the history document
            history_doc = {
                "conversation_id": conversation_id,
                "query": query,
                "response": response,
                "timestamp": datetime.now().isoformat()
            }
            
            # Save to Firebase
            FirestoreDB.create_document(FirebaseQueryService.CHAT_HISTORY_COLLECTION, history_doc)
            
            return True
        except Exception as e:
            logging.error(f"Error saving conversation history: {str(e)}")
            return False
