"""
Schema definitions for chatbot interactions
"""
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional, Literal
from enum import Enum


class UserRole(str, Enum):
    """Valid user roles for the system"""
    HR = "HR"
    RECRUITER = "Recruiter"
    INTERVIEWER = "Interviewer"
    CANDIDATE = "Candidate"
    ADMIN = "Admin"


class ChatMessage(BaseModel):
    """Schema for a chat message"""
    content: str = Field(..., description="The content of the message")
    role: str = Field(default="user", description="The role of the message sender (user or assistant)")


class ChatRequest(BaseModel):
    """Schema for chat requests"""
    message: str = Field(..., description="The user's message")
    sessionId: Optional[str] = Field(None, description="Session ID for conversation tracking")
    user_role: UserRole = Field(default=UserRole.HR, description="The role of the user interacting with the system")

    @validator('user_role', pre=True)
    def validate_user_role(cls, value):
        """Validate and normalize user role"""
        if isinstance(value, str):
            try:
                # Try to convert string to enum
                return UserRole(value)
            except ValueError:
                # If not a valid role, default to HR
                return UserRole.HR
        return value


class ChatResponse(BaseModel):
    """Schema for chat responses"""
    response: str = Field(..., description="The assistant's response message")
    conversation_id: str = Field(..., description="The ID of the conversation")
    executed_action: Optional[Dict[str, Any]] = Field(None, description="Details of any action executed")
    suggested_next_steps: Optional[List[str]] = Field(None, description="Suggested next actions for the user")
    user_role: UserRole = Field(..., description="The role of the user interacting with the system")
    role_specific_info: Optional[Dict[str, Any]] = Field(None, description="Information specific to the user's role")
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
    required_roles: Optional[List[UserRole]] = Field(None, description="User roles allowed to access this endpoint")