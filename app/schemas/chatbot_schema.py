"""
Schema definitions for chatbot interactions
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class ChatMessage(BaseModel):
    """Schema for a chat message"""
    content: str = Field(..., description="The content of the message")
    role: str = Field(default="user", description="The role of the message sender (user or assistant)")


class ChatRequest(BaseModel):
    """Schema for chat requests"""
    message: str = Field(..., description="The user's message")
    sessionId: Optional[str] = Field(None, description="Session ID for conversation tracking")


class ChatResponse(BaseModel):
    """Schema for chat responses"""
    response: str = Field(..., description="The assistant's response message")
    conversation_id: str = Field(..., description="The ID of the conversation")
    executed_action: Optional[Dict[str, Any]] = Field(None, description="Details of any action executed")
    suggested_next_steps: Optional[List[str]] = Field(None, description="Suggested next actions for the user")
    debug_info: Optional[Dict[str, Any]] = Field(None, description="Debug information (only in development mode)")


class ApiEndpoint(BaseModel):
    """Schema for API endpoint definitions"""
    path: str = Field(..., description="The path of the API endpoint")
    method: str = Field(..., description="The HTTP method for this endpoint")
    description: str = Field(..., description="Description of what this endpoint does")
    required_params: Optional[Dict[str, Any]] = Field(None, description="Required parameters for this endpoint")
    optional_params: Optional[Dict[str, Any]] = Field(None, description="Optional parameters for this endpoint")
    example_request: Optional[Dict[str, Any]] = Field(None, description="Example request body")
    example_response: Optional[Dict[str, Any]] = Field(None, description="Example response")
