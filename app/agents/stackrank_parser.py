"""
Natural language request parser for stackrank operations
"""
import os
import re
import json
import logging
from typing import Dict, Any
from openai import OpenAI

logger = logging.getLogger(__name__)

# Get OpenAI API Key from environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY not found in environment. Using default key.")
    # Default key from the project setup
    OPENAI_API_KEY = "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"


def parse_stackrank_request(request_text: str) -> Dict[str, Any]:
    """
    Parse natural language stackranking request using LLM with enhanced error handling
    
    Args:
        request_text: Natural language stackranking request
        
    Returns:
        Dictionary with parsed stackranking parameters
    """
    try:
        # Initialize OpenAI client
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Prepare system prompt
        system_prompt = """
        You are an expert at parsing stackranking and offer letter requests. Extract structured information from 
        the request and format it into the exact JSON structure requested.
        
        Make sure:
        1. Extract the job role name exactly as provided
        2. Extract the joining date if mentioned
        3. Extract the compensation/salary if mentioned
        4. Determine if offer letters should be sent
        5. Extract the percentage of top candidates to select (default: top 1%)
        6. Return ONLY valid JSON with no additional text
        """
        
        # Prepare user prompt
        user_prompt = f"""
        Parse the following stackranking request and format it into this exact JSON structure:
        
        {{
          "job_role_name": "",              # Job role name
          "joining_date": "",               # Joining date if mentioned (format: YYYY-MM-DD)
          "compensation_offered": "",       # Compensation if mentioned
          "send_offer_letters": true,       # Whether to send offer letters
          "top_percentage": 1,              # Percentage of top candidates to select (default: 1)
          "action_type": "stackrank"        # Type of action requested
        }}
        
        STACKRANKING REQUEST:
        {request_text}
        
        IMPORTANT:
        - Extract job role exactly as written
        - If joining date is mentioned, format as YYYY-MM-DD (e.g., "July 10th, 2025" becomes "2025-07-10")
        - If compensation is mentioned, extract the amount with currency/units
        - If request mentions "send offer" or "offer letter", set send_offer_letters to true
        - Default top_percentage to 1 unless specifically mentioned
        - Return ONLY valid JSON with no additional text or explanations
        """
        
        # Call the LLM with timeout and retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = openai_client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1,  # Low temperature for consistent extraction
                    response_format={"type": "json_object"},
                    timeout=30  # 30 second timeout
                )
                
                # Parse the JSON response
                parsed_request = json.loads(response.choices[0].message.content)
                break
                
            except Exception as e:
                logger.warning(f"LLM parsing attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise
        
        # Validate and provide defaults for required fields
        required_fields = ["job_role_name", "send_offer_letters", "top_percentage", "action_type"]
        for field in required_fields:
            if field not in parsed_request:
                logger.warning(f"Missing field {field} in LLM response")
                # Provide defaults
                if field == "send_offer_letters":
                    parsed_request[field] = True
                elif field == "top_percentage":
                    parsed_request[field] = 1
                elif field == "action_type":
                    parsed_request[field] = "stackrank"
                else:
                    parsed_request[field] = ""
        
        # Additional validation
        if not parsed_request["job_role_name"]:
            # Try to extract job role using regex as fallback
            job_role_patterns = [
                r'(?:for|role|position)\s+([A-Za-z\s]+?)(?:\s+role|\s+position|$)',
                r'([A-Za-z\s]+?)\s+(?:role|position|candidates)',
                r'stackrank.*?([A-Za-z\s]+?)(?:\s+and|\s+with|$)'
            ]
            
            for pattern in job_role_patterns:
                match = re.search(pattern, request_text, re.IGNORECASE)
                if match:
                    parsed_request["job_role_name"] = match.group(1).strip()
                    break
            
            if not parsed_request["job_role_name"]:
                parsed_request["job_role_name"] = "Unknown Role"
        
        return parsed_request
    
    except Exception as e:
        logger.error(f"Error parsing stackrank request with LLM: {e}")
        # Return a minimal structure as fallback with better defaults
        return {
            "job_role_name": "Unknown Role",
            "joining_date": "",
            "compensation_offered": "",
            "send_offer_letters": True,
            "top_percentage": 1,
            "action_type": "stackrank",
            "parsing_error": str(e)
        }
