"""
Calendar MCP Server for Interview Scheduling

This MCP server provides tools for working with Google Calendar:
- Finding available time slots
- Scheduling interviews
- Rescheduling interviews
- Checking calendar availability
- Sending calendar invites

Run with: python calendar-mcp-server.py
"""
import os
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import random
import string
import pytz

# Configuration
MCP_SERVER_PORT = 8501
CALENDAR_CREDENTIALS_PATH = 'app/config/calendar_service_account.json'
CALENDAR_TOKEN_PATH = 'app/config/calendar_token.json'
CALENDAR_SCOPES = ['https://www.googleapis.com/auth/calendar']
DEFAULT_CALENDAR_ID = "primary"  # Use primary calendar by default

# Create FastAPI app
app = FastAPI(
    title="Calendar MCP Server",
    description="MCP Server for Google Calendar operations",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CalendarCredentials:
    @staticmethod
    def get_credentials():
        """Get Google Calendar credentials"""
        creds = None
        
        # First check if we have a token.pickle file with credentials
        if os.path.exists(CALENDAR_TOKEN_PATH):
            try:
                with open(CALENDAR_TOKEN_PATH, 'rb') as token:
                    creds = pickle.load(token)
            except Exception as e:
                print(f"Error loading calendar token: {e}")
                
        # If no valid credentials, get them
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing credentials: {e}")
                    creds = None
                    
            # If refresh failed or no credentials, use flow
            if not creds:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        CALENDAR_CREDENTIALS_PATH,
                        CALENDAR_SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                    
                except Exception as e:
                    print(f"Error creating new credentials: {e}")
                    return None
                
            # Save the credentials for next time
            try:
                with open(CALENDAR_TOKEN_PATH, 'wb') as token:
                    pickle.dump(creds, token)
            except Exception as e:
                print(f"Error saving credentials: {e}")
        
        return creds

def get_calendar_service():
    """Get an authorized Google Calendar API service instance"""
    try:
        creds = CalendarCredentials.get_credentials()
        if not creds:
            raise Exception("Failed to obtain calendar credentials")
            
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        print(f"Error building calendar service: {e}")
        return None

def generate_meet_code():
    """Generate a Google Meet code"""
    # Generate three parts: xxx-xxxx-xxx
    part1 = ''.join(random.choices(string.ascii_lowercase, k=3))
    part2 = ''.join(random.choices(string.ascii_lowercase, k=4))
    part3 = ''.join(random.choices(string.ascii_lowercase, k=3))
    return f"{part1}-{part2}-{part3}"

# ----- MCP Tool Functions -----

def list_calendars():
    """List available calendars"""
    try:
        service = get_calendar_service()
        if not service:
            return {"error": "Failed to get calendar service"}
            
        # Get the list of calendars
        calendar_list = service.calendarList().list().execute()
        
        # Extract relevant info
        calendars = []
        for calendar in calendar_list.get('items', []):
            calendars.append({
                'id': calendar['id'],
                'summary': calendar['summary'],
                'description': calendar.get('description', ''),
                'primary': calendar.get('primary', False)
            })
            
        return {"calendars": calendars}
    except Exception as e:
        return {"error": f"Error listing calendars: {e}"}
        
def find_available_slots(
    start_date: str,
    end_date: str,
    min_duration_minutes: int = 60,
    calendar_ids: List[str] = None,
    time_zone: str = "Asia/Kolkata",
    start_time_hour: int = 9,
    end_time_hour: int = 18
):
    """Find available time slots in specified calendars"""
    try:
        service = get_calendar_service()
        if not service:
            return {"error": "Failed to get calendar service"}
        
        # Default to primary calendar if none provided
        if not calendar_ids:
            calendar_ids = [DEFAULT_CALENDAR_ID]
            
        # Parse dates and set timezone
        tz = pytz.timezone(time_zone)
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00')).astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00')).astimezone(tz).replace(hour=23, minute=59, second=59, microsecond=0)
        
        # Get the current date in the specified timezone
        current_dt = datetime.now(tz)
        
        # Adjust start_dt to be at least the current date
        if start_dt < current_dt:
            start_dt = current_dt
        
        # List to store available slots
        available_slots = []
        
        # Iterate through each day
        current_day = start_dt
        while current_day <= end_dt:
            # Define working hours for this day
            day_start = current_day.replace(hour=start_time_hour, minute=0, second=0, microsecond=0)
            day_end = current_day.replace(hour=end_time_hour, minute=0, second=0, microsecond=0)
            
            # If current_day is today and it's already after start_time_hour,
            # adjust day_start to next round hour from current time
            if current_day.date() == current_dt.date() and current_dt.hour >= start_time_hour:
                # Round to next hour
                if current_dt.minute > 0 or current_dt.second > 0:
                    day_start = current_dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                else:
                    day_start = current_dt.replace(minute=0, second=0, microsecond=0)
            
            # Skip if day_start is already past day_end
            if day_start >= day_end:
                current_day = current_day + timedelta(days=1)
                continue
            
            # Get busy periods for all calendars
            busy_periods = []
            for calendar_id in calendar_ids:
                try:
                    # Create time range for freebusy query
                    time_min = day_start.isoformat()
                    time_max = day_end.isoformat()
                    
                    body = {
                        "timeMin": time_min,
                        "timeMax": time_max,
                        "timeZone": time_zone,
                        "items": [{"id": calendar_id}]
                    }
                    
                    # Make the freebusy query
                    freebusy = service.freebusy().query(body=body).execute()
                    
                    # Add busy periods to list
                    calendar_busy = freebusy['calendars'][calendar_id]['busy']
                    for period in calendar_busy:
                        start = datetime.fromisoformat(period['start'].replace('Z', '+00:00')).astimezone(tz)
                        end = datetime.fromisoformat(period['end'].replace('Z', '+00:00')).astimezone(tz)
                        busy_periods.append((start, end))
                except Exception as e:
                    print(f"Error getting freebusy for calendar {calendar_id}: {e}")
                    continue
            
            # Sort busy periods by start time
            busy_periods.sort(key=lambda x: x[0])
            
            # Merge overlapping busy periods
            merged_busy = []
            for period in busy_periods:
                if not merged_busy or period[0] > merged_busy[-1][1]:
                    merged_busy.append(period)
                else:
                    merged_busy[-1] = (merged_busy[-1][0], max(merged_busy[-1][1], period[1]))
            
            # Find free periods
            free_periods = []
            current_time = day_start
            
            # Add free periods between busy periods
            for busy_start, busy_end in merged_busy:
                if current_time < busy_start:
                    free_periods.append((current_time, busy_start))
                current_time = busy_end
            
            # Add final free period if needed
            if current_time < day_end:
                free_periods.append((current_time, day_end))
            
            # Filter free periods by minimum duration
            min_duration = timedelta(minutes=min_duration_minutes)
            valid_free_periods = [period for period in free_periods if period[1] - period[0] >= min_duration]
            
            # Add valid slots to available_slots
            for start, end in valid_free_periods:
                # Create 1-hour slots within each free period
                slot_start = start
                while slot_start + min_duration <= end:
                    slot_end = min(slot_start + min_duration, end)
                    
                    # Add slot
                    available_slots.append({
                        "start": slot_start.isoformat(),
                        "end": slot_end.isoformat(),
                        "duration_minutes": int((slot_end - slot_start).total_seconds() / 60)
                    })
                    
                    # Move to next potential slot
                    slot_start = slot_end
            
            # Move to next day
            current_day = current_day + timedelta(days=1)
        
        return {
            "available_slots": available_slots,
            "total_slots": len(available_slots),
            "time_zone": time_zone
        }
    except Exception as e:
        return {"error": f"Error finding available slots: {e}"}

def create_calendar_event(
    summary: str,
    start_time: str,
    end_time: str,
    description: str = None,
    location: str = None,
    attendees: List[Dict[str, str]] = None,
    calendar_id: str = None,
    send_notifications: bool = True
):
    """Create a calendar event with optional Google Meet link"""
    try:
        service = get_calendar_service()
        if not service:
            return {"error": "Failed to get calendar service"}
        
        # Use primary calendar if none specified
        if not calendar_id:
            calendar_id = DEFAULT_CALENDAR_ID
        
        # Create the event body
        event = {
            'summary': summary,
            'start': {
                'dateTime': start_time,
                'timeZone': 'Asia/Kolkata',  # Default timezone
            },
            'end': {
                'dateTime': end_time,
                'timeZone': 'Asia/Kolkata',  # Default timezone
            },
            'conferenceData': {
                'createRequest': {
                    'requestId': f"meet-{uuid.uuid4().hex}",
                    'conferenceSolutionKey': {
                        'type': 'hangoutsMeet'
                    }
                }
            }
        }
        
        # Add description if provided
        if description:
            event['description'] = description
            
        # Add location if provided
        if location:
            event['location'] = location
            
        # Add attendees if provided
        if attendees:
            event['attendees'] = attendees
        
        # Create the event
        event = service.events().insert(
            calendarId=calendar_id,
            conferenceDataVersion=1,  # To get conference data in the response
            body=event,
            sendUpdates='all' if send_notifications else 'none'
        ).execute()
        
        # Extract key information
        result = {
            'id': event['id'],
            'summary': event['summary'],
            'start': event['start'],
            'end': event['end'],
            'htmlLink': event['htmlLink']
        }
        
        # Add conference data if available
        if 'conferenceData' in event and 'entryPoints' in event['conferenceData']:
            meet_link = None
            for entry_point in event['conferenceData']['entryPoints']:
                if entry_point['entryPointType'] == 'video':
                    meet_link = entry_point['uri']
                    break
            
            if meet_link:
                result['meet_link'] = meet_link
        
        # Add attendees if available
        if 'attendees' in event:
            result['attendees'] = event['attendees']
        
        return result
    except Exception as e:
        return {"error": f"Error creating calendar event: {e}"}

def reschedule_calendar_event(
    event_id: str,
    new_start_time: str,
    new_end_time: str,
    calendar_id: str = None,
    send_notifications: bool = True
):
    """Reschedule an existing calendar event"""
    try:
        service = get_calendar_service()
        if not service:
            return {"error": "Failed to get calendar service"}
        
        # Use primary calendar if none specified
        if not calendar_id:
            calendar_id = DEFAULT_CALENDAR_ID
        
        # Get the existing event
        try:
            event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        except HttpError as e:
            return {"error": f"Event not found: {e}"}
        
        # Update the start and end times
        event['start'] = {
            'dateTime': new_start_time,
            'timeZone': event['start'].get('timeZone', 'Asia/Kolkata')
        }
        event['end'] = {
            'dateTime': new_end_time,
            'timeZone': event['end'].get('timeZone', 'Asia/Kolkata')
        }
        
        # Update the event
        updated_event = service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event,
            sendUpdates='all' if send_notifications else 'none'
        ).execute()
        
        # Extract key information
        result = {
            'id': updated_event['id'],
            'summary': updated_event['summary'],
            'start': updated_event['start'],
            'end': updated_event['end'],
            'htmlLink': updated_event['htmlLink'],
            'status': 'rescheduled'
        }
        
        # Add conference data if available
        if 'conferenceData' in updated_event and 'entryPoints' in updated_event['conferenceData']:
            meet_link = None
            for entry_point in updated_event['conferenceData']['entryPoints']:
                if entry_point['entryPointType'] == 'video':
                    meet_link = entry_point['uri']
                    break
            
            if meet_link:
                result['meet_link'] = meet_link
        
        # Add attendees if available
        if 'attendees' in updated_event:
            result['attendees'] = updated_event['attendees']
        
        return result
    except Exception as e:
        return {"error": f"Error rescheduling calendar event: {e}"}

def cancel_calendar_event(
    event_id: str,
    calendar_id: str = None,
    send_notifications: bool = True
):
    """Cancel/delete a calendar event"""
    try:
        service = get_calendar_service()
        if not service:
            return {"error": "Failed to get calendar service"}
        
        # Use primary calendar if none specified
        if not calendar_id:
            calendar_id = DEFAULT_CALENDAR_ID
        
        # Delete the event
        service.events().delete(
            calendarId=calendar_id,
            eventId=event_id,
            sendUpdates='all' if send_notifications else 'none'
        ).execute()
        
        return {
            'id': event_id,
            'calendar_id': calendar_id,
            'status': 'cancelled'
        }
    except Exception as e:
        return {"error": f"Error cancelling calendar event: {e}"}


# ----- Define the MCP Tool schemas -----

class ListCalendarsSchema(BaseModel):
    """MCP tool schema for listing calendars"""
    pass

class FindAvailableSlotsSchema(BaseModel):
    """MCP tool schema for finding available slots"""
    start_date: str = Field(..., description="Start date in ISO format (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date in ISO format (YYYY-MM-DD)")
    min_duration_minutes: int = Field(60, description="Minimum duration in minutes")
    calendar_ids: List[str] = Field(None, description="List of calendar IDs to check")
    time_zone: str = Field("Asia/Kolkata", description="Timezone for the slots")
    start_time_hour: int = Field(9, description="Starting hour of the workday (0-23)")
    end_time_hour: int = Field(18, description="Ending hour of the workday (0-23)")

class CreateCalendarEventSchema(BaseModel):
    """MCP tool schema for creating a calendar event"""
    summary: str = Field(..., description="Event summary/title")
    start_time: str = Field(..., description="Start time in ISO format")
    end_time: str = Field(..., description="End time in ISO format")
    description: str = Field(None, description="Event description")
    location: str = Field(None, description="Event location")
    attendees: List[Dict[str, str]] = Field(None, description="List of attendees")
    calendar_id: str = Field(None, description="Calendar ID")
    send_notifications: bool = Field(True, description="Whether to send notifications")

class RescheduleCalendarEventSchema(BaseModel):
    """MCP tool schema for rescheduling a calendar event"""
    event_id: str = Field(..., description="Event ID")
    new_start_time: str = Field(..., description="New start time in ISO format")
    new_end_time: str = Field(..., description="New end time in ISO format")
    calendar_id: str = Field(None, description="Calendar ID")
    send_notifications: bool = Field(True, description="Whether to send notifications")

class CancelCalendarEventSchema(BaseModel):
    """MCP tool schema for cancelling a calendar event"""
    event_id: str = Field(..., description="Event ID")
    calendar_id: str = Field(None, description="Calendar ID")
    send_notifications: bool = Field(True, description="Whether to send notifications")

# ----- Define MCP routes -----

@app.get("/mcp/info")
async def mcp_info():
    """Return information about the MCP server"""
    return {
        "name": "calendar",
        "description": "MCP Server for Google Calendar operations",
        "tools": [
            {
                "name": "list_calendars",
                "description": "List available Google calendars",
                "input_schema": ListCalendarsSchema.schema()
            },
            {
                "name": "find_available_slots",
                "description": "Find available time slots in calendars",
                "input_schema": FindAvailableSlotsSchema.schema()
            },
            {
                "name": "create_calendar_event",
                "description": "Create a calendar event with optional Google Meet link",
                "input_schema": CreateCalendarEventSchema.schema()
            },
            {
                "name": "reschedule_calendar_event",
                "description": "Reschedule an existing calendar event",
                "input_schema": RescheduleCalendarEventSchema.schema()
            },
            {
                "name": "cancel_calendar_event",
                "description": "Cancel/delete a calendar event",
                "input_schema": CancelCalendarEventSchema.schema()
            }
        ],
        "resources": []
    }

@app.post("/mcp/tools/list_calendars")
async def mcp_list_calendars():
    """List available calendars"""
    result = list_calendars()
    return result

@app.post("/mcp/tools/find_available_slots")
async def mcp_find_available_slots(params: FindAvailableSlotsSchema):
    """Find available time slots in calendars"""
    result = find_available_slots(
        start_date=params.start_date,
        end_date=params.end_date,
        min_duration_minutes=params.min_duration_minutes,
        calendar_ids=params.calendar_ids,
        time_zone=params.time_zone,
        start_time_hour=params.start_time_hour,
        end_time_hour=params.end_time_hour
    )
    return result

@app.post("/mcp/tools/create_calendar_event")
async def mcp_create_calendar_event(params: CreateCalendarEventSchema):
    """Create a calendar event with optional Google Meet link"""
    result = create_calendar_event(
        summary=params.summary,
        start_time=params.start_time,
        end_time=params.end_time,
        description=params.description,
        location=params.location,
        attendees=params.attendees,
        calendar_id=params.calendar_id,
        send_notifications=params.send_notifications
    )
    return result

@app.post("/mcp/tools/reschedule_calendar_event")
async def mcp_reschedule_calendar_event(params: RescheduleCalendarEventSchema):
    """Reschedule an existing calendar event"""
    result = reschedule_calendar_event(
        event_id=params.event_id,
        new_start_time=params.new_start_time,
        new_end_time=params.new_end_time,
        calendar_id=params.calendar_id,
        send_notifications=params.send_notifications
    )
    return result

@app.post("/mcp/tools/cancel_calendar_event")
async def mcp_cancel_calendar_event(params: CancelCalendarEventSchema):
    """Cancel/delete a calendar event"""
    result = cancel_calendar_event(
        event_id=params.event_id,
        calendar_id=params.calendar_id,
        send_notifications=params.send_notifications
    )
    return result

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Calendar MCP Server is running",
        "endpoints": {
            "MCP Info": "/mcp/info",
            "List Calendars": "/mcp/tools/list_calendars",
            "Find Available Slots": "/mcp/tools/find_available_slots",
            "Create Calendar Event": "/mcp/tools/create_calendar_event",
            "Reschedule Calendar Event": "/mcp/tools/reschedule_calendar_event",
            "Cancel Calendar Event": "/mcp/tools/cancel_calendar_event"
        }
    }

if __name__ == "__main__":
    print(f"Starting Calendar MCP Server on port {MCP_SERVER_PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=MCP_SERVER_PORT)
