"""
Advanced Multi-Contextual Chatbot Service

This service provides a comprehensive chatbot solution with:
- Multi-contextual conversation support
- Professional response handling
- Database querying capabilities
- NLP processing for various scenarios
- Specialized agent integration
- Error handling and fallback mechanisms
"""

import json
import uuid
import re
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
import asyncio
from enum import Enum

# Remove deprecated LangChain imports to avoid compatibility issues
# from langchain.chains import LLMChain
# from langchain.chat_models import ChatOpenAI
# from langchain.memory import ConversationBufferWindowMemory, ConversationSummaryBufferMemory
# from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
# from langchain.schema import SystemMessage, HumanMessage, AIMessage
# from langchain.tools import BaseTool
# from langchain.agents import initialize_agent, AgentType

import openai
from fastapi import HTTPException

# Database and services imports
from app.database.firebase_db import FirestoreDB
from app.services.job_service import JobService
from app.services.candidate_service import CandidateService
from app.services.interview_service import InterviewService
from app.services.final_selection_service import FinalSelectionService
from app.services.firebase_query_service import FirebaseQueryService

# Agent imports
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

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConversationContext(Enum):
    """Enumeration of conversation contexts"""
    GENERAL = "general"
    JOB_MANAGEMENT = "job_management"
    CANDIDATE_MANAGEMENT = "candidate_management"
    INTERVIEW_PROCESS = "interview_process"
    DATABASE_QUERY = "database_query"
    ANALYTICS = "analytics"
    SCHEDULING = "scheduling"
    TECHNICAL_SUPPORT = "technical_support"
    OUT_OF_CONTEXT = "out_of_context"
    SMALL_TALK = "small_talk"
    UNKNOWN = "unknown"

class IntentClassification(Enum):
    """Enumeration of user intents"""
    GREETING = "greeting"
    QUESTION = "question"
    COMMAND = "command"
    REQUEST = "request"
    COMPLAINT = "complaint"
    COMPLIMENT = "compliment"
    GOODBYE = "goodbye"
    HELP = "help"

class ResponseType(Enum):
    """Enumeration of response types"""
    INFORMATIONAL = "informational"
    CONFIRMATIONAL = "confirmational"
    INSTRUCTIONAL = "instructional"
    ERROR = "error"
    SUCCESS = "success"
    WARNING = "warning"

class AdvancedChatbotService:
    """Advanced chatbot service with multi-contextual support"""
    
    # Constants
    COLLECTION_NAME = "advanced_chat_histories"
    MAX_CONTEXT_LENGTH = 50  # Maximum number of conversation turns to keep
    OPENAI_MODEL = "gpt-4o"
    
    def __init__(self):
        """Initialize the advanced chatbot service"""
        # Remove deprecated LangChain LLM initialization
        # We'll use OpenAI client directly instead
        
        # Initialize specialized tools and agents
        self._initialize_tools()
        self._initialize_context_managers()
    
    def _initialize_tools(self):
        """Initialize specialized tools for different contexts"""
        self.database_tools = self._create_database_tools()
        self.analytics_tools = self._create_analytics_tools()
        self.management_tools = self._create_management_tools()
    
    def _initialize_context_managers(self):
        """Initialize context-specific managers"""
        self.context_managers = {
            ConversationContext.DATABASE_QUERY: DatabaseQueryManager(),
            ConversationContext.ANALYTICS: AnalyticsManager(),
            ConversationContext.JOB_MANAGEMENT: JobManagementManager(),
            ConversationContext.CANDIDATE_MANAGEMENT: CandidateManagementManager(),
            ConversationContext.INTERVIEW_PROCESS: InterviewProcessManager(),
            ConversationContext.OUT_OF_CONTEXT: OutOfContextManager(),
            ConversationContext.SMALL_TALK: SmallTalkManager(),
            ConversationContext.UNKNOWN: FallbackManager(),
        }
    
    @staticmethod
    def generate_response(
        message: str,
        conversation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate an advanced response with multi-contextual support
        
        Args:
            message: User's message
            conversation_id: Optional conversation ID
            context: Optional additional context
            
        Returns:
            Comprehensive response dictionary
        """
        try:
            # Initialize conversation ID if not provided
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
            
            # Create service instance
            service = AdvancedChatbotService()
            
            # Load conversation history
            conversation_history = service._load_conversation_history(conversation_id)
            
            # Analyze the message for intent and context
            analysis = service._analyze_message(message, conversation_history)
            
            # Determine the appropriate response strategy
            response_strategy = service._determine_response_strategy(analysis)
            
            # Generate response based on strategy
            response = service._generate_contextual_response(
                message, analysis, response_strategy, conversation_history, context
            )
            
            # Update conversation history
            service._update_conversation_history(
                conversation_id, message, response, analysis
            )
            
            return {
                "response": response["content"],
                "conversation_id": conversation_id,
                "context": analysis["context"],
                "intent": analysis["intent"],
                "confidence": analysis["confidence"],
                "response_type": response["type"],
                "executed_actions": response.get("actions", []),
                "suggestions": response.get("suggestions", []),
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "model_used": service.OPENAI_MODEL,
                    "processing_time": response.get("processing_time", 0)
                }
            }
            
        except Exception as e:
            logger.error(f"Error in advanced chatbot service: {str(e)}")
            return {
                "response": "I apologize, but I encountered an error while processing your request. Please try again or contact support if the issue persists.",
                "conversation_id": conversation_id or str(uuid.uuid4()),
                "context": ConversationContext.GENERAL.value,
                "intent": IntentClassification.QUESTION.value,
                "confidence": 0.0,
                "response_type": ResponseType.ERROR.value,
                "executed_actions": [],
                "suggestions": ["Try rephrasing your question", "Contact support"],
                "error": str(e)
            }
    
    def _load_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Load conversation history from database"""
        try:
            doc = FirestoreDB.get_document(self.COLLECTION_NAME, conversation_id)
            if doc and "history" in doc:
                return doc["history"][-self.MAX_CONTEXT_LENGTH:]  # Keep only recent history
            return []
        except Exception as e:
            logger.warning(f"Could not load conversation history: {str(e)}")
            return []
    
    def _analyze_message(self, message: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze message for intent, context, and entities"""
        try:
            # Create analysis prompt
            analysis_prompt = self._create_analysis_prompt(message, history)
            
            # Get analysis from OpenAI
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=self.OPENAI_MODEL,
                messages=[{"role": "system", "content": analysis_prompt}],
                temperature=0.1
            )
            
            # Parse the analysis result
            analysis_text = response.choices[0].message.content
            analysis = self._parse_analysis_result(analysis_text)
            
            # Extract additional entities and keywords
            analysis["entities"] = self._extract_entities(message)
            analysis["keywords"] = self._extract_keywords(message)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing message: {str(e)}")
            return {
                "context": ConversationContext.GENERAL.value,
                "intent": IntentClassification.QUESTION.value,
                "confidence": 0.5,
                "entities": {},
                "keywords": []
            }
    
    def _create_analysis_prompt(self, message: str, history: List[Dict[str, Any]]) -> str:
        """Create prompt for message analysis"""
        history_context = ""
        if history:
            recent_messages = history[-5:]  # Last 5 exchanges
            history_context = "\n".join([
                f"User: {msg.get('user', '')}\nAssistant: {msg.get('assistant', '')}" 
                for msg in recent_messages
            ])
        
        return f"""
        Analyze the following user message in the context of an interview management system.
        
        CONVERSATION HISTORY:
        {history_context}
        
        CURRENT MESSAGE: "{message}"
        
        Analyze and return a JSON object with:
        {{
            "context": "one of: general, job_management, candidate_management, interview_process, database_query, analytics, scheduling, technical_support",
            "intent": "one of: greeting, question, command, request, complaint, compliment, goodbye, help",
            "confidence": "confidence score 0.0-1.0",
            "primary_topic": "main topic of the message",
            "requires_database": "true/false if database access is needed",
            "requires_agent": "true/false if specialized agent is needed",
            "urgency_level": "low/medium/high"
        }}
        
        Consider:
        - Job-related keywords: create, add, post, hire, position, role
        - Candidate keywords: candidate, applicant, resume, shortlist, interview
        - Database keywords: search, find, filter, sort, list, show, get
        - Analytics keywords: statistics, metrics, performance, analysis, report
        """
    
    def _parse_analysis_result(self, analysis_text: str) -> Dict[str, Any]:
        """Parse the analysis result from OpenAI"""
        try:
            # Extract JSON from the response
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```|({[\s\S]*?})', analysis_text)
            if json_match:
                json_content = json_match.group(1) or json_match.group(2)
                return json.loads(json_content)
            else:
                return json.loads(analysis_text)
        except Exception as e:
            logger.error(f"Error parsing analysis result: {str(e)}")
            return {
                "context": ConversationContext.GENERAL.value,
                "intent": IntentClassification.QUESTION.value,
                "confidence": 0.5,
                "primary_topic": "unknown",
                "requires_database": False,
                "requires_agent": False,
                "urgency_level": "medium"
            }
    
    def _extract_entities(self, message: str) -> Dict[str, List[str]]:
        """Extract entities from the message"""
        entities = {
            "job_ids": [],
            "candidate_names": [],
            "emails": [],
            "dates": [],
            "numbers": [],
            "job_roles": []
        }
        
        # Extract emails
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        entities["emails"] = re.findall(email_pattern, message)
        
        # Extract job IDs (assuming format like job_123 or similar)
        job_id_pattern = r'\b(?:job[_-]?)([a-zA-Z0-9-]+)\b'
        entities["job_ids"] = re.findall(job_id_pattern, message, re.IGNORECASE)
        
        # Extract dates
        date_pattern = r'\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{4}\b'
        entities["dates"] = re.findall(date_pattern, message)
        
        # Extract numbers
        number_pattern = r'\b\d+\b'
        entities["numbers"] = re.findall(number_pattern, message)
        
        return entities
    
    def _extract_keywords(self, message: str) -> List[str]:
        """Extract relevant keywords from the message"""
        # Define keyword categories
        keyword_categories = {
            "job_management": ["job", "position", "role", "hire", "opening", "post"],
            "candidate_management": ["candidate", "applicant", "resume", "cv", "application"],
            "interview_process": ["interview", "schedule", "shortlist", "select", "feedback"],
            "database_operations": ["search", "find", "filter", "sort", "list", "show", "get"],
            "analytics": ["statistics", "metrics", "performance", "analysis", "report", "data"]
        }
        
        found_keywords = []
        message_lower = message.lower()
        
        for category, keywords in keyword_categories.items():
            for keyword in keywords:
                if keyword in message_lower:
                    found_keywords.append(keyword)
        
        return found_keywords
    
    def _determine_response_strategy(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Determine the appropriate response strategy based on analysis"""
        context = analysis.get("context", ConversationContext.GENERAL.value)
        intent = analysis.get("intent", IntentClassification.QUESTION.value)
        requires_database = analysis.get("requires_database", False)
        requires_agent = analysis.get("requires_agent", False)
        
        strategy = {
            "primary_approach": "conversational",
            "use_database": requires_database,
            "use_agent": requires_agent,
            "context_manager": context,
            "response_style": "professional",
            "include_suggestions": True
        }
        
        # Determine specific strategy based on context and intent
        if context == ConversationContext.DATABASE_QUERY.value:
            strategy["primary_approach"] = "database_query"
            strategy["use_database"] = True
        elif context == ConversationContext.INTERVIEW_PROCESS.value and requires_agent:
            strategy["primary_approach"] = "agent_execution"
            strategy["use_agent"] = True
        elif intent == IntentClassification.GREETING.value:
            strategy["primary_approach"] = "greeting"
            strategy["response_style"] = "friendly"
        elif intent == IntentClassification.HELP.value:
            strategy["primary_approach"] = "help"
            strategy["include_suggestions"] = True
        
        return strategy
    
    def _generate_contextual_response(
        self,
        message: str,
        analysis: Dict[str, Any],
        strategy: Dict[str, Any],
        history: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate a contextual response based on the strategy"""
        start_time = datetime.now()
        
        try:
            # Route to appropriate handler based on strategy
            if strategy["primary_approach"] == "database_query":
                response = self._handle_database_query(message, analysis, context)
            elif strategy["primary_approach"] == "agent_execution":
                response = self._handle_agent_execution(message, analysis, context)
            elif strategy["primary_approach"] == "greeting":
                response = self._handle_greeting(message, analysis)
            elif strategy["primary_approach"] == "help":
                response = self._handle_help_request(message, analysis)
            else:
                response = self._handle_conversational(message, analysis, history, context)
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            response["processing_time"] = processing_time
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating contextual response: {str(e)}")
            return {
                "content": "I apologize, but I encountered an error while processing your request. Please try again.",
                "type": ResponseType.ERROR.value,
                "actions": [],
                "suggestions": ["Try rephrasing your question", "Contact support"],
                "processing_time": (datetime.now() - start_time).total_seconds()
            }
    
    def _handle_database_query(self, message: str, analysis: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Handle database query requests"""
        try:
            # Use the DatabaseQueryManager
            manager = self.context_managers[ConversationContext.DATABASE_QUERY]
            result = manager.process_query(message, analysis, context)
            
            return {
                "content": result["response"],
                "type": ResponseType.INFORMATIONAL.value,
                "actions": result.get("actions", []),
                "suggestions": result.get("suggestions", []),
                "data": result.get("data", {})
            }
            
        except Exception as e:
            logger.error(f"Error handling database query: {str(e)}")
            return {
                "content": "I encountered an error while accessing the database. Please try again with a more specific query.",
                "type": ResponseType.ERROR.value,
                "actions": [],
                "suggestions": ["Try being more specific", "Check if the data exists"]
            }
    
    def _handle_agent_execution(self, message: str, analysis: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Handle specialized agent execution"""
        try:
            # Determine which agent to use
            agent_type = self._determine_agent_type(message, analysis)
            
            if agent_type == "shortlisting":
                result = self._execute_shortlisting_agent(message, analysis)
            elif agent_type == "scheduling":
                result = self._execute_scheduling_agent(message, analysis)
            elif agent_type == "end_to_end":
                result = self._execute_end_to_end_agent(message, analysis)
            elif agent_type == "job_management":
                result = self._execute_job_management_agent(message, analysis)
            else:
                result = {"response": "I'm not sure which specialized process you need. Could you be more specific?"}
            
            return {
                "content": result.get("response", "Agent execution completed."),
                "type": ResponseType.SUCCESS.value,
                "actions": [{"type": "agent_execution", "agent": agent_type, "result": result}],
                "suggestions": ["View the results", "Ask for more details"]
            }
            
        except Exception as e:
            logger.error(f"Error executing agent: {str(e)}")
            return {
                "content": "I encountered an error while executing the specialized process. Please try again.",
                "type": ResponseType.ERROR.value,
                "actions": [],
                "suggestions": ["Try again", "Check your parameters"]
            }
    
    def _handle_greeting(self, message: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Handle greeting messages"""
        greetings = [
            "Hello! I'm your AI assistant for interview management. How can I help you today?",
            "Hi there! I'm here to help you with jobs, candidates, interviews, and more. What would you like to do?",
            "Welcome! I can assist you with managing your hiring process. What can I help you with?"
        ]
        
        import random
        greeting = random.choice(greetings)
        
        return {
            "content": greeting,
            "type": ResponseType.INFORMATIONAL.value,
            "actions": [],
            "suggestions": [
                "Create a new job posting",
                "View candidate applications",
                "Schedule interviews",
                "Check interview statistics"
            ]
        }
    
    def _handle_help_request(self, message: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Handle help requests"""
        help_content = """
I can help you with various interview management tasks:

**Job Management:**
- Create new job postings
- View and edit existing jobs
- Search for specific positions

**Candidate Management:**
- Process resume applications
- View candidate profiles
- Filter candidates by criteria

**Interview Process:**
- Shortlist top candidates
- Schedule interview rounds
- Manage interview feedback
- Track interview progress

**Database Queries:**
- Search and filter data
- Generate reports and analytics
- Export information

**Available Commands:**
- "Create a job for [position]"
- "Show me candidates for [job]"
- "Shortlist candidates for [job]"
- "Schedule interviews for [job]"
- "Show interview statistics"

Just ask me naturally, and I'll understand what you need!
        """
        
        return {
            "content": help_content,
            "type": ResponseType.INSTRUCTIONAL.value,
            "actions": [],
            "suggestions": [
                "Try: 'Create a software engineer job'",
                "Try: 'Show me all candidates'",
                "Try: 'Schedule interviews for job_123'"
            ]
        }
    
    def _handle_conversational(self, message: str, analysis: Dict[str, Any], history: List[Dict[str, Any]], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Handle general conversational requests"""
        try:
            # Create a comprehensive system prompt
            system_prompt = self._create_conversational_prompt(analysis, context)
            
            # Build conversation context
            conversation_context = self._build_conversation_context(history, message)
            
            # Generate response using OpenAI
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=self.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": conversation_context}
                ],
                temperature=0.3
            )
            
            response_content = response.choices[0].message.content
            
            # Extract any actions that might be needed
            actions = self._extract_actions_from_response(response_content)
            
            return {
                "content": response_content,
                "type": ResponseType.INFORMATIONAL.value,
                "actions": actions,
                "suggestions": self._generate_contextual_suggestions(analysis)
            }
            
        except Exception as e:
            logger.error(f"Error in conversational handling: {str(e)}")
            return {
                "content": "I understand you're asking about our interview management system. Could you please be more specific about what you'd like to know or do?",
                "type": ResponseType.INFORMATIONAL.value,
                "actions": [],
                "suggestions": ["Be more specific", "Try asking about jobs or candidates"]
            }
    
    def _update_conversation_history(self, conversation_id: str, message: str, response: Dict[str, Any], analysis: Dict[str, Any]):
        """Update conversation history in database"""
        try:
            # Load existing history
            existing_history = self._load_conversation_history(conversation_id)
            
            # Add new exchange
            new_entry = {
                "timestamp": datetime.now().isoformat(),
                "user": message,
                "assistant": response["content"],
                "context": analysis.get("context"),
                "intent": analysis.get("intent"),
                "confidence": analysis.get("confidence")
            }
            
            existing_history.append(new_entry)
            
            # Keep only recent history
            if len(existing_history) > self.MAX_CONTEXT_LENGTH:
                existing_history = existing_history[-self.MAX_CONTEXT_LENGTH:]
            
            # Save to database
            doc_data = {
                "history": existing_history,
                "last_updated": datetime.now().isoformat(),
                "conversation_id": conversation_id
            }
            
            FirestoreDB.update_document(self.COLLECTION_NAME, conversation_id, doc_data)
            
        except Exception as e:
            logger.error(f"Error updating conversation history: {str(e)}")
    
    # Additional helper methods...
    def _create_database_tools(self) -> List[Any]:
        """Create database query tools"""
        # Implementation for database tools
        return []
    
    def _create_analytics_tools(self) -> List[Any]:
        """Create analytics tools"""
        # Implementation for analytics tools
        return []
    
    def _create_management_tools(self) -> List[Any]:
        """Create management tools"""
        # Implementation for management tools
        return []
    
    def _determine_agent_type(self, message: str, analysis: Dict[str, Any]) -> str:
        """Determine which agent type to use"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["shortlist", "select", "choose", "best"]):
            return "shortlisting"
        elif any(word in message_lower for word in ["schedule", "book", "calendar", "time"]):
            return "scheduling"
        elif any(word in message_lower for word in ["end to end", "complete", "full process"]):
            return "end_to_end"
        elif any(word in message_lower for word in ["create job", "new job", "add job"]):
            return "job_management"
        else:
            return "unknown"
    
    def _execute_shortlisting_agent(self, message: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Execute shortlisting agent"""
        # Extract parameters from message
        job_role = self._extract_job_role_from_message(message)
        num_candidates = self._extract_number_from_message(message, default=3)
        
        if not job_role:
            return {"response": "Please specify which job role you want to shortlist candidates for."}
        
        try:
            result = run_shortlisting_process(job_role, num_candidates)
            return {"response": f"Shortlisting completed for {job_role}. {result}"}
        except Exception as e:
            return {"response": f"Error in shortlisting process: {str(e)}"}
    
    def _execute_scheduling_agent(self, message: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Execute scheduling agent"""
        job_role = self._extract_job_role_from_message(message)
        interview_date = self._extract_date_from_message(message)
        num_rounds = self._extract_number_from_message(message, default=2)
        
        if not job_role:
            return {"response": "Please specify which job role you want to schedule interviews for."}
        
        try:
            result = run_scheduling_process(job_role, interview_date, num_rounds)
            return {"response": f"Scheduling completed for {job_role}. {result}"}
        except Exception as e:
            return {"response": f"Error in scheduling process: {str(e)}"}
    
    def _execute_end_to_end_agent(self, message: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Execute end-to-end agent"""
        job_role = self._extract_job_role_from_message(message)
        num_candidates = self._extract_number_from_message(message, default=3)
        interview_date = self._extract_date_from_message(message)
        num_rounds = self._extract_number_from_message(message, default=2, context="rounds")
        
        if not job_role:
            return {"response": "Please specify which job role you want to run the end-to-end process for."}
        
        try:
            result = run_end_to_end_process(job_role, num_candidates, interview_date, num_rounds)
            return {"response": f"End-to-end process completed for {job_role}. {result}"}
        except Exception as e:
            return {"response": f"Error in end-to-end process: {str(e)}"}
    
    def _execute_job_management_agent(self, message: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Execute job management agent"""
        try:
            # Extract job details from message using OpenAI
            job_details = self._extract_job_details_from_message(message)
            result = run_job_creation_process(job_details)
            return {"response": f"Job creation completed. {result}"}
        except Exception as e:
            return {"response": f"Error in job creation process: {str(e)}"}
    
    # Utility methods for parameter extraction
    def _extract_job_role_from_message(self, message: str) -> Optional[str]:
        """Extract job role from message"""
        # Use regex patterns to find job roles
        patterns = [
            r'(?:job role|position|role)\s+["\']([^"\']+)["\']',
            r'(?:for|role)\s+([a-zA-Z\s]+?)(?:\s+(?:job|position|role)|$)',
            r'([a-zA-Z\s]+?)\s+(?:job|position|role)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_number_from_message(self, message: str, default: int = 0, context: str = "") -> int:
        """Extract number from message"""
        if context:
            pattern = f'(\\d+)\\s+{context}'
        else:
            pattern = r'(\d+)'
        
        match = re.search(pattern, message)
        if match:
            return int(match.group(1))
        return default
    
    def _extract_date_from_message(self, message: str) -> Optional[str]:
        """Extract date from message"""
        date_patterns = [
            r'\b(\d{4}-\d{2}-\d{2})\b',
            r'\b(\d{1,2}/\d{1,2}/\d{4})\b',
            r'\b(tomorrow)\b',
            r'\b(today)\b'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                date_str = match.group(1).lower()
                if date_str == "tomorrow":
                    return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
                elif date_str == "today":
                    return datetime.now().strftime("%Y-%m-%d")
                else:
                    return date_str
        
        return None
    
    def _extract_job_details_from_message(self, message: str) -> Dict[str, Any]:
        """Extract job details from message using OpenAI"""
        try:
            prompt = f"""
            Extract job details from this message: "{message}"
            
            Return a JSON object with:
            {{
                "job_role_name": "extracted job title",
                "job_description": "extracted or inferred job description",
                "years_of_experience_needed": "extracted experience requirement",
                "location": "extracted location or 'Remote'",
                "status": "open"
            }}
            """
            
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=self.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            result_text = response.choices[0].message.content
            
            # Parse JSON from response
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```|({[\s\S]*?})', result_text)
            if json_match:
                json_content = json_match.group(1) or json_match.group(2)
                return json.loads(json_content)
            else:
                return json.loads(result_text)
                
        except Exception as e:
            logger.error(f"Error extracting job details: {str(e)}")
            return {
                "job_role_name": "Software Engineer",
                "job_description": "Job posting created from user input",
                "years_of_experience_needed": "2-5 years",
                "location": "Remote",
                "status": "open"
            }
    
    def _create_conversational_prompt(self, analysis: Dict[str, Any], context: Optional[Dict[str, Any]]) -> str:
        """Create system prompt for conversational responses"""
        return f"""
        You are a professional AI assistant for an interview management system.
        
        Context: {analysis.get('context', 'general')}
        Primary Topic: {analysis.get('primary_topic', 'unknown')}
        
        Guidelines:
        - Provide concise, professional responses
        - Focus on interview management topics
        - Offer helpful suggestions when appropriate
        - Be clear about what actions you can perform
        
        Available capabilities:
        - Job management (create, view, search)
        - Candidate management (process, filter, view)
        - Interview scheduling and shortlisting
        - Database queries and analytics
        
        Respond in a helpful, professional manner.
        """
    
    def _build_conversation_context(self, history: List[Dict[str, Any]], current_message: str) -> str:
        """Build conversation context from history"""
        context = f"Current message: {current_message}\n\n"
        
        if history:
            context += "Recent conversation:\n"
            for msg in history[-3:]:  # Last 3 exchanges
                context += f"User: {msg.get('user', '')}\n"
                context += f"Assistant: {msg.get('assistant', '')}\n"
        
        return context
    
    def _extract_actions_from_response(self, response_content: str) -> List[Dict[str, Any]]:
        """Extract any actions that might be needed from the response"""
        actions = []
        
        # Look for patterns that suggest actions
        if "create" in response_content.lower() and "job" in response_content.lower():
            actions.append({"type": "job_creation", "description": "Job creation suggested"})
        
        if "schedule" in response_content.lower() and "interview" in response_content.lower():
            actions.append({"type": "interview_scheduling", "description": "Interview scheduling suggested"})
        
        return actions
    
    def _generate_contextual_suggestions(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate contextual suggestions based on analysis"""
        context = analysis.get("context", "general")
        
        suggestions = {
            "job_management": [
                "Create a new job posting",
                "View existing jobs",
                "Search for specific positions"
            ],
            "candidate_management": [
                "View candidate profiles",
                "Filter candidates by criteria",
                "Process new applications"
            ],
            "interview_process": [
                "Shortlist top candidates",
                "Schedule interview rounds",
                "View interview feedback"
            ],
            "database_query": [
                "Search for specific data",
                "Generate reports",
                "Filter by criteria"
            ],
            "analytics": [
                "View performance metrics",
                "Generate analytics reports",
                "Track hiring progress"
            ]
        }
        
        return suggestions.get(context, [
            "Ask me about jobs or candidates",
            "Try being more specific",
            "Type 'help' for available commands"
        ])


# Context Manager Classes
class DatabaseQueryManager:
    """Manager for database query operations"""
    
    def process_query(self, message: str, analysis: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Process database query requests"""
        try:
            # Determine query type
            query_type = self._determine_query_type(message)
            
            if query_type == "jobs":
                return self._query_jobs(message)
            elif query_type == "candidates":
                return self._query_candidates(message)
            elif query_type == "interviews":
                return self._query_interviews(message)
            else:
                return self._general_query(message)
                
        except Exception as e:
            return {
                "response": f"Error processing database query: {str(e)}",
                "actions": [],
                "suggestions": ["Try a more specific query"]
            }
    
    def _determine_query_type(self, message: str) -> str:
        """Determine the type of database query"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["job", "position", "role"]):
            return "jobs"
        elif any(word in message_lower for word in ["candidate", "applicant"]):
            return "candidates"
        elif any(word in message_lower for word in ["interview", "schedule"]):
            return "interviews"
        else:
            return "general"
    
    def _query_jobs(self, message: str) -> Dict[str, Any]:
        """Query jobs collection"""
        try:
            jobs = JobService.get_all_job_postings()
            
            response = f"Found {len(jobs)} job postings:\n\n"
            for job in jobs[:5]:  # Limit to first 5
                response += f"• {job.job_role_name} - {job.location}\n"
            
            if len(jobs) > 5:
                response += f"... and {len(jobs) - 5} more jobs"
            
            return {
                "response": response,
                "data": {"jobs": [job.__dict__ if hasattr(job, '__dict__') else job for job in jobs]},
                "actions": [{"type": "jobs_query", "count": len(jobs)}],
                "suggestions": ["View specific job details", "Create a new job"]
            }
            
        except Exception as e:
            return {
                "response": f"Error querying jobs: {str(e)}",
                "actions": [],
                "suggestions": ["Try again"]
            }
    
    def _query_candidates(self, message: str) -> Dict[str, Any]:
        """Query candidates collection"""
        try:
            candidates = CandidateService.get_all_candidates()
            
            response = f"Found {len(candidates)} candidates in the system:\n\n"
            for candidate in candidates[:5]:  # Limit to first 5
                response += f"• {candidate.name} - {candidate.email}\n"
            
            if len(candidates) > 5:
                response += f"... and {len(candidates) - 5} more candidates"
            
            return {
                "response": response,
                "data": {"candidates": [candidate.__dict__ if hasattr(candidate, '__dict__') else candidate for candidate in candidates]},
                "actions": [{"type": "candidates_query", "count": len(candidates)}],
                "suggestions": ["View candidate details", "Process resumes"]
            }
            
        except Exception as e:
            return {
                "response": f"Error querying candidates: {str(e)}",
                "actions": [],
                "suggestions": ["Try again"]
            }
    
    def _query_interviews(self, message: str) -> Dict[str, Any]:
        """Query interviews collection"""
        try:
            # This would need to be implemented based on your interview service
            response = "Interview query functionality is available. Please specify what interview information you need."
            
            return {
                "response": response,
                "data": {},
                "actions": [{"type": "interviews_query"}],
                "suggestions": ["Ask for specific interview details", "Check interview schedules"]
            }
            
        except Exception as e:
            return {
                "response": f"Error querying interviews: {str(e)}",
                "actions": [],
                "suggestions": ["Try again"]
            }
    
    def _general_query(self, message: str) -> Dict[str, Any]:
        """Handle general database queries"""
        return {
            "response": "I can help you query the database. Please specify what you're looking for: jobs, candidates, or interviews.",
            "actions": [],
            "suggestions": ["Ask about jobs", "Ask about candidates", "Ask about interviews"]
        }


class AnalyticsManager:
    """Manager for analytics operations"""
    
    def process_query(self, message: str, analysis: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Process analytics requests"""
        return {
            "response": "Analytics functionality is available. I can provide reports on hiring metrics, candidate performance, and interview statistics.",
            "actions": [{"type": "analytics_request"}],
            "suggestions": ["Request specific metrics", "Ask for hiring reports"]
        }


class JobManagementManager:
    """Manager for job management operations"""
    
    def process_query(self, message: str, analysis: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Process job management requests"""
        return {
            "response": "I can help you with job management tasks including creating, viewing, and editing job postings.",
            "actions": [{"type": "job_management"}],
            "suggestions": ["Create a new job", "View existing jobs", "Edit job details"]
        }


class CandidateManagementManager:
    """Manager for candidate management operations"""
    
    def process_query(self, message: str, analysis: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Process candidate management requests"""
        return {
            "response": "I can help you manage candidates including viewing profiles, processing applications, and filtering candidates.",
            "actions": [{"type": "candidate_management"}],
            "suggestions": ["View candidates", "Process applications", "Filter by criteria"]
        }


class InterviewProcessManager:
    """Manager for interview process operations"""
    
    def process_query(self, message: str, analysis: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Process interview management requests"""
        return {
            "response": "I can help you with interview processes including shortlisting candidates, scheduling interviews, and tracking progress.",
            "actions": [{"type": "interview_management"}],
            "suggestions": ["Shortlist candidates", "Schedule interviews", "View interview status"]
        }


class OutOfContextManager:
    """Manager for out-of-context questions"""
    
    def process_query(self, message: str, analysis: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Process out-of-context questions"""
        return {
            "response": "I understand you're asking about something outside of our interview management system. While I'm specialized in helping with jobs, candidates, and interviews, I can try to provide general assistance. However, I work best when helping with hiring-related tasks.",
            "actions": [{"type": "out_of_context_handling"}],
            "suggestions": [
                "Ask about job management",
                "Ask about candidate processes", 
                "Ask about interview scheduling",
                "Type 'help' for available commands"
            ]
        }


class SmallTalkManager:
    """Manager for small talk and casual conversation"""
    
    def process_query(self, message: str, analysis: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Process small talk and casual conversation"""
        
        # Generate appropriate small talk responses
        responses = {
            "how are you": "I'm doing well, thank you! I'm here and ready to help you with your interview management needs. How can I assist you today?",
            "what's your name": "I'm your AI assistant for interview management. You can think of me as your hiring process companion. What would you like to work on?",
            "tell me about yourself": "I'm an AI assistant specialized in helping with interview management tasks. I can help you create jobs, manage candidates, schedule interviews, and much more. What brings you here today?",
            "good morning": "Good morning! I hope you're having a great day. I'm here to help you with any hiring or interview management tasks. What can I do for you?",
            "good afternoon": "Good afternoon! I'm ready to assist you with your interview management needs. Whether it's jobs, candidates, or scheduling, I'm here to help.",
            "thank you": "You're very welcome! I'm always happy to help with your hiring processes. Is there anything else you'd like to work on?",
            "weather": "While I don't have access to weather information, I can definitely help you with your interview management tasks! Perhaps we could schedule some interviews for a nice day?",
            "default": "I appreciate the friendly conversation! While I enjoy chatting, I'm most helpful when assisting with interview management tasks. How can I help you with jobs, candidates, or interviews today?"
        }
        
        message_lower = message.lower()
        response_text = responses.get("default", responses["default"])
        
        # Check for specific small talk patterns
        for pattern, response in responses.items():
            if pattern in message_lower:
                response_text = response
                break
        
        return {
            "response": response_text,
            "actions": [{"type": "small_talk"}],
            "suggestions": [
                "Create a job posting",
                "View candidates",
                "Schedule interviews",
                "Get help with the system"
            ]
        }


class FallbackManager:
    """Fallback manager for unknown or unclear queries"""
    
    def process_query(self, message: str, analysis: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Process unknown or unclear queries"""
        
        # Try to provide helpful fallback responses
        clarification_responses = [
            "I want to make sure I understand what you need. Could you provide more details about what you'd like to do?",
            "I'm not entirely sure what you're looking for. Are you trying to work with jobs, candidates, or interviews?",
            "Let me help you more effectively. Could you be more specific about what you need assistance with?",
            "I'd love to help! Could you clarify whether you want to create something, view information, or perform a specific task?"
        ]
        
        import random
        response_text = random.choice(clarification_responses)
        
        return {
            "response": response_text + "\n\nHere are some things I can help you with:\n• Create and manage job postings\n• Process and view candidate applications\n• Schedule and manage interviews\n• Search and analyze hiring data\n• Generate reports and analytics",
            "actions": [{"type": "fallback_handling"}],
            "suggestions": [
                "Tell me: 'Create a job for [position]'",
                "Ask: 'Show me all candidates'",
                "Try: 'Schedule interviews for [job]'",
                "Type: 'help' for more options"
            ]
        }
