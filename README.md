# Interview Scheduler Agent

A sophisticated interview scheduling system powered by AI agents (CrewAI + LangGraph) to automate job posting management, candidate screening, interview planning, and scheduling.

## 🚀 Features

- **AI-Powered Job Analysis**: Analyze job postings to extract key requirements and create ideal candidate profiles.
- **Intelligent Candidate Screening**: Evaluate candidates against job requirements and rank by fit score.
- **Automated Interview Planning**: Generate tailored interview plans with rounds and questions.
- **Smart Interview Scheduling**: Handle complex interview scheduling with calendar integration.
- **Multiple Agent Architectures**: 
  - CrewAI-based agents for collaborative reasoning
  - LangGraph-based agents for stateful workflows
- **Integration Ready**:
  - Google Calendar integration
  - Firebase database storage
  - PDF resume parsing
  - Email notifications

## 🛠️ Technology Stack

- **Backend Framework**: FastAPI
- **Database**: Firebase Firestore
- **AI/ML**: OpenAI GPT models, LangChain, CrewAI, LangGraph
- **Cloud**: Google Cloud Platform (GCP)
- **Calendar**: Google Calendar API
- **Scheduling**: Custom scheduling algorithms

## 📋 API Endpoints

### Job Management
- `POST /jobs/`: Create a new job posting
- `GET /jobs/{job_id}`: Get job details
- `GET /jobs/`: List all job postings
- `PUT /jobs/{job_id}`: Update a job posting

### Candidate Management
- `/candidates/`: Manage candidate profiles
- `/resume/`: Process and analyze resumes

### Interview Process
- `/shortlist/`: Shortlist candidates for interviews
- `/reschedule/`: Reschedule interviews
- `/langgraph/process`: Process using LangGraph agent workflow
- `/agents/`: CrewAI agent-based operations

## 🔧 Installation and Setup

### Prerequisites
- Python 3.10+
- Firebase account and project
- Google Calendar API credentials
- OpenAI API key

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/interview-scheduler-agent.git
   cd interview-scheduler-agent
   ```

2. Create a virtual environment:
   ```bash
   python -m venv envi
   source envi/bin/activate  # On Windows: envi\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   - Copy `.env.example` to `.env`
   - Fill in your API keys and configurations

5. Set up Firebase:
   - Place your Firebase service account key in `app/config/service_account.json`

6. Set up Google Calendar:
   - Place your Google Calendar credentials in `app/config/calendar_service_account.json`

7. Run the application:
   ```bash
   python run.py
   ```

8. Access the application:
   - API documentation: http://localhost:8000/docs
   - Agent interface: http://localhost:8000/agent
   - Chatbot demo: http://localhost:8000/chatbot

## 🔀 Agent Workflows

### CrewAI-Based Workflow

The CrewAI system uses a team of specialized agents:
1. **Job Analyzer**: Analyzes job descriptions to extract requirements
2. **Candidate Screener**: Evaluates candidates against job requirements
3. **Interview Planner**: Designs interview processes and questions
4. **Scheduler**: Coordinates interview logistics

### LangGraph-Based Workflow

The LangGraph system implements a stateful workflow:
1. **Job Analysis**: Analyzes job requirements and creates ideal profiles
2. **Candidate Screening**: Evaluates and ranks candidates
3. **Interview Planning**: Creates structured interview rounds
4. **Scheduling**: Generates optimal interview schedules

## 📊 Sample Usage

### Creating a Job Posting

```python
import requests

job_data = {
    "job_role_name": "Senior Software Engineer",
    "job_description": "We are looking for a Senior Software Engineer...",
    "years_of_experience_needed": "5+ years",
    "location": "Remote"
}

response = requests.post("http://localhost:8000/jobs/", json=job_data)
print(response.json())
```

### Shortlisting Candidates

```python
import requests

shortlist_data = {
    "job_id": "job-123",
    "number_of_candidates": 5,
    "number_of_rounds": 3
}

response = requests.post("http://localhost:8000/shortlist/", json=shortlist_data)
print(response.json())
```

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request
