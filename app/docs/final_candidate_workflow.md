# Final Candidate Selection and Offer Letter Process

This document describes the enhanced process for selecting the top candidates after interviews and sending offer letters.

## Overview

The system now implements an automatic workflow that:

1. During the stackranking process, automatically stores the top candidate in the `final_candidates` collection with a status of `selected`
2. When an offer is sent, updates the existing record with compensation details and changes status to `offered`
3. Handles the email delivery of offer letters with proper formatting

## Database Schema

The `final_candidates` collection uses the following schema:

```
{
  "candidate_name": "John Smith",
  "job_id": "job-123",
  "candidate_id": "candidate-456",
  "job_role": "Senior Data Scientist",
  "compensation_offered": "$120,000 per year",  // Empty until offer is sent
  "email": "john.smith@example.com",
  "total_score": 28,                           // Added automatically during stackranking
  "status": "selected" or "offered"            // "selected" during stackranking, "offered" when offer sent
}
```

## API Workflow

### Step 1: Stack Rank Candidates

```
GET /final-selection/stackrank/{job_id}
```

Here, `job_id` refers to the unique identifier of a job posting from the `jobs` collection in Firebase. This is the same ID that was created when the job posting was initially created through the `/jobs/` POST endpoint.

This endpoint automatically:
1. Filters candidates who have **complete interview feedback** (with both `rating_out_of_10` and `isSelectedForNextRound` values filled in for all rounds)
2. Calculates total scores by adding up all `rating_out_of_10` values
3. Sorts candidates by total score (descending)
4. **Stores the top candidate in the `final_candidates` collection** with:
   - Status: `selected`
   - Compensation: Empty string (to be filled later)
   - All candidate and job details
   - Total score from the ranking

### Step 2: Get Top Candidate (Optional)

```
GET /final-selection/top-candidate/{job_id}
```

This allows HR to review the top candidate before sending the offer.

### Step 3: Send Offer Letter

```
POST /final-selection/send-offer/{job_id}?compensation_offered=$120,000%20per%20year
```

This endpoint:
1. Finds the existing candidate record in `final_candidates` (created during stackranking)
2. Updates it with the compensation details
3. Changes the status from `selected` to `offered`
4. Generates and sends the offer letter email

### Step 4: Review Sent Offers (Optional)

```
GET /final-selection/offers/{job_id}
```

This returns all offers for a specific job, including their status and compensation details.

## Status Values

- `selected`: The candidate has been identified as the top candidate during stackranking but has not yet received an offer
- `offered`: An offer letter has been sent to the candidate with compensation details

## Example API Responses

### Stackranking Response

```json
[
  {
    "candidate_id": "candidate-123",
    "interview_candidate_id": "interview-456",
    "total_score": 28,
    "feedback": [...]
  },
  ...
]
```

### Final Candidate Response (After Offer)

```json
{
  "id": "fc-789",
  "candidate_name": "John Smith",
  "job_id": "job-123",
  "candidate_id": "candidate-456",
  "job_role": "Senior Data Scientist",
  "compensation_offered": "$120,000 per year",
  "email": "john.smith@example.com",
  "total_score": 28,
  "status": "offered"
}
