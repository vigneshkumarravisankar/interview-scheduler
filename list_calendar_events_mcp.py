"""
Script to list all calendar events using Calendar MCP Server
"""
import requests
import datetime
from datetime import timedelta
from pprint import pprint
import json

# MCP Server URL
MCP_SERVER_URL = "http://localhost:8501"

def list_available_calendars():
    """List all available calendars using MCP"""
    try:
        response = requests.post(f"{MCP_SERVER_URL}/mcp/tools/list_calendars")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error listing calendars: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error connecting to MCP server: {e}")
        return None

def list_events_for_calendar(calendar_id=None, max_days=30):
    """List all events for a calendar within the next N days"""
    try:
        # Calculate date range (today to N days ahead)
        today = datetime.datetime.now()
        end_date = today + timedelta(days=max_days)
        
        # Format dates for the API
        start_date_str = today.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        # Find available slots (which gives us events)
        payload = {
            "start_date": start_date_str,
            "end_date": end_date_str,
            "min_duration_minutes": 15  # Small duration to get most events
        }
        
        # Add calendar_id if specified
        if calendar_id:
            payload["calendar_ids"] = [calendar_id]
        
        response = requests.post(
            f"{MCP_SERVER_URL}/mcp/tools/find_available_slots", 
            json=payload
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error listing events: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"Error connecting to MCP server: {e}")
        return None

def main():
    """Main function to list all calendar events"""
    print("Fetching calendars and events using Calendar MCP Server...")
    
    # First, list available calendars
    calendars_result = list_available_calendars()
    
    if not calendars_result or "error" in calendars_result:
        print("Failed to get calendar list.")
        if calendars_result and "error" in calendars_result:
            print(f"Error: {calendars_result['error']}")
        return
    
    # Print calendar info
    if "calendars" in calendars_result:
        calendars = calendars_result["calendars"]
        print(f"Found {len(calendars)} calendars:")
        for i, calendar in enumerate(calendars, 1):
            print(f"{i}. {calendar['summary']} ({calendar['id']})")
            print(f"   {'Primary' if calendar.get('primary') else 'Secondary'} calendar")
            print(f"   Description: {calendar.get('description', 'No description')}")
            print("-" * 50)
        
        # For each calendar, list events
        for calendar in calendars:
            calendar_id = calendar["id"]
            calendar_name = calendar["summary"]
            
            print(f"\nEvents for calendar: {calendar_name}")
            print("=" * 60)
            
            events_result = list_events_for_calendar(calendar_id)
            
            if not events_result or "error" in events_result:
                print(f"Failed to get events for calendar {calendar_name}")
                if events_result and "error" in events_result:
                    print(f"Error: {events_result['error']}")
                continue
                
            # Process available_slots to determine busy periods
            if "available_slots" in events_result:
                slots = events_result["available_slots"]
                print(f"Found {events_result['total_slots']} available time slots out of the requested time period.")
                print("This means the following times are likely booked with events:")
                
                # Since we only have available slots, we need to infer busy times
                if len(slots) > 0:
                    # Sort slots by start time
                    slots.sort(key=lambda x: x["start"])
                    
                    # Check for gaps between slots which would indicate events
                    for i in range(len(slots) - 1):
                        current_end = datetime.datetime.fromisoformat(slots[i]["end"].replace('Z', '+00:00'))
                        next_start = datetime.datetime.fromisoformat(slots[i+1]["start"].replace('Z', '+00:00'))
                        
                        if (next_start - current_end).total_seconds() > 60:  # If gap is more than 1 minute
                            event_start = current_end.strftime("%A, %B %d, %Y at %I:%M %p")
                            event_end = next_start.strftime("%I:%M %p")
                            duration_mins = int((next_start - current_end).total_seconds() / 60)
                            
                            print(f"Busy from {event_start} to {event_end} ({duration_mins} minutes)")
                else:
                    print("No available slots found, which could mean either:")
                    print("1. The calendar is completely booked")
                    print("2. The calendar has no events scheduled")
            else:
                print("No schedule information available")
    else:
        print("No calendars found")

if __name__ == "__main__":
    main()
