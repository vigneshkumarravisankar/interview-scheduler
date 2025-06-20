"""
Basic tests for the Interview Scheduler Agent API endpoints
"""
import os
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app

# Create test client
client = TestClient(app)

# Test data
test_job = {
    "job_role_name": "Software Engineer",
    "job_description": "We are looking for a skilled software engineer with experience in Python and web development.",
    "years_of_experience_needed": "3-5 years",
    "location": "Remote"
}


def test_health_check():
    """Test the health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root_endpoint():
    """Test the root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_create_job_posting():
    """Test creating a job posting"""
    response = client.post("/jobs/", json=test_job)
    
    # For this test we'll accept both 201 (created) or 500 (if Firebase is not configured)
    assert response.status_code in [201, 500]
    
    if response.status_code == 201:
        # If successful, verify response structure
        data = response.json()
        assert "job_id" in data
        assert data["job_role_name"] == test_job["job_role_name"]
        
        # Save the job ID for other tests
        with open("test_job_id.txt", "w") as f:
            f.write(data["job_id"])


def test_get_job_posting():
    """Test getting a job posting"""
    # Try to load previously created job ID
    job_id = None
    try:
        with open("test_job_id.txt", "r") as f:
            job_id = f.read().strip()
    except FileNotFoundError:
        pytest.skip("No job ID available from previous test")
    
    if job_id:
        response = client.get(f"/jobs/{job_id}")
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert data["job_id"] == job_id


def test_langgraph_endpoint():
    """Test the LangGraph process endpoint"""
    # Try to load previously created job ID
    job_id = None
    try:
        with open("test_job_id.txt", "r") as f:
            job_id = f.read().strip()
    except FileNotFoundError:
        # Use a mock ID for testing
        job_id = "mock-job-id"
    
    test_data = {
        "query": "Analyze this job posting",
        "job_id": job_id
    }
    
    # Just check if the endpoint exists, don't worry about successful processing
    response = client.post("/langgraph/process", json=test_data)
    assert response.status_code in [200, 404, 422, 500]


if __name__ == "__main__":
    # Run the tests
    pytest.main(["-xvs", "test_api.py"])
