"""
API routes for the Firebase natural language query service
"""
import json
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field

from app.services.firebase_query_service import FirebaseQueryService

# Create router
router = APIRouter(
    prefix="/firebase-query",
    tags=["firebase query"],
    responses={404: {"description": "Not found"}},
)

# Request and response models
class QueryRequest(BaseModel):
    """Request model for natural language query"""
    query: str = Field(..., description="Natural language query text")
    conversation_id: Optional[str] = Field(None, description="Optional conversation ID for context")

class FeedbackRequest(BaseModel):
    """Request model for updating interview feedback"""
    interview_id: str = Field(..., description="ID of the interview candidate document")
    round_index: int = Field(..., description="Index of the interview round (0-based)")
    feedback: str = Field(..., description="Feedback text from the interviewer")
    rating: int = Field(..., description="Rating out of 10")
    selected_for_next: str = Field(..., description="'yes' or 'no' indicating if candidate moves to next round")

class QueryResponse(BaseModel):
    """Response model for query results"""
    response: str = Field(..., description="Natural language response to the query")
    conversation_id: str = Field(..., description="ID for tracking conversation history")
    raw_result: Optional[Dict[str, Any]] = Field(None, description="Raw result data (if available)")

@router.post("/", response_model=QueryResponse)
async def process_natural_language_query(request: QueryRequest):
    """
    Process a natural language query to the Firebase database
    
    This endpoint accepts queries in natural language and returns relevant information
    from the database. It can handle queries about jobs, candidates, interviews, and more.
    
    Examples:
    - "Show me all open jobs"
    - "How many candidates have been shortlisted for the Software Engineer position?"
    - "What is the status of the interview process for candidate John Smith?"
    - "Update the status of job ABC123 to closed"
    """
    try:
        # Process the query
        result = FirebaseQueryService.process_query(request.query, request.conversation_id)
        
        # Save to conversation history if we have a conversation ID
        if "conversation_id" in result:
            FirebaseQueryService.add_to_conversation_history(
                result["conversation_id"],
                request.query,
                result.get("response", "")
            )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@router.post("/conversation-history", response_model=dict)
async def get_conversation_history(conversation_id: str = Body(..., embed=True)):
    """
    Get the conversation history for a specific conversation ID
    """
    try:
        history = FirebaseQueryService.get_conversation_history(conversation_id)
        return {"conversation_id": conversation_id, "history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving conversation history: {str(e)}")

@router.post("/update-interview-feedback", response_model=dict)
async def update_interview_feedback(request: FeedbackRequest):
    """
    Update feedback for a specific interview round
    
    This endpoint updates the feedback, rating, and selection status for a specific
    interview round. If this is the final round and the candidate is selected, they
    will automatically be moved to the final_candidates collection.
    """
    try:
        result = FirebaseQueryService.update_interview_feedback(
            request.interview_id,
            request.round_index,
            request.feedback,
            request.rating,
            request.selected_for_next
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating interview feedback: {str(e)}")
