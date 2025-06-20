# calendar_api/oauth.py
import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from calendar_api.email_notification import send_interview_notification
 
SCOPES = ['https://www.googleapis.com/auth/calendar']
 
# 📧 Centralized participant emails
INTERVIEWER_EMAILS = [
    "rrvigneshkumar2002@gmail.com",
    "kldhanwanth@gmail.com"
]
CANDIDATE_EMAIL = "sathyaprathap2004@gmail.com"


def get_calendar_service():
    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(port=3000)
    service = build("calendar", "v3", credentials=creds)
    return service
 
def get_actual_busy_slots(service, calendar_id, start_time, end_time):
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_time,
        timeMax=end_time,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    busy_slots = []
    for event in events:
        busy_slots.append({
            'start': event['start'].get('dateTime'),
            'end': event['end'].get('dateTime')
        })
    return busy_slots

 
from calendar_api.oauth import INTERVIEWER_EMAILS, CANDIDATE_EMAIL

def create_event_with_fallback(service, time_slot, calendar_id="primary", max_retries=1):
    start, end = time_slot

    event = {
        'summary': 'Scheduled Interview',
        'description': 'Interview scheduled by the AI agent.',
        'start': {'dateTime': start, 'timeZone': 'UTC'},
        'end': {'dateTime': end, 'timeZone': 'UTC'},
        'conferenceData': {
            'createRequest': {
                'requestId': 'some-random-string',
                'conferenceSolutionKey': {'type': 'hangoutsMeet'}
            }
        },
        'attendees': [
            {'email': email} for email in INTERVIEWER_EMAILS + [CANDIDATE_EMAIL]
        ],
        'sendUpdates': 'all'
    }

    attempt = 0
    while attempt < max_retries:
        try:
            event_response = service.events().insert(
                calendarId=calendar_id,
                body=event,
                conferenceDataVersion=1
            ).execute()

            # ✅ Safely extract Meet link
            meet_link = None
            if 'conferenceData' in event_response and 'entryPoints' in event_response['conferenceData']:
                entry_points = event_response.get("conferenceData", {}).get("entryPoints", [])
                meet_link = next((ep["uri"] for ep in entry_points if ep["entryPointType"] == "video"), "N/A")

                print(f"📹 Google Meet link: {meet_link}")
            else:
                print("⚠️ Meet link not generated.")

            # 📧 Send email notifications
            for email in INTERVIEWER_EMAILS + [CANDIDATE_EMAIL]:
                send_interview_notification(email, start, end, meet_link or "No link")

            return event_response

        except Exception as e:
            print(f"⚠️ Failed to create event (attempt {attempt + 1}): {e}")
            attempt += 1

    print("❌ Failed to create event after all retry attempts.")
    return None

