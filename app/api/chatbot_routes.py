"""
API routes for chatbot interactions - optimized for direct API execution
"""
from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any, Optional
import uuid
from firebase_admin import firestore

from app.schemas.chatbot_schema import ChatRequest, ChatResponse
from app.services.chatbot_service import ChatbotService
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
    
    This endpoint is optimized for performance and direct API execution.
    """
    try:
        # Handle nested payload structure if present
        payload = request
        if isinstance(request, dict) and "payload" in request:
            payload = request["payload"]
        
        # Extract message and sessionId from the payload
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
        
        # Get chat history if sessionId exists
        chat_history = []
        if sessionId:
            try:
                # Fetch chat history from Firebase
                chat_doc = FirestoreDB.get_document("chats", sessionId)
                if chat_doc and "history" in chat_doc:
                    chat_history = chat_doc["history"]
            except Exception as history_error:
                print(f"Error fetching chat history: {history_error}")
        
        # Generate response and execute API action in one step
        response = ChatbotService.generate_response(
            message=message,
            conversation_id=sessionId,
            context={"chat_history": chat_history}
        )
        
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
        except Exception as save_error:
            print(f"Error saving chat history: {save_error}")
        
        # Construct a more concise response
        result = None
        action_result = response.get("action_result")
        
        if action_result:
            # Format action results in a more user-friendly way
            if isinstance(action_result, dict) and "result" in action_result:
                result = action_result
            else:
                result = {"result": action_result}
        
        return {
            "message": response["response"],
            "sessionId": sessionId,
            "success": True,
            "result": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing query: {str(e)}"
        )
