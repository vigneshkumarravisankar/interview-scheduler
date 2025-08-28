# Interview Scheduler Agent

# Updated readme agent 1 - test - 28/08

An AI-powered interview scheduling system built with FastAPI, CrewAI, LangGraph, and Firebase.

## Overview

This application helps with creating job postings and managing the interview process using AI agents. The system includes:

- Job posting management (create, read, update, delete)
- AI-powered interview question generation based on job requirements
- Candidate evaluation using AI agents
- Interview scheduling capabilities
- Integration with Firebase for data storage

## Technology Stack

- **FastAPI**: A modern, high-performance web framework for building APIs
- **CrewAI**: Framework for orchestrating role-playing AI agents
- **LangGraph**: Library for creating LLM-powered multi-step reasoning systems
- **Firebase/Firestore**: NoSQL database for storing job and interview data
- **OpenAI**: GPT models for powering the AI agents

## Project Structure

```
app/
├── api/              # API routes
├── agents/           # AI agents for interview process
├── config/           # Configuration files
├── database/         # Database connection and operations
├── models/           # Data models
├── schemas/          # Pydantic schemas for validation
├── services/         # Business logic services
├── utils/            # Utility functions
└── main.py           # Application entry point
```

## Environment Setup

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and update as needed:
   ```
   cp .env.example .env
   ```

## Firebase Setup

1. Create a Firebase project in the [Firebase Console](https://console.firebase.google.com/)
2. Set up Firestore database
3. Get your Firebase credentials
4. Set the Firebase project ID in your `.env` file

## Running the Application

Start the FastAPI server:

```
python -m app.main
```

Or using Uvicorn directly:

```
uvicorn app.main:app --reload
```

The application will be available at http://localhost:8000

## API Documentation

Once the application is running, you can access:

- Interactive API documentation: http://localhost:8000/docs
- Alternative API documentation: http://localhost:8000/redoc

## API Endpoints

### Job Posting Endpoints

- `POST /jobs/`: Create a new job posting
- `GET /jobs/`: List all job postings
- `GET /jobs/{job_id}`: Get a specific job posting
- `PUT /jobs/{job_id}`: Update a job posting
- `DELETE /jobs/{job_id}`: Delete a job posting

### AI Agent Endpoints

- `POST /analyze-job/{job_id}`: Analyze a job posting using LangGraph agents
- `POST /create-interview-crew/{job_id}`: Create a CrewAI crew for a job posting

## Development

### Testing

Run unit tests:

```
pytest
```

### Code Quality

Format code with Black:

```
black app
```

Lint code with Flake8:

```
flake8 app
```

## License

MIT
