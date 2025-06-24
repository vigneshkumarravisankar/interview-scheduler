"""
Automated Google Calendar Authentication
Attempts to authenticate automatically, falls back to guided manual process
"""

import os
import sys
import json
from pathlib import Path
from calendar_api.automated_oauth import get_authenticated_calendar_service, AutomatedOAuthManager

def check_existing_credentials():
    """Check if we have existing valid credentials"""
    print("🔍 Checking for existing credentials...")
    
    oauth_manager = AutomatedOAuthManager()
    
    # Check for stored token file
    if os.path.exists("token.pickle"):
        print("📁 Found stored token file")
        if oauth_manager.is_authenticated():
            print("✅ Existing credentials are valid!")
            return oauth_manager.get_calendar_service()
        else:
            print("⚠️ Stored credentials are expired or invalid")
    else:
        print("❌ No stored token file found")
    
    # Check for refresh token in environment
    refresh_token = os.getenv('GOOGLE_REFRESH_TOKEN')
    if refresh_token:
        print("🔄 Found refresh token in environment variables")
        if oauth_manager.authenticate_with_refresh_token(refresh_token):
            return oauth_manager.get_calendar_service()
        else:
            print("⚠️ Environment refresh token is invalid")
    else:
        print("❌ No refresh token found in environment variables")
    
    return None

def provide_manual_instructions():
    """Provide instructions for manual authentication"""
    print("\n" + "="*60)
    print("🔐 MANUAL AUTHENTICATION REQUIRED")
    print("="*60)
    
    oauth_manager = AutomatedOAuthManager()
    auth_url = oauth_manager.get_auth_url()
    
    if auth_url:
        print("📋 STEP-BY-STEP INSTRUCTIONS:")
        print("1. Copy and paste this URL into your browser:")
        print(f"   {auth_url}")
        print("\n2. Sign in with your Google account")
        print("3. Grant permissions to access your calendar")
        print("4. After granting permissions, you'll be redirected to a localhost URL")
        print("5. Copy the ENTIRE redirect URL from your browser's address bar")
        print("6. Run this command with the copied URL:")
        print(f"   python complete_oauth_flow.py \"<paste_the_full_callback_url_here>\"")
        print("\nExample callback URL:")
        print("   http://localhost:3000/?code=4/0AX4XfWh-abc123...")
        
        print("\n" + "="*60)
        print("🚀 QUICK SETUP COMMANDS:")
        print("="*60)
        print("# After getting the callback URL, run:")
        print(f"cd {os.getcwd()}")
        print("python complete_oauth_flow.py \"<your_callback_url>\"")
        
    else:
        print("❌ Error generating authorization URL")

def test_calendar_access(service):
    """Test calendar access with the authenticated service"""
    try:
        print("\n🧪 Testing calendar access...")
        
        # List calendars
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get('items', [])
        
        print(f"✅ Successfully connected to Google Calendar API!")
        print(f"📅 Found {len(calendars)} calendars:")
        
        for i, calendar in enumerate(calendars[:5], 1):  # Show first 5 calendars
            name = calendar.get('summary', 'Unknown')
            access_role = calendar.get('accessRole', 'Unknown')
            print(f"   {i}. {name} ({access_role})")
        
        if len(calendars) > 5:
            print(f"   ... and {len(calendars) - 5} more calendars")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing calendar access: {e}")
        return False

def main():
    """Main authentication function"""
    print("🚀 Google Calendar Auto-Authentication")
    print("="*50)
    
    # Change to the correct directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"📂 Working directory: {os.getcwd()}")
    
    # Try automatic authentication first
    service = check_existing_credentials()
    
    if service:
        print("🎉 Automatic authentication successful!")
        test_calendar_access(service)
        return service
    else:
        print("❌ Automatic authentication failed")
        provide_manual_instructions()
        return None

if __name__ == "__main__":
    main()
