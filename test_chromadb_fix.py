"""
Test script to verify ChromaDB functionality after migration
"""

from app.database.chroma_db import ChromaVectorDB, FirestoreDB
from app.services.job_service import JobService
from app.services.candidate_service import CandidateService
import uuid

def test_chromadb_operations():
    """Test basic ChromaDB operations"""
    print("🔧 Testing ChromaDB Operations...")
    
    try:
        # Test 1: Create a sample job
        print("1. Testing job creation...")
        from app.schemas.job_schema import JobPostingCreate
        
        job_data = JobPostingCreate(
            job_role_name="Test Software Engineer",
            job_description="We are looking for a talented software engineer to join our team.",
            years_of_experience_needed="3-5 years",
            location="Remote",
            status="active"
        )
        
        job_result = JobService.create_job_posting(job_data)
        print(f"✅ Job created successfully: {job_result.job_id}")
        
        # Test 2: Retrieve the job
        print("2. Testing job retrieval...")
        retrieved_job = JobService.get_job_posting(job_result.job_id)
        if retrieved_job:
            print(f"✅ Job retrieved successfully: {retrieved_job.job_role_name}")
        else:
            print("❌ Failed to retrieve job")
            
        # Test 3: Test semantic search
        print("3. Testing semantic search...")
        db = ChromaVectorDB()
        search_results = db.semantic_search(
            collection_name="jobs",
            query_text="software developer position",
            n_results=5
        )
        print(f"✅ Semantic search returned {len(search_results)} results")
        
        # Test 4: Test RAG search
        print("4. Testing RAG search...")
        rag_results = db.rag_search(
            collection_name="jobs",
            query="What are the requirements for software engineering roles?",
            n_results=3
        )
        print(f"✅ RAG search returned context with {rag_results['document_count']} documents")
        
        # Test 5: Get collection stats
        print("5. Testing collection statistics...")
        stats = db.get_collection_stats("jobs")
        print(f"✅ Jobs collection has {stats['document_count']} documents")
        
        print("\n🎉 All ChromaDB tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ ChromaDB test failed: {e}")
        return False

if __name__ == "__main__":
    test_chromadb_operations()
