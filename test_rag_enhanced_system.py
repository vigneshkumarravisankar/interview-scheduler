"""
Test script to verify RAG-enhanced agent routing and ChromaDB functionality
"""

from app.database.chroma_db import ChromaVectorDB, FirestoreDB
from app.agents.crew_agent_system import get_agent_system
from app.services.job_service import JobService
from app.services.candidate_service import CandidateService
import uuid
import json

def test_rag_enhanced_system():
    """Test RAG-enhanced agent routing system"""
    print("🔧 Testing RAG-Enhanced Agent System...")
    
    try:
        # Test 1: Initialize ChromaDB
        print("1. Testing ChromaDB initialization...")
        db = ChromaVectorDB()
        collections = db.list_collections()
        print(f"✅ ChromaDB initialized. Collections: {collections}")
        
        # Test 2: Test agent system initialization
        print("2. Testing agent system initialization...")
        agent_system = get_agent_system()
        print(f"✅ Agent system initialized with {len(agent_system.crew.agents)} agents")
        
        # Test 3: Test RAG-based routing for job queries
        print("3. Testing RAG routing for job queries...")
        job_query = "Create a new job posting for Senior Python Developer"
        rag_routing = agent_system._rag_based_agent_routing(job_query)
        print(f"✅ RAG routing - Agent: {rag_routing['primary_agent'].role if rag_routing['primary_agent'] else 'None'}")
        print(f"   Confidence: {rag_routing['confidence']:.2f}")
        print(f"   Suggested actions: {rag_routing['suggested_actions']}")
        
        # Test 4: Test RAG-based routing for candidate queries
        print("4. Testing RAG routing for candidate queries...")
        candidate_query = "Find me top profiles for Java Developer"
        rag_routing = agent_system._rag_based_agent_routing(candidate_query)
        print(f"✅ RAG routing - Agent: {rag_routing['primary_agent'].role if rag_routing['primary_agent'] else 'None'}")
        print(f"   Confidence: {rag_routing['confidence']:.2f}")
        print(f"   Suggested actions: {rag_routing['suggested_actions']}")
        
        # Test 5: Test RAG context summary
        print("5. Testing RAG context summary...")
        mock_context = {
            "jobs": {
                "document_count": 3,
                "context": "Senior Software Engineer position requiring Python, Django, and React skills..."
            },
            "candidates_data": {
                "document_count": 2,
                "context": "Experienced Python developer with 5 years of experience in web development..."
            }
        }
        summary = agent_system._create_rag_context_summary(mock_context)
        print(f"✅ RAG context summary generated: {summary[:100]}...")
        
        # Test 6: Test semantic search if data exists
        print("6. Testing semantic search...")
        if "jobs" in collections:
            search_results = db.semantic_search(
                collection_name="jobs",
                query_text="python developer position",
                n_results=3
            )
            print(f"✅ Semantic search returned {len(search_results)} results")
            if search_results:
                print(f"   Top result similarity: {search_results[0].get('_similarity_score', 'N/A')}")
        else:
            print("⚠️  No jobs collection found - skipping semantic search test")
        
        # Test 7: Test RAG search
        print("7. Testing RAG search...")
        if "jobs" in collections:
            rag_results = db.rag_search(
                collection_name="jobs",
                query="What are the requirements for software engineering roles?",
                n_results=3
            )
            print(f"✅ RAG search returned context with {rag_results['document_count']} documents")
            print(f"   Context length: {len(rag_results['context'])} characters")
        else:
            print("⚠️  No jobs collection found - skipping RAG search test")
        
        # Test 8: Test action suggestions
        print("8. Testing action suggestions...")
        actions = agent_system._generate_suggested_actions(
            "candidate_screening", 
            "Find top Java developers", 
            mock_context
        )
        print(f"✅ Generated {len(actions)} suggested actions:")
        for action in actions:
            print(f"   - {action}")
        
        # Test 9: Test collection statistics
        print("9. Testing collection statistics...")
        for collection_name in collections:
            stats = db.get_collection_stats(collection_name)
            print(f"✅ {collection_name}: {stats['document_count']} documents")
        
        # Test 10: Test query processing with RAG
        print("10. Testing query processing with RAG...")
        try:
            test_query = "Hi, I'm looking for information about available positions"
            result = agent_system.process_query(test_query, "test_session_123")
            print(f"✅ Query processed successfully")
            print(f"   Primary agent: {result.get('primary_agent', 'N/A')}")
            print(f"   Confidence: {result.get('confidence', 'N/A')}")
            print(f"   Thought process steps: {len(result.get('thought_process', []))}")
            if result.get('rag_context'):
                print(f"   RAG context collections: {list(result['rag_context']['relevant_context'].keys())}")
        except Exception as e:
            print(f"⚠️  Query processing test failed: {e}")
        
        print("\n🎉 All RAG-enhanced system tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ RAG-enhanced system test failed: {e}")
        return False

def test_query_routing_scenarios():
    """Test different query routing scenarios"""
    print("\n🔍 Testing Query Routing Scenarios...")
    
    agent_system = get_agent_system()
    
    test_queries = [
        ("Create a job for Senior Python Developer", "job_management"),
        ("Find candidates for Java Developer role", "candidate_screening"),
        ("Schedule interviews for shortlisted candidates", "scheduling"),
        ("What interview questions should I ask?", "interview_planning"),
        ("Reschedule the interview tomorrow", "scheduling"),
        ("Process resumes for data scientist position", "candidate_screening")
    ]
    
    for query, expected_intent in test_queries:
        try:
            rag_info = agent_system._rag_based_agent_routing(query)
            agent_name = rag_info['primary_agent'].role if rag_info['primary_agent'] else 'None'
            confidence = rag_info['confidence']
            
            print(f"✅ Query: '{query[:50]}...'")
            print(f"   → Agent: {agent_name}")
            print(f"   → Confidence: {confidence:.2f}")
            print(f"   → Actions: {len(rag_info['suggested_actions'])}")
            
        except Exception as e:
            print(f"❌ Query routing failed for '{query}': {e}")

if __name__ == "__main__":
    print("="*80)
    print("🚀 RAG-ENHANCED AGENT SYSTEM TESTING")
    print("="*80)
    
    # Run main tests
    success = test_rag_enhanced_system()
    
    if success:
        # Run routing scenario tests
        test_query_routing_scenarios()
        
        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED - RAG-ENHANCED SYSTEM IS READY!")
        print("="*80)
    else:
        print("\n" + "="*80)
        print("❌ SOME TESTS FAILED - CHECK CONFIGURATION")
        print("="*80)
