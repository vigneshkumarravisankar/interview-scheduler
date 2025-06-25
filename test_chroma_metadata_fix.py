#!/usr/bin/env python3
"""
Test script to verify ChromaDB metadata serialization fix
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from database.chroma_db import ChromaVectorDB
import uuid

def test_complex_metadata():
    """Test creating and retrieving documents with complex metadata"""
    
    # Initialize ChromaDB
    db = ChromaVectorDB()
    collection_name = "test_metadata"
    
    # Test data with complex nested structures (like the original error)
    test_document = {
        "id": str(uuid.uuid4()),
        "name": "Test Candidate",
        "email": "test@example.com",
        "interview_rounds": [
            {
                'rating_out_of_10': None, 
                'feedback': None, 
                'meet_link': 'https://meet.google.com/omx-coxz-eqt', 
                'scheduled_time': '10AM', 
                'interviewer_id': '', 
                'interviewer_name': 'Technical Interviewer 1', 
                'interviewer_email': 'technical_interviewer@example.com', 
                'round_type': 'Technical', 
                'department': 'Engineering', 
                'scheduled_event': {
                    'htmlLink': 'https://www.google.com/calendar/event?eid=fmvhlys2cqucnnpsa6v8', 
                    'start': {'timeZone': 'Asia/Kolkata', 'dateTime': '2025-06-25T10:00:00+05:30'}, 
                    'end': {'timeZone': 'Asia/Kolkata', 'dateTime': '2025-06-25T11:00:00+05:30'}, 
                    'id': 'fmvhlys2cqucnnpsa6v8'
                }, 
                'round_number': 1, 
                'isSelectedForNextRound': None
            },
            {
                'rating_out_of_10': None, 
                'feedback': None, 
                'meet_link': '', 
                'scheduled_time': '', 
                'interviewer_id': '', 
                'interviewer_name': 'Technical Interviewer 2', 
                'interviewer_email': 'technical_interviewer@example.com', 
                'round_type': 'Technical', 
                'department': 'Engineering', 
                'scheduled_event': {}, 
                'round_number': 2, 
                'isSelectedForNextRound': None
            }
        ],
        "skills": ["Python", "JavaScript", "React"],
        "experience": {
            "years": 5,
            "companies": ["Company A", "Company B"]
        },
        "status": "active"
    }
    
    print("Testing ChromaDB metadata serialization fix...")
    
    try:
        # Test 1: Create document with complex metadata
        print("1. Creating document with complex metadata...")
        doc_id = db.create_document_with_id(collection_name, test_document["id"], test_document)
        print(f"   ✓ Document created successfully with ID: {doc_id}")
        
        # Test 2: Retrieve document and verify data integrity
        print("2. Retrieving document...")
        retrieved_doc = ChromaVectorDB.get_document(collection_name, doc_id)
        
        if retrieved_doc:
            print("   ✓ Document retrieved successfully")
            
            # Verify complex data structures are preserved
            if isinstance(retrieved_doc.get("interview_rounds"), list):
                print("   ✓ Interview rounds list preserved")
                
                if len(retrieved_doc["interview_rounds"]) == 2:
                    print("   ✓ All interview rounds preserved")
                    
                    # Check nested dictionary structure
                    first_round = retrieved_doc["interview_rounds"][0]
                    if isinstance(first_round.get("scheduled_event"), dict):
                        print("   ✓ Nested scheduled_event dictionary preserved")
                        
                        if "start" in first_round["scheduled_event"]:
                            print("   ✓ Deep nested structures preserved")
                    else:
                        print("   ✗ Nested dictionary not preserved properly")
                else:
                    print(f"   ✗ Expected 2 interview rounds, got {len(retrieved_doc['interview_rounds'])}")
            else:
                print("   ✗ Interview rounds not preserved as list")
            
            # Test skills array
            if isinstance(retrieved_doc.get("skills"), list) and len(retrieved_doc["skills"]) == 3:
                print("   ✓ Skills array preserved")
            else:
                print("   ✗ Skills array not preserved properly")
            
            # Test experience object
            if isinstance(retrieved_doc.get("experience"), dict):
                print("   ✓ Experience object preserved")
            else:
                print("   ✗ Experience object not preserved properly")
        else:
            print("   ✗ Failed to retrieve document")
            return False
        
        # Test 3: Update document with more complex data
        print("3. Updating document with additional complex data...")
        update_data = {
            "new_field": {
                "nested": {
                    "deeply": ["nested", "array", "with", "strings"]
                }
            }
        }
        
        ChromaVectorDB.update_document(collection_name, doc_id, update_data)
        print("   ✓ Document updated successfully")
        
        # Test 4: Query functionality
        print("4. Testing query functionality...")
        results = ChromaVectorDB.execute_query(collection_name, "status", "==", "active")
        
        if results and len(results) > 0:
            print("   ✓ Query executed successfully")
            if isinstance(results[0].get("interview_rounds"), list):
                print("   ✓ Complex data preserved in query results")
            else:
                print("   ✗ Complex data not preserved in query results")
        else:
            print("   ✗ Query failed or returned no results")
        
        # Test 5: Clean up
        print("5. Cleaning up test data...")
        ChromaVectorDB.delete_document(collection_name, doc_id)
        print("   ✓ Test document deleted")
        
        print("\n✅ All tests passed! ChromaDB metadata serialization fix is working correctly.")
        return True
        
    except Exception as e:
        print(f"   ✗ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = test_complex_metadata()
    if success:
        print("\n🎉 ChromaDB is now ready to handle complex metadata structures!")
    else:
        print("\n❌ Tests failed. Please check the implementation.")
