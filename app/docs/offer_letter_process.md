# Offer Letter Generation Process

This document explains the process of stackranking candidates after interviews and sending offer letters to the top candidates.

## Overview

After candidates have completed all interview rounds, the stackranking process evaluates them based on their interview feedback scores. The top candidate is then selected to receive an offer letter.

## API Endpoints

### 1. Stack Rank Candidates

```
GET /final-selection/stackrank/{job_id}
```

This endpoint returns a list of all candidates for a job who have completed all interview rounds, sorted by their total interview score (descending).

**Example Response:**
```json
[
  {
    "candidate_id": "candidate-123",
    "interview_candidate_id": "interview-456",
    "total_score": 28,
    "feedback": [
      {
        "interviewer_id": "interviewer-1",
        "interviewer_name": "John Smith",
        "interviewer_email": "john.smith@example.com",
        "department": "Engineering",
        "rating_out_of_10": 9,
        "feedback": "Strong technical skills..."
      },
      {
        "interviewer_id": "interviewer-2",
        "interviewer_name": "Jane Doe",
        "interviewer_email": "jane.doe@example.com",
        "department": "Management",
        "rating_out_of_10": 8,
        "feedback": "Good leadership potential..."
      },
      {
        "interviewer_id": "interviewer-3",
        "interviewer_name": "Alice Johnson",
        "interviewer_email": "alice.johnson@example.com",
        "department": "Human Resources",
        "rating_out_of_10": 10,
        "feedback": "Excellent cultural fit..."
      }
    ]
  },
  {
    "candidate_id": "candidate-789",
    "interview_candidate_id": "interview-101",
    "total_score": 25,
    "feedback": [...]
  }
]
```

### 2. Get Top Candidate

```
GET /final-selection/top-candidate/{job_id}
```

This endpoint returns the top candidate for a job, including both their interview data and candidate profile.

**Example Response:**
```json
{
  "interview_data": {
    "candidate_id": "candidate-123",
    "interview_candidate_id": "interview-456",
    "total_score": 28,
    "feedback": [...]
  },
  "candidate_data": {
    "id": "candidate-123",
    "name": "Michael Brown",
    "email": "michael.brown@example.com",
    "resume_url": "https://storage.example.com/resumes/michael-brown.pdf",
    "skills": ["Python", "Machine Learning", "AWS"],
    "years_experience": 5,
    "ai_fit_score": 95
  }
}
```

### 3. Send Offer Letter

```
POST /final-selection/send-offer/{job_id}?compensation_offered=$120,000%20per%20year
```

This endpoint selects the top candidate for a job and sends them an offer letter by email. The offer letter includes the job title, compensation, and other details.

**Example Response:**
```json
{
  "id": "offer-789",
  "candidate_name": "Michael Brown",
  "job_id": "job-123",
  "candidate_id": "candidate-123",
  "job_role": "Senior Data Scientist",
  "compensation_offered": "$120,000 per year",
  "email": "michael.brown@example.com"
}
```

### 4. Get Offers for Job

```
GET /final-selection/offers/{job_id}
```

This endpoint returns all offer letters sent for a specific job.

**Example Response:**
```json
[
  {
    "id": "offer-789",
    "candidate_name": "Michael Brown",
    "job_id": "job-123",
    "candidate_id": "candidate-123",
    "job_role": "Senior Data Scientist",
    "compensation_offered": "$120,000 per year",
    "email": "michael.brown@example.com"
  }
]
```

## How Candidate Scoring Works

1. Each candidate must complete all scheduled interview rounds.
2. After each interview, the interviewer provides:
   - A rating out of 10
   - Written feedback
   - Selection decision (yes/no/maybe)

3. The system calculates a total score by adding all ratings from all interview rounds.
4. Candidates are ranked by their total score (highest first).
5. Only candidates with complete feedback (ratings for all rounds) are considered.

## Offer Letter Process

1. The top candidate is selected based on the stackranking.
2. An offer letter is generated with:
   - Candidate's name
   - Job title
   - Compensation details
   - Start date information
   
3. The offer letter is sent to the candidate via email in both plain text and HTML formats.
4. A record of the offer is stored in the `final_candidates` collection in Firebase.

## Workflow Example

### Complete Workflow

1. Create a job posting:
   ```
   POST /jobs/
   {
     "job_role_name": "Senior Data Scientist",
     "job_description": "We are looking for an experienced data scientist...",
     "years_of_experience_needed": 5
   }
   ```

2. Process resumes for the job:
   ```
   POST /candidates/process/{job_id}
   ```

3. Shortlist candidates and schedule interviews:
   ```
   POST /interviews/shortlist
   {
     "job_id": "job-123",
     "number_of_candidates": 5,
     "no_of_interviews": 3
   }
   ```

4. After all interviews are completed with feedback, stack rank the candidates:
   ```
   GET /final-selection/stackrank/{job_id}
   ```

5. Send an offer to the top candidate:
   ```
   POST /final-selection/send-offer/{job_id}?compensation_offered=$120,000%20per%20year
   ```

6. Check if the offer was sent:
   ```
   GET /final-selection/offers/{job_id}
   ```

### Gmail API Configuration

To set up the Gmail API for sending offer letters:

1. Create OAuth credentials in Google Cloud Console
2. Download credentials to `app/config/gmail_credentials.json`
3. On first run, the system will prompt you to authenticate
4. Authentication token will be stored in `app/config/gmail_token.json`
