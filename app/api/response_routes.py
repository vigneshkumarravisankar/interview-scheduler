"""
Routes for handling interview response (accept/decline) and dashboard
"""
from fastapi import APIRouter, HTTPException, status, Query, Request
from fastapi.responses import HTMLResponse
from typing import Dict, Any, Optional

from app.utils.email_notification import load_responses, save_response
from app.services.interview_service import InterviewService

router = APIRouter(
    tags=["responses"],
    responses={404: {"description": "Not found"}},
)


@router.get("/api/respond", response_class=HTMLResponse)
async def respond_to_interview(
    id: str = Query(..., description="Response ID"),
    action: str = Query(..., description="Action to take (accept or decline)")
):
    """
    Endpoint to handle interview response (accept or decline)
    
    This route is accessed via the email links sent to candidates and interviewers
    """
    if not id or not action:
        return generate_error_html("Invalid request. Missing ID or action.")
    
    responses = load_responses()
    if id not in responses:
        return generate_error_html("Invalid response ID. This link may have expired.")
    
    response_data = responses[id]
    
    if action not in ["accept", "decline"]:
        return generate_error_html("Invalid action. Must be 'accept' or 'decline'.")
    
    # Update response status
    response_data['status'] = action
    response_data['response_time'] = True
    save_response(id, response_data)
    
    # Print notification to terminal for visibility
    print(f"\n🔔 NOTIFICATION: Interview {action.capitalize()}d")
    print(f"👤 Recipient: {response_data['recipient']}")
    print(f"⏰ Interview time: {response_data['start_time']} - {response_data['end_time']}")
    print(f"✅ Status: {action.capitalize()}d")
    if response_data.get('meet_link'):
        print(f"🔗 Meet link: {response_data['meet_link']}")
    print(f"📅 Event ID: {response_data.get('event_id', 'Not available')}\n")
    
    # If this response is tied to an interview candidate record, update it
    try:
        if 'event_id' in response_data and response_data['event_id']:
            # Find any interview candidates with this event ID
            all_candidates = InterviewService.get_all_interview_candidates()
            for candidate in all_candidates:
                feedback_list = candidate.get('feedback', [])
                for idx, feedback in enumerate(feedback_list):
                    # Check if this event is referenced in the feedback
                    scheduled_event = feedback.get("scheduled_event", {})
                    if scheduled_event.get("id") == response_data['event_id']:
                        # Find which person is responding (interviewer or candidate)
                        is_interviewer = response_data['recipient'] == feedback.get("interviewer_email")
                        
                        # Update the appropriate status
                        if is_interviewer:
                            feedback["interviewer_response"] = action
                        else:
                            feedback["candidate_response"] = action
                            
                            # Handle declines for candidate
                            if action == "decline":
                                # Initialize or increment the decline count
                                current_declines = feedback.get("declines_count", 0) + 1
                                feedback["declines_count"] = current_declines
                                
                                if current_declines > 1:
                                    # More than one decline - automatically reject the candidate
                                    feedback["isSelectedForNextRound"] = "no"
                                    feedback["auto_rejected"] = True
                                    feedback["rejection_reason"] = "Multiple interview declines"
                                    print(f"Candidate {candidate.get('id')} automatically rejected due to multiple declines")
                                else:
                                    # First decline - attempt to reschedule
                                    print(f"First decline for candidate {candidate.get('id')} - attempting to reschedule")
                                    
                                    # Get the job data
                                    job_id = candidate.get("job_id")
                                    if job_id:
                                        job_data = JobService.get_job_posting(job_id)
                                        if job_data:
                                            # Convert to dict for reschedule
                                            job_data_dict = {
                                                "job_id": job_data.job_id,
                                                "job_role_name": job_data.job_role_name,
                                                "job_description": job_data.job_description,
                                                "years_of_experience_needed": job_data.years_of_experience_needed
                                            }
                                            
                                            # Attempt to reschedule
                                            rescheduled = InterviewService.reschedule_interview(
                                                candidate['id'], 
                                                idx, 
                                                job_data_dict,
                                                tomorrow=True
                                            )
                                            
                                            if rescheduled:
                                                # Successfully rescheduled
                                                feedback["rescheduled"] = True
                                                print(f"Successfully rescheduled interview for candidate {candidate.get('id')}")
                                            else:
                                                print(f"Failed to reschedule interview for candidate {candidate.get('id')}")
                        
                        # Update the interview candidate
                        InterviewService.update_interview_candidate(candidate['id'], {'feedback': feedback_list})
                        break
    except Exception as e:
        print(f"Error updating interview candidate: {e}")
        # Don't return an error to the user, still show success page
    
    # Return HTML response
    if action == "accept":
        return generate_success_html(
            "Thank you for accepting the interview.",
            "Your response has been recorded. The interview has been confirmed.",
            response_data
        )
    else:
        return generate_success_html(
            "Interview declined.",
            "Your response has been recorded. The organizer will be notified.",
            response_data
        )


@router.get("/interviews/responses", response_class=HTMLResponse)
async def interview_responses_dashboard(request: Request):
    """Dashboard displaying all interview responses"""
    responses = load_responses()
    
    # Generate table rows outside the f-string to avoid complex nesting
    rows = []
    for resp_id, resp_data in responses.items():
        recipient = resp_data.get('recipient', 'Unknown')
        start_time = resp_data.get('start_time', 'Not specified')
        end_time = resp_data.get('end_time', 'Not specified')
        status = resp_data.get('status', 'pending')
        status_cap = status.capitalize()
        action = resp_data.get('action', 'Unknown')
        
        # Handle meet link display
        meet_link = resp_data.get('meet_link')
        if meet_link:
            meet_link_display = f'<a href="{meet_link}" target="_blank">{meet_link}</a>'
        else:
            meet_link_display = 'Not available'
        
        # Create row
        row = f"""
        <tr>
            <td>{recipient}</td>
            <td>{start_time}</td>
            <td>{end_time}</td>
            <td class="{status}">{status_cap}</td>
            <td>{action}</td>
            <td>{meet_link_display}</td>
        </tr>
        """
        rows.append(row)
    
    # Join all rows
    all_rows = "".join(rows)
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Interview Response Tracker</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1000px;
                margin: 0 auto;
                padding: 20px;
            }}
            .container {{
                background-color: #f9f9f9;
                border-radius: 5px;
                padding: 20px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
            }}
            h1, h2 {{
                color: #4285f4;
                border-bottom: 1px solid #eee;
                padding-bottom: 10px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th, td {{
                padding: 10px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }}
            th {{
                background-color: #f2f2f2;
            }}
            .accepted {{
                color: green;
                font-weight: bold;
            }}
            .declined {{
                color: red;
                font-weight: bold;
            }}
            .pending {{
                color: orange;
                font-weight: bold;
            }}
            .success {{
                color: #4CAF50;
                font-weight: bold;
            }}
            .details {{
                background-color: #fff;
                padding: 15px;
                border-radius: 5px;
                margin: 15px 0;
                border-left: 4px solid #4285f4;
            }}
            .refresh {{
                padding: 10px 20px;
                background-color: #4285f4;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
                margin-bottom: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Interview Response Tracker</h1>
            <p>This dashboard shows all responses to interview invitations.</p>
            
            <a href="/interviews/responses" class="refresh">🔄 Refresh Dashboard</a>
            
            <h2>Current Responses</h2>
            <table>
                <tr>
                    <th>Recipient</th>
                    <th>Start Time</th>
                    <th>End Time</th>
                    <th>Status</th>
                    <th>Action</th>
                    <th>Meet Link</th>
                </tr>
                {all_rows}
            </table>
            
            <div class="details">
                <h3>Test Response Links</h3>
                <p>Use these links to test the response functionality:</p>
                <ul>
                    <li><a href="/api/respond?id=test&action=accept">Test Accept</a></li>
                    <li><a href="/api/respond?id=test&action=decline">Test Decline</a></li>
                </ul>
                <p><b>Note:</b> The test links will only work if a 'test' response ID exists in the responses file.</p>
            </div>
            
            <p>The response server is integrated with the main FastAPI server, so you don't need to run a separate server.</p>
        </div>
        
        <script>
            // Auto-refresh every 60 seconds
            setTimeout(function() {{
                window.location.reload();
            }}, 60000);
        </script>
    </body>
    </html>
    """


@router.get("/api/schedule-next-round/{interview_candidate_id}")
async def schedule_next_round(interview_candidate_id: str):
    """
    Schedule the next interview round if the previous round was successful
    
    This endpoint checks if the previous round is completed with positive feedback,
    and schedules the next round if conditions are met.
    """
    result = InterviewService.schedule_next_round(interview_candidate_id)
    
    if result:
        return {"status": "success", "message": "Next interview round scheduled successfully"}
    else:
        return {"status": "error", "message": "Unable to schedule next round. Check logs for details."}


# Helper functions for HTML responses
def generate_success_html(title: str, message: str, data: Dict[str, Any]) -> str:
    """Generate HTML response for successful action"""
    meet_link = data.get('meet_link', '')
    meet_link_html = f"""
        <p><strong>Google Meet Link:</strong> <a href="{meet_link}" target="_blank">{meet_link}</a></p>
    """ if meet_link else ""
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Interview Response</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .container {{
                background-color: #f9f9f9;
                border-radius: 5px;
                padding: 20px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #4285f4;
                border-bottom: 1px solid #eee;
                padding-bottom: 10px;
            }}
            .details {{
                background-color: #fff;
                padding: 15px;
                border-radius: 5px;
                margin: 15px 0;
                border-left: 4px solid #4285f4;
            }}
            .success {{
                color: #4CAF50;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1 class="success">{title}</h1>
            <p>{message}</p>
            
            <div class="details">
                <p><strong>Start Time:</strong> {data.get('start_time', 'Not specified')}</p>
                <p><strong>End Time:</strong> {data.get('end_time', 'Not specified')}</p>
                {meet_link_html}
            </div>
            
            <p>This window will close automatically in a few seconds.</p>
            <p><a href="/interviews/responses">View All Responses</a></p>
        </div>
        
        <script>
            setTimeout(function() {{
                window.close();
            }}, 5000);
        </script>
    </body>
    </html>
    """


def generate_error_html(error_message: str) -> str:
    """Generate HTML response for error"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Error</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .container {{
                background-color: #f9f9f9;
                border-radius: 5px;
                padding: 20px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #f44336;
                border-bottom: 1px solid #eee;
                padding-bottom: 10px;
            }}
            .error {{
                color: #f44336;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Error</h1>
            <p class="error">{error_message}</p>
            <p>This window will close automatically in a few seconds.</p>
            <p><a href="/interviews/responses">Return to Response Tracker</a></p>
        </div>
        
        <script>
            setTimeout(function() {{
                window.close();
            }}, 5000);
        </script>
    </body>
    </html>
    """
