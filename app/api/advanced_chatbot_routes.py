"""
Advanced Multi-Contextual Chatbot API Routes

This module provides enhanced chatbot endpoints with:
- Multi-contextual conversation support
- Professional response handling
- Database querying capabilities
- NLP processing for various scenarios
- Specialized agent integration
- Error handling and fallback mechanisms
"""

from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from typing import Dict, Any, Optional, List
import uuid
import json
import logging
from datetime import datetime
from firebase_admin import firestore

from app.schemas.chatbot_schema import ChatRequest, ChatResponse
from app.services.advanced_chatbot_service import AdvancedChatbotService
from app.services.chatbot_service_enhanced import ChatbotServiceEnhanced
from app.database.chroma_db import FirestoreDB, ChromaVectorDB

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat/advanced",
    tags=["advanced-chatbot"],
    responses={404: {"description": "Not found"}},
)


@router.post("/query")
async def process_advanced_query(request: dict):
    """
    Process a natural language query using the advanced multi-contextual chatbot
    
    This endpoint provides:
    - Intent and context analysis
    - Multi-turn conversation support
    - Specialized agent integration
    - Database query capabilities
    - Professional response handling
    - Error recovery mechanisms
    
    Features:
    - Understands natural language commands
    - Maintains conversation context
    - Routes to appropriate specialized agents
    - Provides helpful suggestions
    - Handles complex multi-step processes
    """
    try:
        # Handle nested payload structure if present
        payload = request
        if isinstance(request, dict) and "payload" in request:
            payload = request["payload"]
        
        # Extract message and sessionId from the payload
        if not isinstance(payload, dict):
            payload_dict = payload.dict() if hasattr(payload, "dict") else payload
        else:
            payload_dict = payload
        
        # Get required fields
        message = payload_dict.get("message", "")
        if not message:
            raise HTTPException(status_code=400, detail="No message provided in request")
            
        # Initialize session or get existing session
        sessionId = payload_dict.get("sessionId") or str(uuid.uuid4())
        
        # Get additional context if provided
        context = payload_dict.get("context", {})
        
        # Process using the advanced chatbot service
        response = AdvancedChatbotService.generate_response(
            message=message,
            conversation_id=sessionId,
            context=context
        )
        
        # Return comprehensive response
        return {
            "message": response["response"],
            "sessionId": response["conversation_id"],
            "context": response["context"],
            "intent": response["intent"],
            "confidence": response["confidence"],
            "response_type": response["response_type"],
            "executed_actions": response["executed_actions"],
            "suggestions": response["suggestions"],
            "metadata": response["metadata"],
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Error in advanced chatbot query: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing advanced query: {str(e)}"
        )


@router.post("/conversation/start")
async def start_conversation():
    """
    Start a new conversation session
    
    Returns a new conversation ID and initial greeting
    """
    try:
        conversation_id = str(uuid.uuid4())
        
        # Generate initial greeting
        response = AdvancedChatbotService.generate_response(
            message="Hello",
            conversation_id=conversation_id
        )
        
        return {
            "conversation_id": conversation_id,
            "message": response["response"],
            "context": response["context"],
            "suggestions": response["suggestions"],
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Error starting conversation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting conversation: {str(e)}"
        )


@router.get("/conversation/{conversation_id}/history")
async def get_conversation_history(conversation_id: str):
    """
    Get conversation history for a specific session
    
    Args:
        conversation_id: The conversation session ID
        
    Returns:
        Conversation history and metadata
    """
    try:
        # Get conversation history from database
        doc = FirestoreDB.get_document("advanced_chat_histories", conversation_id)
        
        if not doc:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return {
            "conversation_id": conversation_id,
            "history": doc.get("history", []),
            "last_updated": doc.get("last_updated"),
            "total_messages": len(doc.get("history", [])),
            "success": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving conversation history: {str(e)}"
        )


@router.delete("/conversation/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """
    Delete a conversation and its history
    
    Args:
        conversation_id: The conversation session ID to delete
    """
    try:
        # Delete from database
        FirestoreDB.delete_document("advanced_chat_histories", conversation_id)
        
        return {
            "message": "Conversation deleted successfully",
            "conversation_id": conversation_id,
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Error deleting conversation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting conversation: {str(e)}"
        )


@router.post("/analyze")
async def analyze_message(request: dict):
    """
    Analyze a message for intent, context, and entities without generating a full response
    
    Useful for:
    - Understanding user intent
    - Extracting entities from text
    - Context classification
    - Confidence scoring
    """
    try:
        message = request.get("message", "")
        if not message:
            raise HTTPException(status_code=400, detail="No message provided")
        
        # Create a temporary service instance to analyze the message
        service = AdvancedChatbotService()
        analysis = service._analyze_message(message, [])
        
        return {
            "message": message,
            "analysis": analysis,
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Error analyzing message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing message: {str(e)}"
        )


@router.post("/bulk-process")
async def bulk_process_messages(request: dict, background_tasks: BackgroundTasks):
    """
    Process multiple messages in bulk
    
    Useful for:
    - Processing chat logs
    - Batch analysis
    - Testing conversation flows
    """
    try:
        messages = request.get("messages", [])
        conversation_id = request.get("conversation_id") or str(uuid.uuid4())
        
        if not messages:
            raise HTTPException(status_code=400, detail="No messages provided")
        
        results = []
        
        for i, message in enumerate(messages):
            try:
                response = AdvancedChatbotService.generate_response(
                    message=message,
                    conversation_id=conversation_id
                )
                
                results.append({
                    "index": i,
                    "message": message,
                    "response": response["response"],
                    "context": response["context"],
                    "intent": response["intent"],
                    "confidence": response["confidence"]
                })
                
            except Exception as msg_error:
                results.append({
                    "index": i,
                    "message": message,
                    "error": str(msg_error)
                })
        
        return {
            "conversation_id": conversation_id,
            "processed_count": len(messages),
            "results": results,
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Error in bulk processing: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing bulk messages: {str(e)}"
        )


@router.get("/capabilities")
async def get_chatbot_capabilities():
    """
    Get information about chatbot capabilities and available commands
    
    Returns:
        Comprehensive list of capabilities, contexts, and example commands
    """
    try:
        capabilities = {
            "contexts": [
                {
                    "name": "general",
                    "description": "General conversation and help",
                    "examples": ["Hello", "Help me", "What can you do?"]
                },
                {
                    "name": "job_management",
                    "description": "Create, view, and manage job postings",
                    "examples": ["Create a software engineer job", "Show me all jobs", "Update job posting"]
                },
                {
                    "name": "candidate_management",
                    "description": "Manage candidate applications and profiles",
                    "examples": ["Show me candidates", "Process resumes", "Filter candidates by experience"]
                },
                {
                    "name": "interview_process",
                    "description": "Shortlist candidates and schedule interviews",
                    "examples": ["Shortlist candidates for developer role", "Schedule interviews", "End-to-end process"]
                },
                {
                    "name": "database_query",
                    "description": "Search and filter data from the system",
                    "examples": ["Find candidates with Python skills", "Show jobs in New York", "List recent interviews"]
                },
                {
                    "name": "analytics",
                    "description": "Generate reports and analytics",
                    "examples": ["Show hiring metrics", "Interview success rate", "Candidate performance"]
                }
            ],
            "specialized_agents": [
                {
                    "name": "shortlisting_agent",
                    "description": "Automatically shortlist top candidates based on AI fit scores",
                    "triggers": ["shortlist", "select best candidates", "choose top candidates"]
                },
                {
                    "name": "scheduling_agent",
                    "description": "Schedule interviews with calendar integration",
                    "triggers": ["schedule interviews", "book interviews", "set up meetings"]
                },
                {
                    "name": "end_to_end_agent",
                    "description": "Complete hiring process from shortlisting to scheduling",
                    "triggers": ["complete process", "end-to-end", "full hiring process"]
                },
                {
                    "name": "job_creation_agent",
                    "description": "Create comprehensive job postings with AI assistance",
                    "triggers": ["create job", "new position", "add job posting"]
                }
            ],
            "features": [
                "Multi-turn conversation memory",
                "Intent and context recognition",
                "Entity extraction (emails, dates, names)",
                "Professional response formatting",
                "Error handling and recovery",
                "Contextual suggestions",
                "Database integration",
                "Agent execution tracking"
            ],
            "response_types": [
                "informational",
                "confirmational", 
                "instructional",
                "error",
                "success",
                "warning"
            ]
        }
        
        return {
            "capabilities": capabilities,
            "version": "1.0.0",
            "model": "gpt-4o",
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Error getting capabilities: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving capabilities: {str(e)}"
        )


@router.post("/feedback")
async def submit_feedback(request: dict):
    """
    Submit feedback about chatbot responses
    
    Helps improve the chatbot by collecting user feedback
    """
    try:
        conversation_id = request.get("conversation_id")
        message_index = request.get("message_index")
        feedback_type = request.get("feedback_type")  # positive, negative, suggestion
        feedback_text = request.get("feedback_text", "")
        rating = request.get("rating")  # 1-5 scale
        
        feedback_data = {
            "conversation_id": conversation_id,
            "message_index": message_index,
            "feedback_type": feedback_type,
            "feedback_text": feedback_text,
            "rating": rating,
            "timestamp": datetime.now().isoformat(),
            "user_agent": request.get("user_agent", "")
        }
        
        # Store feedback in database
        feedback_id = str(uuid.uuid4())
        FirestoreDB.update_document("chatbot_feedback", feedback_id, feedback_data)
        
        return {
            "message": "Feedback submitted successfully",
            "feedback_id": feedback_id,
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Error submitting feedback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting feedback: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """
    Health check endpoint for the advanced chatbot service
    """
    try:
        # Test basic functionality
        test_response = AdvancedChatbotService.generate_response(
            message="health check",
            conversation_id="health_check_session"
        )
        
        return {
            "status": "healthy",
            "service": "advanced_chatbot",
            "timestamp": datetime.now().isoformat(),
            "test_response_generated": bool(test_response.get("response")),
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "service": "advanced_chatbot",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "success": False
        }
