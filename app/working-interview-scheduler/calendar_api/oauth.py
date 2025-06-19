# calendar_api/oauth.py
import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from calendar_api.email_notification import send_interview_notification

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(port=3000)
    service = build("calendar", "v3", credentials=creds)
    return service

def get_free_busy(service, start_time, end_time, calendar_id='primary'):
    body = {
        "timeMin": start_time,
        "timeMax": end_time,
        "timeZone": "UTC",
        "items": [{"id": calendar_id}]
    }
    events_result = service.freebusy().query(body=body).execute()
    busy_times = events_result['calendars'][calendar_id]['busy']
    return busy_times

def create_event_with_fallback(service, time_slot, calendar_id="primary", max_retries=1):
    start, end = time_slot

    # Define attendees
    interviewer_email1 = "rvkvigneshkumar02@gmail.com"
    interviewer_email2 = "sathyaprathap2004@gmail.com"
    candidate_email = "kldhanwanth@gmail.com"

    event = {
        'summary': 'Scheduled Interview',
        'description': 'Interview scheduled by the AI agent.',
        'start': {'dateTime': start, 'timeZone': 'UTC'},
        'end': {'dateTime': end, 'timeZone': 'UTC'},
        'conferenceData': {
            'createRequest': {
                'requestId': 'some-random-string',
                'conferenceSolutionKey': {
                    'type': 'hangoutsMeet'
                }
            }
        },
        'attendees': [
            {'email': interviewer_email1},
            {'email': interviewer_email2},
            {'email': candidate_email}
        ],
        'sendUpdates': 'all'  # This will send calendar notifications to attendees
    }

    attempt = 0
    while attempt < max_retries:
        try:
            event_response = service.events().insert(
                calendarId=calendar_id,
                body=event,
                conferenceDataVersion=1
            ).execute()
            meet_link = event_response['conferenceData']['entryPoints'][0]['uri']
            print(f"📹 Google Meet link: {meet_link}")

            # Send email notifications with accept/decline options
            send_interview_notification(interviewer_email1, start, end, meet_link)
            send_interview_notification(interviewer_email2, start, end, meet_link)
            send_interview_notification(candidate_email, start, end, meet_link)

            print("\n⚠️ IMPORTANT: Run the response server to handle accept/decline responses:")
            print("python -m calendar_api.response_server\n")

            return event_response
        except Exception as e:
            print(f"⚠️ Failed to create event (attempt {attempt + 1}): {e}")
            attempt += 1

    print("❌ Failed to create event after all retry attempts.")
    return None