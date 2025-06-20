"""
Interview Scheduler Agent - Entry point for the API application
"""
import os
import uvicorn
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables from .env file
load_dotenv()

# Import after loading environment variables
from app.main import app

# Set default OpenAI API key if not in environment 
if "OPENAI_API_KEY" not in os.environ:
    os.environ["OPENAI_API_KEY"] = "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"

if __name__ == "__main__":
    """
    Run the FastAPI application
    
    Start with:
        python run.py
        
    Environment variables:
        PORT: Port to run the server on (default: 8000)
        HOST: Host to run the server on (default: 0.0.0.0)
        RELOAD: Whether to reload the server on file changes (default: True)
    """
    # Get configuration from environment
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0") 
    reload = os.getenv("RELOAD", "True").lower() == "true"
    
    origins = ["*"]
    
    # Print startup message
    print("\n" + "="*80)
    print("🤖 INTERVIEW SCHEDULER AGENT 🤖")
    print("="*80)
    print(f"Starting server on {host}:{port}")
    print(f"API documentation: http://localhost:{port}/docs")
    print(f"Agent interface: http://localhost:{port}/agent")
    print(f"Chatbot demo: http://localhost:{port}/chatbot")
    print("="*80 + "\n")
    
    # Run the server
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload
    )
