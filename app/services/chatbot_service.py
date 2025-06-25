"""
Service for handling chatbot interactions using LangChain and OpenAI
"""
import json
import uuid
import re
import logging
from typing import Dict, Any, List, Optional, Tuple

from langchain.chains import LLMChain
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import SystemMessage, HumanMessage, AIMessage

import openai
from fastapi import HTTPException

from app.database.chroma_db import FirestoreDB, ChromaVectorDB
from app.services.job_service import JobService
from app.services.candidate_service import CandidateService, extract_resume_data
from app.services.interview_service import InterviewService
from app.services.interview_shortlist_service import InterviewShortlistService
from app.services.final_selection_service import FinalSelectionService


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
            },
            {
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
Your job is to understand what the user is trying to do, and then execute the appropriate API call.

# DETAILED API DOCUMENTATION

{combined_docs}

# REQUEST HANDLING INSTRUCTIONS

For each user message:
1. Analyze what the user wants to do
2. Determine which API endpoint from the documentation above would fulfill this request
3. Extract all required parameters from the user's message
4. Execute the API call with the extracted parameters
5. Return the results in a friendly, helpful way
6. Suggest next steps the user might want to take

# IMPORTANT RULES

- Only use the API endpoints listed in the documentation above. Don't make up new endpoints.
- If you don't have enough information, ask the user for clarification.
- If the request is outside the scope of managing interviews, job postings, and candidates, politely inform the user.
- If an API call fails, explain the error and suggest how to fix it.
- Always return the executed API call and its results for transparency.
- ONLY discuss and retrieve information relevant to this Interview Scheduling system.

# PARAMETER HANDLING GUIDELINES

- When a parameter is not explicitly provided by the user:
  * For job_id: Use the first available job if possible
  * For integer values: Use 0 as default
  * For string values: Use a placeholder with format default_param_name
  * For object/dict values: Use an empty object

# JOB POSTING GUIDELINES

When creating a new job posting, extract the following fields:
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
        Create a LangChain LLM chain for processing chat messages
        
        Args:
            temperature: Temperature parameter for the OpenAI model
        
        Returns:
            LLMChain object
        """
        # Create prompt template
        system_prompt = ChatbotService._get_system_prompt()
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            HumanMessage(content="{input}")
        ])
        
        # Create LLM
        llm = ChatOpenAI(
            model_name="gpt-4o", 
            temperature=temperature, 
            # Use the OpenAI API key from environment
        )
        
        # Create memory
        memory = ConversationBufferMemory(return_messages=True, input_key="input", memory_key="chat_history")
        
        # Create chain
        chain = LLMChain(llm=llm, prompt=prompt, memory=memory, verbose=True)
        
        return chain
        
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
                    final_candidates = FinalSelectionService.get_final_candidates_by_job(job_id)
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
                                candidate = CandidateService.get_candidate_by_id(candidate_id)
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
                    candidate = CandidateService.get_candidate_by_id(candidate_id)
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
                            candidate = CandidateService.get_candidate_by_id(candidate_id)
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
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a response using the chatbot
        
        Args:
            message: The user's message
            conversation_id: Optional conversation ID to continue
            context: Optional additional context for the LLM
        
        Returns:
            Response dictionary containing the assistant's message and metadata
        """
        try:
            # Initialize conversation ID if not provided
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
            
            # Set up LLM chain - optimized to skip history retrieval
            chain = ChatbotService.create_llm_chain()
            
            # Fetch relevant data from Firebase based on the user's message
            db_context = ChatbotService._fetch_relevant_data(message)
            
            # Include all context
            input_text = message
            context_parts = []
            
            # Add database schema information
            context_parts.append("DATABASE SCHEMA:\n" + ChatbotService._get_database_schema())
            
            # Add fetched data context
            if db_context:
                context_parts.append("RELEVANT DATA FROM DATABASE:\n" + json.dumps(db_context, indent=2))
            
            # Add any additional context provided
            if context:
                context_parts.append("ADDITIONAL CONTEXT:\n" + json.dumps(context, indent=2))
            
            # Add combined context if any context parts exist
            if context_parts:
                input_text += "\n\n" + "\n\n".join(context_parts)
            
            try:
                # Generate response from OpenAI using the new API format (>=1.0.0)
                client = openai.OpenAI()  # Create a client instance
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": ChatbotService._get_system_prompt()},
                        {"role": "user", "content": input_text}
                    ],
                    temperature=0.2
                )
            except Exception as e:
                logging.error(f"Error generating OpenAI response: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error with OpenAI: {str(e)}")
            
            # Extract the response text - updated for new OpenAI API response format
            full_response_text = response.choices[0].message.content
            
            # Trim content from "### Result" to "#" as requested
            response_text = full_response_text
            result_marker = "```"
            end_marker = "```"
            
            if result_marker in full_response_text:
                result_section_start = full_response_text.find(result_marker)
                # Find the next occurrence of # after the result_marker
                end_section = full_response_text.find(end_marker, result_section_start + len(result_marker))
                
                if end_section > result_section_start:
                    # Extract only the content between the markers, excluding the markers themselves
                    trimmed_content = full_response_text[result_section_start + len(result_marker):end_section].strip()
                    response_text = trimmed_content
            
            # Parse the response to extract any API calls that were made
            api_call_info = ChatbotService._extract_api_call_info(response_text)
            executed_action = None
            
            # Execute the API call if identified
            if api_call_info:
                executed_action = ChatbotService._execute_api_call(api_call_info, message)
                
            # Set a minimal response structure
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
    def _execute_api_call(api_call_info: Dict[str, Any], user_message: str) -> Dict[str, Any]:
        """
        Execute an API call based on extracted information
        
        Args:
            api_call_info: Dictionary with API call information
            user_message: The user's message to extract parameters from
        
        Returns:
            Dictionary with API call results
        """
        try:
            endpoint = api_call_info['endpoint']
            function = endpoint['function']
            params = endpoint['params']
            
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
            client = openai.OpenAI()  # Create a client instance
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
                from app.schemas.job_schema import JobPostingCreate
                
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
                
                # Create JobPostingCreate object
                try:
                    job_posting = JobPostingCreate(
                        job_role_name=job_role_name or "Default Job Title",
                        job_description=job_description or "Default job description",
                        years_of_experience_needed=str(years_of_experience),
                        status=status,
                        location=location
                    )
                    print(f"Created job posting with years_of_experience_needed: {job_posting.years_of_experience_needed}")
                except Exception as validation_error:
                    logging.error(f"Validation error creating job posting: {validation_error}")
                    # Create with explicit string values as fallback
                    job_posting = JobPostingCreate(
                        job_role_name="Default Job Title",
                        job_description="Default job description",
                        years_of_experience_needed="1-3 years",
                        status="open",
                        location="remote"
                    )
                
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
