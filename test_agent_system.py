#!/usr/bin/env python3

import sys
import traceback
from datetime import datetime
from app.agents.crew_agent_system import get_agent_system

def test_agent_system_directly():
    """Test the agent system directly without the API layer"""
    try:
        print("Testing agent system directly...")
        
        # Get the agent system
        agent_system = get_agent_system()
        print("✅ Agent system initialized successfully")
        
        # Test a simple query
        result = agent_system.process_query("test query", "test_session")
        print("✅ Agent system processed query successfully")
        
        print(f"Result keys: {result.keys()}")
        print(f"Response: {result.get('response', 'No response')[:100]}...")
        print(f"Primary agent: {result.get('primary_agent', 'Unknown')}")
        print(f"Thought process count: {len(result.get('thought_process', []))}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        print(f"❌ Full traceback:")
        traceback.print_exc()
        return False

def test_schema_validation():
    """Test the schema validation"""
    try:
        print("\nTesting schema validation...")
        
        from app.schemas.agent_schema import AgentQueryRequest, AgentResponse
        
        # Test creating the request model
        request = AgentQueryRequest(
            query="test query",
            agent_system_type="crew_ai"
        )
        print("✅ AgentQueryRequest created successfully")
        print(f"Request: {request}")
        
        # Test creating the response model
        response = AgentResponse(
            session_id="test_session",
            query="test query",
            response="test response",
            primary_agent="Test Agent",
            thought_process=[],
            timestamp=datetime.now().isoformat()
        )
        print("✅ AgentResponse created successfully")
        print(f"Response: {response}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR in schema validation: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Testing Agent System Components")
    print("=" * 50)
    
    # Test schema first
    schema_ok = test_schema_validation()
    
    if schema_ok:
        # Test agent system
        agent_ok = test_agent_system_directly()
        
        if agent_ok:
            print("\n✅ ALL TESTS PASSED")
        else:
            print("\n❌ AGENT SYSTEM TEST FAILED")
    else:
        print("\n❌ SCHEMA VALIDATION TEST FAILED")
