"""
Schemas for the agent API
"""
from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class AgentSystemType(str, Enum):
    """
    Type of agent system to use
    """
    CREW_AI = "crew_ai"
    LANGGRAPH = "langgraph"


class ThoughtProcess(BaseModel):
    """
    Model for a thought in the agent's thought process
    """
    agent: str = Field(..., description="Name of the agent")
    thought: str = Field(..., description="Content of the thought")
    timestamp: str = Field(..., description="Timestamp of when the thought occurred")


class AgentQueryRequest(BaseModel):
    """
    Request model for agent query
    """
    query: str = Field(..., description="User query to process")
    session_id: Optional[str] = Field(None, description="Session ID for conversation context")
    agent_system_type: str = Field(default="crew_ai", 
                                   description="Type of agent system to use (crew_ai or langgraph)")
    job_data: Optional[Dict[str, Any]] = Field(default=None, 
                                           description="Job data needed for LangGraph processing")
    candidate_data: Optional[Dict[str, Any]] = Field(default=None, 
                                                description="Candidate data needed for LangGraph processing")


class AgentResponse(BaseModel):
    """
    Response model for agent query
    """
    session_id: str = Field(..., description="Session ID for conversation context")
    query: str = Field(..., description="User query that was processed")
    response: str = Field(..., description="Agent's response to the query")
    primary_agent: str = Field(..., description="Primary agent that handled the query")
    thought_process: List[Dict[str, Any]] = Field(default_factory=list, description="List of thoughts in the agent's thought process")
    timestamp: str = Field(..., description="Timestamp of the response")
