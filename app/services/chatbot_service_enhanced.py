"""
Enhanced service for handling chatbot interactions with better agent integration
"""
import json
import uuid
import re
import logging
from typing import Dict, Any, List, Optional, Tuple, Union

from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import SystemMessage, HumanMessage, AIMessage

import openai
from fastapi import HTTPException

from app.database.firebase_db import FirestoreDB
from app.services.job_service import JobService
from app.services.candidate_service import CandidateService, extract_resume_data
from app.services.interview_service import InterviewService
from app.services.interview_shortlist_service import InterviewShortlistService
from app.services.final_selection_service import FinalSelectionService

# Import specialized agents for direct integration
from app.agents.specialized_agents import (
    run_shortlisting_process,
    run_scheduling_process, 
    run_end_to_end_process
)
from app.agents.job_agents import (
    run_job_creation_process,
    run_job_retrieval_process,
    run_resume_processing_process
)


class ChatbotServiceEnhanced:
    """Enhanced service for handling chatbot interactions with direct agent integration"""

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
            
            # SPECIALIZED AGENT ENDPOINTS - New direct agent integrations
            # Job Management Agents
            {
                "path": "/agents/create-job",
                "method": "POST",
                "description": "Run the AI agent to create a new job posting",
                "function": run_job_creation_process,
                "params": {
                    "job_details": "object"
                },
                "keywords": [
                    "create job", "add job", "new job", "post job", "create position",
                    "add position", "new posting", "job posting", "add opening", "new role"
                ]
            },
            {
                "path": "/agents/get-jobs",
                "method": "GET",
                "description": "Run the AI agent to retrieve job information",
                "function": run_job_retrieval_process,
                "params": {
                    "job_id": "string"
                },
                "keywords": [
                    "get jobs", "list jobs", "show jobs", "find jobs", "job listings",
                    "available jobs", "job details", "view jobs", "job info", "job information"
                ]
            },
            {
                "path": "/agents/process-resumes",
                "method": "POST",
                "description": "Run the AI agent to process resume data for a job",
                "function": run_resume_processing_process,
                "params": {
                    "job_id": "string"
                },
                "keywords": [
                    "process resumes", "analyze resumes", "review candidates", "check applications",
                    "parse resumes", "candidate data", "resume analysis", "applicant review"
                ]
            },
            # Interview Management Agents
            {
                "path": "/agents/shortlist",
                "method": "POST",
                "description": "Run the AI agent to shortlist candidates for a job using advanced techniques",
                "function": run_shortlisting_process,
                "params": {
                    "job_id": "string", 
                    "number_of_candidates": "integer"
                },
                "keywords": [
                    "shortlist", "select candidates", "pick best candidates", "find top candidates",
                    "choose candidates", "select best", "shortlist candidates", "ai shortlist"
                ]
            },
            {
                "path": "/agents/schedule",
                "method": "POST",
                "description": "Run the AI agent to schedule interviews for shortlisted candidates",
                "function": run_scheduling_process,
                "params": {
                    "job_id": "string", 
                    "interview_date": "string", 
                    "number_of_rounds": "integer"
                },
                "keywords": [
                    "schedule interview", "book interview", "create interview", "set up interview",
                    "arrange interview", "interview schedule", "set interview", "calendar"
                ]
            },
            {
                "path": "/agents/end-to-end",
                "method": "POST",
                "description": "Run the AI agent for the entire process from shortlisting to scheduling",
                "function": run_end_to_end_process,
                "params": {
                    "job_id": "string", 
                    "number_of_candidates": "integer", 
                    "interview_date": "string", 
                    "number_of_rounds": "integer"
                },
                "keywords": [
                    "complete process", "full process", "shortlist and schedule", "end to end",
                    "shortlist then schedule", "entire process", "full interview process"
                ]
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
        registry = ChatbotServiceEnhanced._get_api_registry()
        
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
                        default_info = " (Default: appropriate value based on context)"
                    elif param_type == "string" and param_name == "interview_date":
                        default_info = " (Default: tomorrow's date)"
                    elif param_type == "string":
                        default_info = f" (Default: will be inferred from context)"
                    
                    endpoint_doc += f"\n- `{param_name}`: {param_type}{default_info}"
            
            # Add keyword matches for specialized agents
            if "keywords" in endpoint:
                endpoint_doc += "\n\n**Triggered by phrases like:**\n"
                keyword_groups = [endpoint["keywords"][i:i+3] for i in range(0, len(endpoint["keywords"]), 3)]
                for group in keyword_groups:
                    endpoint_doc += "\n- " + ", ".join([f'"{kw}"' for kw in group])
            
            detailed_docs.append(endpoint_doc)
        
        combined_docs = "\n\n".join(detailed_docs)
        
        system_prompt = f"""You are an AI assistant that helps users interact with an Interview Scheduler API and its advanced AI agents.
Your job is to understand what the user is trying to do, and then execute the appropriate API call or agent.

# DETAILED API DOCUMENTATION

{combined_docs}

# SPECIALIZED AGENT CAPABILITIES

You have access to powerful AI agents that can perform complex tasks:

1. Shortlisting Agent: Analyzes candidates based on their AI fit scores, skills, experience, and other qualifications to select the best candidates for interviews.

2. Scheduling Agent: Manages the scheduling process including calendar integration, meeting invites, and email notifications.

3. End-to-End Agent: Combines shortlisting and scheduling into one seamless process.

These agents are your most powerful tools for helping users with interview processes. Use them whenever a user wants to shortlist candidates, schedule interviews, or both.

# REQUEST HANDLING INSTRUCTIONS

For each user message:
1. Analyze what the user wants to do
2. Determine if this is a task for one of the specialized agents based on keywords
3. If so, execute the appropriate agent with the extracted parameters
4. Otherwise, determine which regular API endpoint would fulfill this request
5. Extract all required parameters from the user's message
6. Execute the API call with the extracted parameters
7. Return the results in a friendly, helpful way
8. Suggest next steps the user might want to take

# IMPORTANT RULES

- Use specialized agents for complex tasks like shortlisting and scheduling.
- If the user mentions scheduling or shortlisting, use the appropriate agent rather than the basic API endpoints.
- If you don't have enough information, ask the user for clarification.
- If an API call fails, explain the error and suggest how to fix it.
- Always return the executed API call and its results for transparency.
- ONLY discuss and retrieve information relevant to this Interview Scheduling system.

You are now ready to help users interact with the Interview Scheduler API and its specialized agents using natural language!
"""
        return system_prompt

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
            
            # Extract initial intent for specialized agent detection
            intent = ChatbotServiceEnhanced._extract_initial_intent(message)
            
            # Check if this should be handled by a specialized agent
            agent_endpoint = ChatbotServiceEnhanced._match_to_specialized_agent(message, intent)
            
            if agent_endpoint:
                # Process using specialized agent
                return ChatbotServiceEnhanced._process_with_specialized_agent(
                    message, agent_endpoint, conversation_id, context
                )
            
            # Otherwise, use the regular chatbot flow
            
            # Set up LLM chain - optimized to skip history retrieval
            prompt = ChatbotServiceEnhanced._get_system_prompt()
            
            # Fetch relevant data from Firebase based on the user's message
            db_context = ChatbotServiceEnhanced._fetch_relevant_data(message)
            
            # Include all context
            input_text = message
            context_parts = []
            
            # Add database schema information
            context_parts.append("DATABASE SCHEMA:\n" + ChatbotServiceEnhanced._get_database_schema())
            
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
                # Generate response from OpenAI using the API format
                client = openai.OpenAI()  # Create a client instance
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": prompt},
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
            api_call_info = ChatbotServiceEnhanced._extract_api_call_info(response_text)
            executed_action = None
            
            # Execute the API call if identified
            if api_call_info:
                executed_action = ChatbotServiceEnhanced._execute_api_call(api_call_info, message)
                
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
    def _extract_initial_intent(message: str) -> Dict[str, float]:
        """
        Extract the initial intent of the user message
        
        Args:
            message: The user's message
        
        Returns:
            Dictionary with intent categories and their confidence scores
        """
        intent_categories = {
            # Job management categories
            "create_job": ["create job", "add job", "new job", "post job", "add position", "new role", "job posting"],
            "get_jobs": ["get jobs", "list jobs", "show jobs", "find jobs", "job listings", "job details", "view jobs"],
            "process_resumes": ["process resumes", "analyze resumes", "review candidates", "candidate data", "resume analysis"],
            
            # Interview management categories
            "shortlist": ["shortlist", "select", "choose", "best candidate", "top candidate", "pick", "filter"],
            "schedule": ["schedule", "book", "calendar", "interview time", "interview slot", "arrange meeting", "set up interview"],
            "end_to_end": ["end to end", "full process", "complete process", "entire process", "shortlist and schedule", "both"]
        }
        
        intent_scores = {}
        
        # Simple keyword matching
        for category, keywords in intent_categories.items():
            score = 0
            message_lower = message.lower()
            
            # Each keyword match increases the score
            for keyword in keywords:
                if keyword in message_lower:
                    score += 1
            
            # Normalize the score
            if score > 0:
                intent_scores[category] = min(score / len(keywords), 1.0)
            else:
                intent_scores[category] = 0.0
        
        return intent_scores

    @staticmethod
    def _match_to_specialized_agent(message: str, intent: Dict[str, float]) -> Optional[Dict[str, Any]]:
        """
        Match the user message to a specialized agent based on intent and keywords
        
        Args:
            message: The user's message
            intent: Dictionary with intent categories and confidence scores
        
        Returns:
            API endpoint info for the matched agent or None if no match
        """
        # Get the API registry
        registry = ChatbotServiceEnhanced._get_api_registry()
        
        # Only consider endpoints with 'keywords' field - these are the specialized agent endpoints
        specialized_endpoints = [endpoint for endpoint in registry if 'keywords' in endpoint]
        
        # If any intent score is above threshold, check for matching endpoint
        intent_threshold = 0.5
        prioritized_category = None
        
        # Check if any intent hits the threshold
        for category, score in sorted(intent.items(), key=lambda x: x[1], reverse=True):
            if score >= intent_threshold:
                prioritized_category = category
                break
        
        # Match endpoint to category
        category_endpoint_map = {
            # Job management
            "create_job": "/agents/create-job",
            "get_jobs": "/agents/get-jobs",
            "process_resumes": "/agents/process-resumes",
            
            # Interview management
            "shortlist": "/agents/shortlist",
            "schedule": "/agents/schedule",
            "end_to_end": "/agents/end-to-end"
        }
        
        # Check if we have a priority category match
        if prioritized_category and prioritized_category in category_endpoint_map:
            target_path = category_endpoint_map[prioritized_category]
            for endpoint in specialized_endpoints:
                if endpoint["path"] == target_path:
                    return endpoint
        
        # If no clear intent match, do keyword matching directly
        message_lower = message.lower()
        for endpoint in specialized_endpoints:
            for keyword in endpoint.get("keywords", []):
                if keyword.lower() in message_lower:
                    return endpoint
        
        # No match found
        return None

    @staticmethod
    def _process_with_specialized_agent(
        message: str, 
        agent_endpoint: Dict[str, Any],
        conversation_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a message using a specialized agent
        
        Args:
            message: The user's message
            agent_endpoint: The agent endpoint info from the API registry
            conversation_id: Conversation ID
            context: Optional additional context
            
        Returns:
            Response dictionary
        """
        try:
            # Extract parameters for the agent
            params = ChatbotServiceEnhanced._extract_agent_parameters(message, agent_endpoint)
            
            # Execute the agent function
            function = agent_endpoint["function"]
            result = function(**params)
            
            # Make the result JSON serializable
            json_serializable_result = ChatbotServiceEnhanced._make_serializable(result)
            
            # Generate a response based on the agent used
            agent_type = ""
            if agent_endpoint["path"] == "/agents/shortlist":
                agent_type = "shortlisting"
            elif agent_endpoint["path"] == "/agents/schedule":
                agent_type = "scheduling"
            else:
                agent_type = "end-to-end"
                
            # Create a response for the user
            response_text = f"I've completed the {agent_type} process using our specialized AI agent. "
            
            if agent_type == "shortlisting":
                response_text += "The agent has analyzed all candidates and selected the best matches based on skills, experience and AI fit scores."
            elif agent_type == "scheduling":
                response_text += "The agent has scheduled interviews for the shortlisted candidates, created calendar events, and sent email notifications."
            else:
                response_text += "The agent has both shortlisted the best candidates and scheduled their interviews, creating calendar events and sending notifications."
            
            action_result = {
                "path": agent_endpoint["path"],
                "method": agent_endpoint["method"],
                "params": params,
                "result": json_serializable_result
            }
            
            # Return the final response
            return {
                "response": response_text,
                "conversation_id": conversation_id,
                "executed_action": action_result,
                "action_result": json_serializable_result
            }
            
        except Exception as e:
            logging.error(f"Error processing with specialized agent: {str(e)}")
            return {
                "response": f"I encountered an error while trying to use the specialized agent: {str(e)}",
                "conversation_id": conversation_id,
                "executed_action": None,
                "action_result": None
            }
    
    @staticmethod
    def _extract_agent_parameters(message: str, agent_endpoint: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract parameters for a specialized agent from the user message
        
        Args:
            message: The user's message
            agent_endpoint: The agent endpoint info from the API registry
            
        Returns:
            Dictionary with parameter values
        """
        params = agent_endpoint["params"]
        extracted_params = {}
        
        # Special handling for job creation
        if agent_endpoint["path"] == "/agents/create-job":
            # Use OpenAI to extract job details with exact schema
            prompt = f"""
            Extract the complete job details from this text:
            
            Text: "{message}"
            
            Return ONLY a JSON object that precisely follows this schema:
            {{
              "job_details": {{
                "job_role_name": "", // Required: The title of the position
                "job_description": "", // Required: Detailed description of responsibilities
                "years_of_experience_needed": "", // Required: Experience required in format like "3-5 years"
                "location": "", // Required: Location of the job
                "status": "open" // Default to "open"
              }}
            }}
            
            Extract as much detail as possible from the text and ensure the values accurately reflect the job posting information.
            """
            
            try:
                client = openai.OpenAI()
                extraction_response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                
                extraction_text = extraction_response.choices[0].message.content
                
                # Extract JSON from the response
                json_match = re.search(r'```json\s*([\s\S]*?)\s*```|({[\s\S]*?})', extraction_text)
                if json_match:
                    json_content = json_match.group(1) or json_match.group(2)
                    job_data = json.loads(json_content)
                else:
                    job_data = json.loads(extraction_text)
                
                # Make sure we have the job_details object
                if "job_details" in job_data:
                    extracted_params = {"job_details": job_data["job_details"]}
                else:
                    extracted_params = {"job_details": job_data}
                
                print(f"Extracted job details: {extracted_params}")
                return extracted_params
            except Exception as e:
                logging.error(f"Error extracting job details: {str(e)}")
                # Create default values if extraction fails
                extracted_params = {
                    "job_details": {
                        "job_role_name": "Software Engineer",
                        "job_description": "Default job description extracted from user query",
                        "years_of_experience_needed": "0-3 years",
                        "location": "Remote",
                        "status": "open"
                    }
                }
                return extracted_params
        
        # Normal parameter extraction for other agents
        prompt = f"""
        Extract parameters from the user message for the specialized agent call:
        
        Agent: {agent_endpoint['path']} ({agent_endpoint['method']})
        Required parameters: {json.dumps(params)}
        User message: "{message}"
        
        For any parameters not explicitly mentioned:
        - If job_id is needed but not specified, make a note to use the first available job
        - If number_of_candidates is needed but not specified, use 3
        - If number_of_rounds is needed but not specified, use 2
        - If interview_date is needed but not specified, use tomorrow's date
        
        Return ONLY a JSON object with parameter names as keys and extracted values.
        """
        
        # Get parameter extraction from OpenAI
        client = openai.OpenAI()
        extraction_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        # Parse the extraction result
        try:
            extraction_text = extraction_response.choices[0].message.content
            # Extract JSON content from the response
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```|({[\s\S]*?})', extraction_text)
            if json_match:
                json_content = json_match.group(1) or json_match.group(2)
                extracted_params = json.loads(json_content)
            else:
                extracted_params = json.loads(extraction_text)
        except Exception as e:
            logging.error(f"Error parsing parameter extraction: {str(e)}")
            # Set defaults for all required parameters
            for param_name, param_type in params.items():
                extracted_params[param_name] = None
        
        # Handle any missing parameters with appropriate defaults
        for param_name, param_type in params.items():
            if param_name not in extracted_params or extracted_params[param_name] is None:
                if param_name == "job_id":
                    # Get the first job ID from the database
                    try:
                        all_jobs = JobService.get_all_job_postings()
                        if all_jobs and len(all_jobs) > 0:
                            first_job = all_jobs[0]
                            if hasattr(first_job, "job_id"):
                                extracted_params[param_name] = first_job.job_id
                            elif hasattr(first_job, "id"):
                                extracted_params[param_name] = first_job.id
                            elif isinstance(first_job, dict) and "job_id" in first_job:
                                extracted_params[param_name] = first_job["job_id"]
                            elif isinstance(first_job, dict) and "id" in first_job:
                                extracted_params[param_name] = first_job["id"]
                            else:
                                extracted_params[param_name] = "default_job_id"
                        else:
                            extracted_params[param_name] = "default_job_id"
                    except Exception:
                        extracted_params[param_name] = "default_job_id"
                elif param_name == "number_of_candidates":
                    extracted_params[param_name] = 3
                elif param_name == "number_of_rounds":
                    extracted_params[param_name] = 2
                elif param_name == "interview_date":
                    # Set to tomorrow's date in ISO format
                    from datetime import datetime, timedelta
                    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
                    extracted_params[param_name] = tomorrow
                else:
                    # Generic defaults
                    if param_type == "string":
                        extracted_params[param_name] = f"default_{param_name}"
                    elif param_type == "integer":
                        extracted_params[param_name] = 0
                    else:
                        extracted_params[param_name] = None
        
        return extracted_params
        
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
                    data["job"] = ChatbotServiceEnhanced._make_serializable(job)
            
            # If the message mentions "final offer" or related terms, fetch final candidates data
            if any(term in message.lower() for term in ["final offer", "offer letter", "selected", "hiring"]) and job_id:
                try:
                    # Get final candidates for the job using service
                    final_candidates = FinalSelectionService.get_final_candidates_by_job(job_id)
                    if final_candidates:
                        data["final_candidates"] = ChatbotServiceEnhanced._make_serializable(final_candidates)
                    
                    # Get interview candidates for the job
                    interview_candidates = InterviewService.get_interview_candidates_by_job_id(job_id)
                    if interview_candidates:
                        data["interview_candidates"] = ChatbotServiceEnhanced._make_serializable(interview_candidates)
                        
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
                                    data["candidates"].append(ChatbotServiceEnhanced._make_serializable(candidate))
                except Exception as service_error:
                    logging.error(f"Error fetching final candidates data: {service_error}")
            
            # If the message is about statistics or performance
            if any(term in message.lower() for term in ["statistics", "performance", "metrics", "tracking"]) and job_id:
                try:
                    # Get interview statistics using service
                    statistics = InterviewService.get_tracking_statistics_by_job(job_id)
                    if statistics:
                        data["interview_statistics"] = ChatbotServiceEnhanced._make_serializable(statistics)
                except Exception as stats_error:
                    logging.error(f"Error fetching interview statistics: {stats_error}")
            
            # If a specific candidate ID is mentioned
            if candidate_id:
                try:
                    candidate = CandidateService.get_candidate_by_id(candidate_id)
                    if candidate:
                        data["candidate"] = ChatbotServiceEnhanced._make_serializable(candidate)
                except Exception as candidate_error:
                    logging.error(f"Error fetching candidate: {candidate_error}")
            
            # If a specific interview ID is mentioned
            if interview_id:
                try:
                    interview = InterviewService.get_interview_candidate(interview_id)
                    if interview:
                        data["interview"] = ChatbotServiceEnhanced._make_serializable(interview)
                        
                        # Get candidate for this interview
                        candidate_id = getattr(interview, "candidate_id", None)
                        if candidate_id:
                            candidate = CandidateService.get_candidate_by_id(candidate_id)
                            if candidate:
                                data["candidate"] = ChatbotServiceEnhanced._make_serializable(candidate)
                except Exception as interview_error:
                    logging.error(f"Error fetching interview: {interview_error}")
                    
            return data
            
        except Exception as e:
            logging.error(f"Error fetching relevant data: {str(e)}")
            return {}
            
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
        registry = ChatbotServiceEnhanced._get_api_registry()
        
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
            
            # Use OpenAI to extract parameters
            prompt = f"""
            Extract parameters from the user message for the API call:
            
            API: {api_call_info['path']} ({api_call_info['method']})
            Required parameters: {json.dumps(params)}
            User message: "{user_message}"
            
            Return ONLY a JSON object with parameter names as keys and extracted values.
            """
            
            # Get parameter extraction from OpenAI using the API format
            client = openai.OpenAI()  # Create a client instance
            extraction_response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            # Parse the extraction result
            try:
                extraction_text = extraction_response.choices[0].message.content
                # Extract JSON content from the response
                json_match = re.search(r'```json\s*([\s\S]*?)\s*```|({[\s\S]*?})', extraction_text)
                if json_match:
                    json_content = json_match.group(1) or json_match.group(2)
                    param_values = json.loads(json_content)
                else:
                    param_values = json.loads(extraction_text)
            except Exception as e:
                logging.error(f"Error parsing parameter extraction: {str(e)}")
                
            # Handle any missing parameters with appropriate defaults
            for param_name, param_type in params.items():
                if param_name not in param_values or param_values[param_name] is None:
                    if param_name == "job_id":
                        # Get the first job ID from the database
                        try:
                            all_jobs = JobService.get_all_job_postings()
                            if all_jobs and len(all_jobs) > 0:
                                first_job = all_jobs[0]
                                if hasattr(first_job, "job_id"):
                                    param_values[param_name] = first_job.job_id
                                elif hasattr(first_job, "id"):
                                    param_values[param_name] = first_job.id
                                elif isinstance(first_job, dict) and "job_id" in first_job:
                                    param_values[param_name] = first_job["job_id"]
                                elif isinstance(first_job, dict) and "id" in first_job:
                                    param_values[param_name] = first_job["id"]
                                else:
                                    param_values[param_name] = "default_job_id"
                            else:
                                param_values[param_name] = "default_job_id"
                        except Exception:
                            param_values[param_name] = "default_job_id"
                    else:
                        # Generic handling for other parameters
                        if param_type == "string":
                            param_values[param_name] = f"default_{param_name}"
                        elif param_type == "integer":
                            param_values[param_name] = 0
                        else:
                            param_values[param_name] = None
            
            # Execute the function with the extracted parameters
            result = function(**param_values)
            
            # Make the result JSON serializable
            json_serializable_result = ChatbotServiceEnhanced._make_serializable(result)
            
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
            return {k: ChatbotServiceEnhanced._make_serializable(v) for k, v in obj.__dict__.items() 
                   if not k.startswith('_') and not callable(v)}
        elif isinstance(obj, dict):
            # Process each item in dictionaries
            return {k: ChatbotServiceEnhanced._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            # Process each item in lists
            return [ChatbotServiceEnhanced._make_serializable(i) for i in obj]
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
