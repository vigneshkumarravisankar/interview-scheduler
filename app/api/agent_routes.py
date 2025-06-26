"""
Routes for the agent system
"""
import os
from typing import Dict, Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
import socketio
import json
import uuid
import asyncio
from datetime import datetime

from app.schemas.agent_schema import AgentQueryRequest, AgentResponse, AgentSystemType
from app.agents.crew_agent_system import get_agent_system
from app.agents.langgraph_agent import get_langgraph_agent

# Create router
router = APIRouter(
    prefix="/api/agents",
    tags=["agents"],
)

# Create Socket.IO server
sio = socketio.AsyncServer(
    async_mode='asgi', 
    cors_allowed_origins='*',
    logger=True,
    engineio_logger=True
)

# Create Socket.IO app
socket_app = socketio.ASGIApp(sio)

# Store active sessions
active_sessions = {}

@router.post("/query", response_model=AgentResponse)
async def process_agent_query(request: AgentQueryRequest):
    """
    Process a query using the agent system
    
    Args:
        request: The query request
    
    Returns:
        The agent response
    """
    try:
        session_id = request.session_id or str(uuid.uuid4())
        
        # Select the appropriate agent system
        agent_type_str = request.agent_system_type or "crew_ai"
        print(f"DEBUG: agent_system_type = {agent_type_str}")
        print(f"DEBUG: agent_system_type type = {type(agent_type_str)}")
        
        # Use simple string comparison
        if agent_type_str == "crew_ai":
            agent_system = get_agent_system()
            # Process the query with CrewAI
            result = agent_system.process_query(request.query, session_id)
        else:  # LangGraph
            agent_system = get_langgraph_agent()
            # Process with LangGraph (requires job_data)
            job_data = request.job_data or {
                "job_role_name": "Software Engineer",
                "job_description": "We're looking for an experienced software engineer proficient in Python and modern web frameworks.",
                "years_of_experience_needed": "3-5 years"
            }
            result = agent_system.process_query(request.query, job_data, request.candidate_data)
        
        # Transform to response model
        response = AgentResponse(
            session_id=session_id,
            query=request.query,
            response=result.get("response", ""),
            thought_process=result.get("thought_process", []),
            primary_agent=result.get("primary_agent", ""),
            timestamp=datetime.now().isoformat()
        )
        
        return response
    except Exception as e:
        import traceback
        print(f"Full error traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@sio.event
async def connect(sid, environ):
    """Handle client connection"""
    print(f"Client connected: {sid}")
    await sio.emit('connected', {'message': 'Connected to agent server'}, room=sid)

@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    print(f"Client disconnected: {sid}")
    if sid in active_sessions:
        del active_sessions[sid]

@sio.event
async def join_session(sid, data):
    """Handle client joining a session"""
    session_id = data.get('session_id', str(uuid.uuid4()))
    active_sessions[sid] = session_id
    await sio.emit('session_joined', {'session_id': session_id}, room=sid)
    print(f"Client {sid} joined session {session_id}")

@sio.event
async def agent_query(sid, data):
    """Handle agent query from client"""
    try:
        query = data.get('query', '')
        session_id = active_sessions.get(sid, str(uuid.uuid4()))
        agent_system_type = data.get('agent_system_type', 'crew_ai')
        
        if not query:
            await sio.emit('error', {'message': 'Query is required'}, room=sid)
            return
        
        # Let client know we're processing
        await sio.emit('processing_started', {'message': 'Processing your query...'}, room=sid)
        
        # Select the appropriate agent system
        if agent_system_type == 'langgraph':
            agent_system = get_langgraph_agent()
            # For LangGraph, we need job data
            job_data = data.get('job_data', {
                "job_role_name": "Software Engineer",
                "job_description": "We're looking for an experienced software engineer proficient in Python and modern web frameworks.",
                "years_of_experience_needed": "3-5 years"
            })
        else:
            # Default to CrewAI
            agent_system = get_agent_system()
        
        # Process the query asynchronously
        # First emit that we're starting to think
        await sio.emit('thinking', {
            'agent': 'System',
            'thought': f'Processing query: {query}',
            'timestamp': datetime.now().isoformat()
        }, room=sid)
        
        # Run agent query in a separate thread to not block the event loop
        loop = asyncio.get_event_loop()
        
        def process_query():
            if agent_system_type == 'langgraph':
                # For LangGraph, we need job data
                job_data = data.get('job_data', {
                    "job_role_name": "Software Engineer",
                    "job_description": "We're looking for an experienced software engineer proficient in Python and modern web frameworks.",
                    "years_of_experience_needed": "3-5 years"
                })
                candidate_data = data.get('candidate_data', None)
                return agent_system.process_query(query, job_data, candidate_data)
            else:
                # Default to CrewAI
                return agent_system.process_query(query, session_id)
        
        # Run in executor to not block the event loop
        result = await loop.run_in_executor(None, process_query)
        
        # Stream thought process to client
        thoughts = result.get('thought_process', [])
        for thought in thoughts:
            # Make sure thought has all required fields
            if 'agent' not in thought:
                thought['agent'] = 'System'
            if 'thought' not in thought:
                thought['thought'] = 'Processing...'
            if 'timestamp' not in thought:
                thought['timestamp'] = datetime.now().isoformat()
                
            await sio.emit('thinking', thought, room=sid)
            # Add a small delay to simulate thinking and allow client to process
            await asyncio.sleep(0.7)
        
        # Send final result
        # Ensure all data is JSON serializable
        response = {
            'session_id': session_id,
            'query': query,
            'response': str(result.get('response', '')),
            'primary_agent': result.get('primary_agent', ''),
            'timestamp': datetime.now().isoformat(),
            
        }
        
        # Wait a moment after the thoughts are displayed before showing the final response
        await asyncio.sleep(1.0)
        await sio.emit('agent_response', response, room=sid)
        print(f"Sent response to {sid}")
        
    except Exception as e:
        print(f"Error processing query: {e}")
        await sio.emit('error', {'message': f'Error: {str(e)}'}, room=sid)
