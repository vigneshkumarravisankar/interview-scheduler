#!/usr/bin/env python3

import requests
import json

def test_agent_endpoint():
    url = "http://localhost:5000/api/agents/query"
    
    # Test data
    test_data = {
        "query": "test query",
        "agent_system_type": "crew_ai"
    }
    
    try:
        print("Testing agent endpoint...")
        print(f"URL: {url}")
        print(f"Data: {json.dumps(test_data, indent=2)}")
        
        response = requests.post(
            url,
            json=test_data,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ SUCCESS: Agent endpoint is working!")
        else:
            print("❌ ERROR: Agent endpoint failed")
            
    except Exception as e:
        print(f"❌ EXCEPTION: {str(e)}")

if __name__ == "__main__":
    test_agent_endpoint()
