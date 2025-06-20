"""
API routes for chatbot interactions - optimized for direct API execution
"""
from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any, Optional
import uuid
import logging
import json
from firebase_admin import firestore

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("api_debug.log")
    ]
)
logger = logging.getLogger("chatbot_api")

from app.schemas.chatbot_schema import ChatRequest, ChatResponse
from app.services.chatbot_service import ChatbotService
from app.services.chatbot_service_enhanced import ChatbotServiceEnhanced
from app.database.firebase_db import FirestoreDB


router = APIRouter(
    prefix="/chat",
    tags=["chatbot"],
    responses={404: {"description": "Not found"}},
)


@router.post("/execute")
async def execute_query(request: dict):
    """
    Process a natural language query and execute the appropriate API action
    
    This streamlined endpoint:
    1. Takes a natural language query as input
    2. Determines which API endpoint should handle the request
    3. Extracts parameters from the query
    4. Executes the API call directly
    5. Returns both the LLM's response and the API call result
    
    The system can handle natural language queries about:
    - Job postings (create, get, list)
    - Candidates (process resumes, get candidates for job)
    - Interviews (scheduling, feedback, shortlisting)
    - Can directly connect to specialized agents for complex tasks
    
    This endpoint is optimized for performance and direct API execution.
    """
    logger.info("=" * 60)
    logger.info("[API] Received execute_query request")
    if isinstance(request, dict):
        logger.info(f"[API] Request keys: {list(request.keys())}")
        if "payload" in request:
            logger.info(f"[API] Payload keys: {list(request['payload'].keys()) if isinstance(request['payload'], dict) else 'Not a dict'}")
    
    try:
        # Handle nested payload structure if present
        payload = request
        if isinstance(request, dict) and "payload" in request:
            payload = request["payload"]
        
        # Extract message, sessionId, and user_role from the payload
        if not isinstance(payload, dict):
            # If payload is not a dict (might be a Pydantic model), convert to dict
            payload_dict = payload.dict() if hasattr(payload, "dict") else payload
        else:
            payload_dict = payload
        
        # Get required fields
        message = payload_dict.get("message", "")
        if not message:
            raise HTTPException(status_code=400, detail="No message provided in request")
            
        # Initialize session or get existing session
        sessionId = payload_dict.get("sessionId") or str(uuid.uuid4())
        
        # Get user role (default to HR if not provided)
        user_role = payload_dict.get("user_role", "HR")
        logger.info(f"[API] User role: {user_role}")
        
        # Validate role
        valid_roles = ["HR", "Recruiter", "Interviewer"]
        if user_role not in valid_roles:
            logger.warning(f"[API] Invalid role '{user_role}', defaulting to HR")
            user_role = "HR"  # Default to HR for unrecognized roles
        
        # Get chat history if sessionId exists
        chat_history = []
        if sessionId:
            try:
                # Fetch chat history from Firebase
                chat_doc = FirestoreDB.get_document("chats", sessionId)
                if chat_doc and "history" in chat_doc:
                    chat_history = chat_doc["history"]
                    logger.info(f"[API] Retrieved chat history: {len(chat_history)} messages")
            except Exception as history_error:
                logger.error(f"[API] Error fetching chat history: {history_error}")
        
        # Use the enhanced chatbot service which connects directly to specialized agents
        try:
            response = ChatbotServiceEnhanced.generate_response(
                message=message,
                conversation_id=sessionId,
                context={"chat_history": chat_history}
            )
        except Exception as enhanced_error:
            print(f"Enhanced chatbot service failed: {enhanced_error}. Falling back to standard service.")
            # Fall back to original service if enhanced version fails
            try:
            logger.info(f"[API] Calling ChatbotService with message: '{message}' and role: '{user_role}'")
            
            response = ChatbotService.generate_response(
                    message=message,
                    conversation_id=sessionId,
                    context={"chat_history": chat_history},
                    user_role=user_role
            )
            
            logger.info("[API] Got response from ChatbotService")
            
            # Check if there was a permission denial in the executed action
            executed_action = response.get("executed_action", {})
            if isinstance(executed_action, dict):
                logger.info(f"[API] Executed action: {executed_action.get('path', 'unknown')} ({executed_action.get('method', 'unknown')})")
                logger.info(f"[API] Action status: {executed_action.get('status', 'unknown')}")
                
                if executed_action.get("status") == "permission_denied":
                    logger.warning(f"[API] Permission denied: {executed_action.get('error')}")
                    # Return a 403 Forbidden status with the error message
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=executed_action.get("error", "Permission denied based on user role")
                    )
        except HTTPException:
            # Re-raise HTTP exceptions to be handled properly
            logger.error("[API] HTTP Exception caught, re-raising")
            raise
        except Exception as e:
            # Handle other exceptions
            logger.error(f"[API] Unexpected error in ChatbotService.generate_response: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error generating response: {str(e)}")
        
        # Store chat history
        try:
            # Update history with new message and response
            chat_history.append({"role": "user", "content": message})
            chat_history.append({"role": "assistant", "content": response["response"]})
            
            # Save to Firebase
            FirestoreDB.update_document(
                "chats", 
                sessionId, 
                {
                    "history": chat_history,
                    "last_updated": firestore.SERVER_TIMESTAMP,
                    "last_message": message
                }
            )
            logger.info(f"[API] Updated chat history for session {sessionId}")
        except Exception as save_error:
            logger.error(f"[API] Error saving chat history: {save_error}")
        
        # Construct a more concise response
        result = None
        action_result = response.get("action_result")
        
        if action_result:
            # Format action results in a more user-friendly way
            if isinstance(action_result, dict) and "result" in action_result:
                result = action_result
            else:
                result = {"result": action_result}
            logger.info(f"[API] Action result preview: {str(result)[:100]}...")
        
        # Log the full response before returning
        logger.info(f"[API] Returning response with message length: {len(response.get('response', ''))}")
        logger.info(f"[API] Response contains result data: {result is not None}")
        logger.info(f"[API] Response user_role: {user_role}")
        
        final_response = {
            "message": response.get("response", ""),
            "sessionId": sessionId,
            "success": True,
            "user_role": user_role,
            "result": result
        }
        
        # Log a preview of what the UI will receive
        logger.info(f"[API] Final response to UI (preview): {str(final_response)[:200]}...")
        
        return final_response
        
    except HTTPException as http_ex:
        # Log the HTTP exception and re-raise
        logger.error(f"[API] HTTP Exception: {http_ex.status_code} - {http_ex.detail}")
        raise
        
    except Exception as e:
        # Log any other exceptions and return as 500
        logger.error(f"[API] Unhandled exception: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing request: {str(e)}"
        )
