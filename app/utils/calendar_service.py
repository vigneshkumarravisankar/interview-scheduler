import os
import random
import string
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from dateutil import parser
from dotenv import load_dotenv
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Load environment variables
load_dotenv()

# Constants
SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = os.environ.get('CALENDAR_SERVICE_ACCOUNT_PATH', 'app/config/calendar_service_account.json')
CREDENTIALS_FILE = os.environ.get('CREDENTIALS_FILE', 'app/renamer-scheduler-agent/credentials.json')

class CalendarService:
    """Service for interacting with Google Calendar API"""
    
    @staticmethod
    def get_calendar_service():
        """Get a service client for Google Calendar API using OAuth flow or service account"""
        try:
            # Try using OAuth flow (preferred for user-level access)
            if os.path.exists(CREDENTIALS_FILE):
                print(f"Using OAuth flow with credentials file: {CREDENTIALS_FILE}")
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                    creds = flow.run_local_server(port=3000)
                    service = build("calendar", "v3", credentials=creds)
                    return service
                except Exception as oauth_error:
                    print(f"OAuth flow failed: {oauth_error}. Falling back to service account.")
                
            # Fall back to service account (limited permissions)
            print(f"Using calendar service account file: {SERVICE_ACCOUNT_FILE}")
            if os.path.exists(SERVICE_ACCOUNT_FILE):
                credentials = service_account.Credentials.from_service_account_file(
                    SERVICE_ACCOUNT_FILE, scopes=SCOPES
                )
                service = build('calendar', 'v3', credentials=credentials)
                return service
            else:
                print(f"Calendar service account file not found at {SERVICE_ACCOUNT_FILE}")
                raise FileNotFoundError(f"No valid credentials found for calendar access")
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
        start_time: datetime, 
        end_time: datetime,
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
            # if attendees:
            #     # Format attendees properly
            #     formatted_attendees = []
            #     for attendee in attendees:
                    # if isinstance(attendee, str):
                    #     # If attendee is just a string (email), convert to proper format
                    #     formatted_attendees.append(attendee)
                    # elif isinstance(attendee, dict):
                    #     if "email" not in attendee:
                    #         # If dict but missing email field, skip this attendee
                    #         print(f"Warning: Attendee record missing email field: {attendee}")
                    #         continue
                    #     formatted_attendees.append(attendee)
                    # else:
                    #     print(f"Warning: Invalid attendee format: {attendee}")
                    #     continue
                #     formatted_attendees.append(attendee)
                
                # # Only add if we have valid attendees
                # if formatted_attendees:
                #     event['attendees'] = formatted_attendees
            
            valid_attendees = [
                attendee for attendee in attendees 
                if attendee.get('email') and isinstance(attendee['email'], str)
            ]

            # Only add attendees if there are valid ones
            if valid_attendees:
                event['attendees'] = valid_attendees
            
            # No conference data needed since we're using a pre-generated Meet link
            
            # Add the event to the calendar (no conference data)
            try:
                print("event: ",event)
                event = service.events().insert(
                    calendarId='primary',  # Use primary calendar
                    body=event
                ).execute()
                
                print(f"Calendar event created successfully with Meet link: {meet_link}")
                
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
                        body=event
                    ).execute()
                    
                    print(f"Calendar event created successfully without attendees")
                    
                    # Our Meet link is already generated and in the event
                    
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
    def get_actual_busy_slots(calendar_id="primary", start_time=None, end_time=None):
        """Get busy time slots for a calendar
        
        Args:
            calendar_id: Email address or calendar ID
            start_time: Start time as datetime or ISO string
            end_time: End time as datetime or ISO string
            
        Returns:
            List of busy slot dictionaries with start and end times
        """
        try:
            service = CalendarService.get_calendar_service()
            
            # Convert datetime objects to ISO strings if needed
            if isinstance(start_time, datetime):
                start_time = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            if isinstance(end_time, datetime):
                end_time = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
                
            # Execute the query    
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
                if 'start' in event and 'end' in event:
                    busy_slots.append({
                        'start': event['start'].get('dateTime'),
                        'end': event['end'].get('dateTime')
                    })
            return busy_slots
        except Exception as e:
            print(f"Error getting busy slots: {e}")
            return []
    
    @staticmethod
    def generate_time_slots(start_time_str, end_time_str, slot_duration_minutes=30):
        """Generate time slots within a time range
        
        Args:
            start_time_str: Start time as datetime object or ISO string
            end_time_str: End time as datetime object or ISO string
            slot_duration_minutes: Duration of each slot in minutes
            
        Returns:
            List of time slot tuples (start, end)
        """
        # Convert to datetime objects if strings are provided
        if isinstance(start_time_str, str):
            start_dt = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        else:
            start_dt = start_time_str
            
        if isinstance(end_time_str, str):
            end_dt = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
        else:
            end_dt = end_time_str

        slots = []
        current = start_dt
        while current + timedelta(minutes=slot_duration_minutes) <= end_dt:
            slot_start = current
            slot_end = current + timedelta(minutes=slot_duration_minutes)
            slots.append((slot_start, slot_end))
            current += timedelta(minutes=slot_duration_minutes)

        return slots
    
    @staticmethod
    def compute_bitmasks(busy_times_list, time_slots):
        """Compute availability bitmasks based on busy times
        
        Args:
            busy_times_list: List of lists containing busy time dictionaries
            time_slots: List of time slot tuples (start, end)
            
        Returns:
            List of bitmasks (lists of 0/1 indicating busy/free)
        """
        bitmasks = []

        for busy_times in busy_times_list:
            bitmask = []
            for slot_start, slot_end in time_slots:
                # Slot times are datetime objects
                is_busy = False
                for busy in busy_times:
                    # Parse busy times if they're strings
                    if isinstance(busy["start"], str):
                        busy_start = parser.isoparse(busy["start"]).replace(tzinfo=timezone.utc)
                    else:
                        busy_start = busy["start"].replace(tzinfo=timezone.utc)
                        
                    if isinstance(busy["end"], str):
                        busy_end = parser.isoparse(busy["end"]).replace(tzinfo=timezone.utc)
                    else:
                        busy_end = busy["end"].replace(tzinfo=timezone.utc)
                        
                    # Add timezone info if not present
                    if slot_start.tzinfo is None:
                        slot_start = slot_start.replace(tzinfo=timezone.utc)
                    if slot_end.tzinfo is None:
                        slot_end = slot_end.replace(tzinfo=timezone.utc)

                    # Check overlap
                    if slot_start < busy_end and slot_end > busy_start:
                        is_busy = True
                        break

                bitmask.append(0 if is_busy else 1)
            bitmasks.append(bitmask)
        
        return bitmasks
    
    @staticmethod
    def secure_bitmask_intersection(bitmasks):
        """Find common available slots using bitmask intersection
        
        Args:
            bitmasks: List of bitmasks (lists of 0/1)
            
        Returns:
            List with intersection result (1 = free in all calendars)
        """
        if not bitmasks or len(bitmasks) == 0:
            return []
            
        length = len(bitmasks[0])
        intersection = [1] * length
        for mask in bitmasks:
            for i in range(length):
                intersection[i] = intersection[i] & mask[i]
        return intersection
    
    @staticmethod
    def find_first_available_slot(bitmask, time_slots):
        """Find the first available slot in a bitmask
        
        Args:
            bitmask: List of 0/1 indicating busy/free
            time_slots: List of time slot tuples (start, end)
            
        Returns:
            Tuple (start, end) of available slot or None
        """
        for i, val in enumerate(bitmask):
            if val == 1 and i < len(time_slots):
                return time_slots[i]
        return None
    
    @staticmethod
    def get_events(
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
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
                time_min = datetime.utcnow()
            
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
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        working_hours: Dict[str, Any] = None
    ) -> Optional[Dict[str, datetime]]:
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
                start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            if not end_date:
                end_date = start_date + timedelta(days=7)
            
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
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    start_dt = start_dt.replace(tzinfo=None)  # Remove timezone info
                    
                    end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                    end_dt = end_dt.replace(tzinfo=None)  # Remove timezone info
                    
                    busy_slots.append((start_dt, end_dt))
            
            # Sort busy slots by start time
            busy_slots.sort(key=lambda x: x[0])
            
            # Look for available slots day by day
            current_date = start_date
            while current_date < end_date:
                # Skip weekends
                if current_date.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
                    current_date += timedelta(days=1)
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
                    potential_slot_end = potential_slot_start + timedelta(minutes=duration_minutes)
                    
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
                        potential_slot_start += timedelta(minutes=30)
                
                # Move to next day
                current_date += timedelta(days=1)
            
            # No available slot found
            return None
        
        except Exception as e:
            print(f"Error finding available calendar slot: {e}")
            # Return a default slot tomorrow at 10 AM as fallback
            tomorrow = datetime.now() + timedelta(days=1)
            start = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
            end = start + timedelta(minutes=duration_minutes)
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
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00').replace(' ', 'T'))
        else:
            start_dt = start_time
            
        if isinstance(end_time, str):
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00').replace(' ', 'T'))
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
