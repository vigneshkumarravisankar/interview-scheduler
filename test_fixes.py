#!/usr/bin/env python3
"""
Test script to verify the CrewAI agent system fixes
"""

import sys
import os
sys.path.append('.')

from app.agents.crew_agent_system import get_agent_system
from app.database.chroma_db import FirestoreDB
import uuid

def test_chroma_db_fix():
    """Test that ChromaDB create_document_with_id works as a static method"""
    print("Testing ChromaDB fix...")
    
    try:
        # Test creating a document with ID
        test_doc_id = str(uuid.uuid4())
        test_data = {
            "name": "Test Document",
            "description": "Testing ChromaDB fix",
            "status": "active"
        }
        
        # This should now work without the missing argument error
        result_id = FirestoreDB.create_document_with_id("test_collection", test_doc_id, test_data)
        print(f"✅ ChromaDB fix successful - Document created with ID: {result_id}")
        return True
    except Exception as e:
        print(f"❌ ChromaDB fix failed: {e}")
        return False

def test_job_creation_tool_fix():
    """Test that CreateJobPosting tool handles dictionary inputs"""
    print("Testing CreateJobPosting tool fix...")
    
    try:
        # Get the agent system
        agent_system = get_agent_system()
        
        # Test with a job creation query that would pass a dictionary to the tool
        test_query = "Create a job posting for a Software Engineer position with 3+ years experience in Python and React, located in San Francisco."
        
        # Process the query
        result = agent_system.process_query(test_query, "test_session")
        
        print(f"✅ CreateJobPosting tool fix successful")
        print(f"Response: {result['response'][:200]}..." if len(result['response']) > 200 else result['response'])
        return True
    except Exception as e:
        print(f"❌ CreateJobPosting tool fix failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🔧 Testing Interview Agent System Fixes\n")
    
    # Test 1: ChromaDB fix
    chroma_success = test_chroma_db_fix()
    print()
    
    # Test 2: Job creation tool fix
    job_tool_success = test_job_creation_tool_fix()
    print()
    
    # Summary
    print("=" * 50)
    print("TEST RESULTS SUMMARY:")
    print(f"ChromaDB Fix: {'✅ PASSED' if chroma_success else '❌ FAILED'}")
    print(f"Job Creation Tool Fix: {'✅ PASSED' if job_tool_success else '❌ FAILED'}")
    
    if chroma_success and job_tool_success:
        print("\n🎉 All fixes are working correctly!")
        return 0
    else:
        print("\n⚠️  Some fixes need attention.")
        return 1

if __name__ == "__main__":
    exit(main())
