import os
import random
import string
from typing import List, Dict, Any, Optional
import datetime
import pickle
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Load environment variables
load_dotenv()

# Constants
SCOPES = ['https://www.googleapis.com/auth/calendar']
CREDENTIALS_FILE = os.environ.get('CALENDAR_CREDENTIALS_PATH', 'app/config/gmail_credentials.json')
TOKEN_FILE = os.environ.get('CALENDAR_TOKEN_PATH', 'app/config/calendar_token.pickle')

class CalendarService:
    """Service for interacting with Google Calendar API"""
    
    @staticmethod
    def get_calendar_service():
        """
        Get a service client for Google Calendar API using OAuth flow
        This matches the approach in the working-interview-scheduler
        """
        try:
            creds = None
            # Check if we have stored credentials
            if os.path.exists(TOKEN_FILE):
                with open(TOKEN_FILE, 'rb') as token:
                    creds = pickle.load(token)
            
            # If credentials don't exist or are invalid, get new ones
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not os.path.exists(CREDENTIALS_FILE):
                        print(f"Credentials file not found at {CREDENTIALS_FILE}")
                        raise FileNotFoundError(f"Calendar credentials file not found: {CREDENTIALS_FILE}")
                    
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                    creds = flow.run_local_server(port=0)
                    
                    # Save credentials for next time
                    with open(TOKEN_FILE, 'wb') as token:
                        pickle.dump(creds, token)
            
            service = build('calendar', 'v3', credentials=creds)
            return service
        except Exception as e:
            print(f"Error creating calendar service: {e}")
            raise
    
    @staticmethod
    def generate_meet_code():
        """
        Generate a Google Meet code in the standard format (xxx-xxxx-xxx) using only lowercase letters
        
        Returns:
            Google Meet code string
        """
        # Generate three groups of characters (3-4-3) as in Google Meet links
        # Using only lowercase letters (a-z) as per Google Meet format
        letters = string.ascii_lowercase  # Just lowercase letters a-z
        group1 = ''.join(random.choice(letters) for _ in range(3))
        group2 = ''.join(random.choice(letters) for _ in range(4))
        group3 = ''.join(random.choice(letters) for _ in range(3))
        
        # Combine with hyphens to match Google Meet format
        meet_code = f"{group1}-{group2}-{group3}"
        return meet_code
    
    @staticmethod
    def create_interview_event(
        summary: str, 
        description: str, 
        start_time: datetime.datetime, 
        end_time: datetime.datetime,
        attendees: List[Dict[str, str]] = None,
        location: str = "Google Meet",
        timezone: str = "Asia/Kolkata",
        use_specific_meet_link: Optional[str] = None  # Added parameter to specify a Meet link
    ) -> Dict[str, Any]:
        """
        Create an interview event in Google Calendar
        
        Args:
            summary: Title of the event
            description: Description of the event
            start_time: Start time of the event
            end_time: End time of the event
            attendees: List of attendees [{'email': 'person@example.com'}]
                       Note: Service accounts cannot send invites without Domain-Wide Delegation
            location: Location of the event
            timezone: Timezone for the event
            use_specific_meet_link: Optional specific Meet link to use (for consistency)
        
        Returns:
            Dict containing created event information
        """
        try:
            service = CalendarService.get_calendar_service()
                
            # Generate or use the provided Google Meet link
            if use_specific_meet_link:
                meet_link = use_specific_meet_link
            else:
                # Generate a Meet code and link
                meet_code = CalendarService.generate_meet_code()
                meet_link = f"https://meet.google.com/{meet_code}"
                
            # Create event with the Meet link in location and description
            event = {
                'summary': summary,
                'location': f"Google Meet: {meet_link}",
                'description': f"{description}\n\nJoin with Google Meet: {meet_link}",
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': timezone,
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': timezone,
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': 30},
                    ],
                },
            }
                
            # Only add attendees if explicitly requested (will only work with Domain-Wide Delegation)
            if attendees:
                event['attendees'] = attendees
            
            # Add conference data for Google Meet
            event['conferenceData'] = {
                'createRequest': {
                    'requestId': f"meet-{random.randint(1000000, 9999999)}",
                    'conferenceSolutionKey': {
                        'type': 'hangoutsMeet'
                    }
                }
            }
            
            # Add the event to the calendar with conference data
            try:
                event = service.events().insert(
                    calendarId='primary',  # Use primary calendar
                    body=event,
                    conferenceDataVersion=1  # Request Google Meet link
                ).execute()
                
                print(f"Calendar event created successfully")
                
                # Get the actual Meet link from the response
                if 'conferenceData' in event and 'entryPoints' in event['conferenceData']:
                    for entry_point in event['conferenceData']['entryPoints']:
                        if entry_point['entryPointType'] == 'video':
                            meet_link = entry_point['uri']
                            print(f"Google Meet link: {meet_link}")
                            break
                
                # Store our meet link in the event response
                event['manual_meet_link'] = meet_link
                
                return event
            except Exception as insert_error:
                print(f"Error inserting calendar event: {insert_error}")
                
                # If error is about attendees, remove them and retry
                if attendees and "Service accounts cannot invite attendees" in str(insert_error):
                    print("Removing attendees due to service account limitations")
                    if 'attendees' in event:
                        del event['attendees']
                    
                    # Try the insert again without attendees
                    event = service.events().insert(
                        calendarId='primary',  # Use primary calendar
                        body=event,
                        conferenceDataVersion=1
                    ).execute()
                    
                    print(f"Calendar event created successfully without attendees")
                    
                    # Get the actual Meet link from the response
                    if 'conferenceData' in event and 'entryPoints' in event['conferenceData']:
                        for entry_point in event['conferenceData']['entryPoints']:
                            if entry_point['entryPointType'] == 'video':
                                meet_link = entry_point['uri']
                                print(f"Google Meet link: {meet_link}")
                                break
                    
                    event['manual_meet_link'] = meet_link
                    
                    return event
                else:
                    # Re-raise other errors
                    raise
        except Exception as e:
            print(f"Error creating calendar event: {e}")
            # Raise the exception to be handled by the caller
            raise
    
    @staticmethod
    def get_events(
        time_min: Optional[datetime.datetime] = None,
        time_max: Optional[datetime.datetime] = None,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming events from the calendar
        
        Args:
            time_min: Start time for the query (default: now)
            time_max: End time for the query (optional)
            max_results: Maximum number of events to return
        
        Returns:
            List of events
        """
        try:
            service = CalendarService.get_calendar_service()
            
            # Default to now for time_min if not specified
            if not time_min:
                time_min = datetime.datetime.utcnow()
            
            # Query parameters
            params = {
                'calendarId': 'primary',  # Use primary calendar
                'timeMin': time_min.isoformat() + 'Z',  # 'Z' indicates UTC time
                'maxResults': max_results,
                'singleEvents': True,
                'orderBy': 'startTime',
            }
            
            # Add time_max if specified
            if time_max:
                params['timeMax'] = time_max.isoformat() + 'Z'
            
            # Execute the query
            events_result = service.events().list(**params).execute()
            events = events_result.get('items', [])
            
            return events
        except Exception as e:
            print(f"Error getting calendar events: {e}")
            # Return empty list as fallback
            return []
    
    @staticmethod
    def find_available_slot(
        duration_minutes: int = 60,
        start_date: Optional[datetime.datetime] = None,
        end_date: Optional[datetime.datetime] = None,
        working_hours: Dict[str, Any] = None
    ) -> Optional[Dict[str, datetime.datetime]]:
        """
        Find an available time slot for scheduling an interview
        
        Args:
            duration_minutes: Duration of the interview in minutes
            start_date: Start date to look for availability (default: today)
            end_date: End date to look for availability (default: 7 days from start_date)
            working_hours: Dictionary specifying working hours
                           e.g. {'start': 9, 'end': 17} for 9 AM to 5 PM
        
        Returns:
            Dictionary with start and end times of available slot, or None if no slot found
        """
        try:
            # Default values
            if not start_date:
                start_date = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            if not end_date:
                end_date = start_date + datetime.timedelta(days=7)
            
            if not working_hours:
                working_hours = {'start': 9, 'end': 17}  # 9 AM to 5 PM
            
            # Get existing events in the date range
            events = CalendarService.get_events(time_min=start_date, time_max=end_date, max_results=100)
            
            # Convert events to busy time slots
            busy_slots = []
            for event in events:
                start = event['start'].get('dateTime')
                end = event['end'].get('dateTime')
                
                if start and end:
                    # Parse dates and remove timezone info to avoid comparison issues
                    start_dt = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
                    start_dt = start_dt.replace(tzinfo=None)  # Remove timezone info
                    
                    end_dt = datetime.datetime.fromisoformat(end.replace('Z', '+00:00'))
                    end_dt = end_dt.replace(tzinfo=None)  # Remove timezone info
                    
                    busy_slots.append((start_dt, end_dt))
            
            # Sort busy slots by start time
            busy_slots.sort(key=lambda x: x[0])
            
            # Look for available slots day by day
            current_date = start_date
            while current_date < end_date:
                # Skip weekends
                if current_date.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
                    current_date += datetime.timedelta(days=1)
                    continue
                
                # Set working hours for the current day
                day_start = current_date.replace(
                    hour=working_hours['start'], minute=0, second=0, microsecond=0
                )
                day_end = current_date.replace(
                    hour=working_hours['end'], minute=0, second=0, microsecond=0
                )
                
                # Find available slots within working hours
                potential_slot_start = day_start
                while potential_slot_start < day_end:
                    potential_slot_end = potential_slot_start + datetime.timedelta(minutes=duration_minutes)
                    
                    # Check if slot is free
                    slot_is_free = True
                    for busy_start, busy_end in busy_slots:
                        # Check if there's an overlap
                        if (potential_slot_start < busy_end and potential_slot_end > busy_start):
                            slot_is_free = False
                            # Move potential slot to end of busy period
                            potential_slot_start = busy_end
                            break
                    
                    # If slot is free and within working hours, return it
                    if slot_is_free and potential_slot_end <= day_end:
                        return {
                            'start': potential_slot_start,
                            'end': potential_slot_end
                        }
                    
                    # If not free, try next slot (increment by 30 minutes)
                    if slot_is_free:
                        potential_slot_start += datetime.timedelta(minutes=30)
                
                # Move to next day
                current_date += datetime.timedelta(days=1)
            
            # No available slot found
            return None
        
        except Exception as e:
            print(f"Error finding available calendar slot: {e}")
            # Return a default slot tomorrow at 10 AM as fallback
            tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
            start = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
            end = start + datetime.timedelta(minutes=duration_minutes)
            return {'start': start, 'end': end}
    
    @staticmethod
    def delete_event(event_id: str) -> bool:
        """
        Delete a calendar event
        
        Args:
            event_id: ID of the event to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            service = CalendarService.get_calendar_service()
            service.events().delete(calendarId='primary', eventId=event_id).execute()
            print(f"Successfully deleted event {event_id}")
            return True
        except Exception as e:
            print(f"Error deleting calendar event: {e}")
            return False


# Alias for the create_interview_event method to maintain compatibility
def create_calendar_event(
    summary: str,
    description: str,
    start_time: str,
    end_time: str,
    location: str = "Google Meet",
    attendees: List[Dict[str, str]] = None,
    timezone: str = "Asia/Kolkata",
    calendar_id: str = "primary"  # Added calendar_id parameter with default
) -> Dict[str, Any]:
    """
    Create a calendar event for an interview - wrapper function for CalendarService.create_interview_event
    
    Args:
        summary: Title of the event
        description: Description of the event
        start_time: Start time of the event as ISO string
        end_time: End time of the event as ISO string
        location: Location of the event (default: Google Meet)
        attendees: List of attendees [{'email': 'person@example.com'}]
        timezone: Timezone for the event (default: Asia/Kolkata)
    
    Returns:
        Dict containing created event information
    """
    try:
        # Parse ISO strings to datetime objects
        if isinstance(start_time, str):
            start_dt = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00').replace(' ', 'T'))
        else:
            start_dt = start_time
            
        if isinstance(end_time, str):
            end_dt = datetime.datetime.fromisoformat(end_time.replace('Z', '+00:00').replace(' ', 'T'))
        else:
            end_dt = end_time
        
        # Create the calendar event
        return CalendarService.create_interview_event(
            summary=summary,
            description=description,
            start_time=start_dt,
            end_time=end_dt,
            location=location,
            attendees=attendees,
            timezone=timezone
        )
    except Exception as e:
        print(f"Error in create_calendar_event wrapper: {e}")
        # Re-raise the exception to be handled by the caller
        raise
