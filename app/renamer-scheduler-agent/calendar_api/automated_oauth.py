"""
Automated OAuth Authentication for Google Calendar API
Handles OAuth flow without manual browser intervention
"""

import os
import json
import pickle
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import requests
import urllib.parse
from datetime import datetime, timedelta

class AutomatedOAuthManager:
    def __init__(self, credentials_file="credentials.json", token_file="token.pickle"):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.scopes = ['https://www.googleapis.com/auth/calendar']
        self.creds = None
        
    def get_stored_credentials(self):
        """Load stored credentials from pickle file"""
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, 'rb') as token:
                    self.creds = pickle.load(token)
                print("✅ Loaded stored credentials")
                return True
            except Exception as e:
                print(f"⚠️ Error loading stored credentials: {e}")
                return False
        return False
    
    def refresh_credentials(self):
        """Refresh expired credentials"""
        if self.creds and self.creds.expired and self.creds.refresh_token:
            try:
                self.creds.refresh(Request())
                self.save_credentials()
                print("✅ Credentials refreshed successfully")
                return True
            except Exception as e:
                print(f"⚠️ Error refreshing credentials: {e}")
                return False
        return False
    
    def save_credentials(self):
        """Save credentials to pickle file"""
        try:
            with open(self.token_file, 'wb') as token:
                pickle.dump(self.creds, token)
            print("✅ Credentials saved successfully")
        except Exception as e:
            print(f"⚠️ Error saving credentials: {e}")
    
    def create_credentials_from_code(self, auth_code):
        """Create credentials from authorization code"""
        try:
            # Load client secrets
            with open(self.credentials_file, 'r') as f:
                client_config = json.load(f)
            
            # Create flow
            flow = Flow.from_client_config(
                client_config,
                scopes=self.scopes,
                redirect_uri='http://localhost:3000/'
            )
            
            # Exchange authorization code for tokens
            flow.fetch_token(code=auth_code)
            self.creds = flow.credentials
            self.save_credentials()
            print("✅ Credentials created from authorization code")
            return True
        except Exception as e:
            print(f"⚠️ Error creating credentials from code: {e}")
            return False
    
    def get_auth_url(self):
        """Generate authorization URL"""
        try:
            with open(self.credentials_file, 'r') as f:
                client_config = json.load(f)
            
            flow = Flow.from_client_config(
                client_config,
                scopes=self.scopes,
                redirect_uri='http://localhost:3000/'
            )
            
            auth_url, _ = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true'
            )
            return auth_url
        except Exception as e:
            print(f"⚠️ Error generating auth URL: {e}")
            return None
    
    def authenticate_with_refresh_token(self, refresh_token):
        """Authenticate using a refresh token directly"""
        try:
            with open(self.credentials_file, 'r') as f:
                client_config = json.load(f)
            
            client_id = client_config['web']['client_id']
            client_secret = client_config['web']['client_secret']
            
            # Exchange refresh token for access token
            token_url = 'https://oauth2.googleapis.com/token'
            data = {
                'client_id': client_id,
                'client_secret': client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token'
            }
            
            response = requests.post(token_url, data=data)
            if response.status_code == 200:
                token_data = response.json()
                
                # Create credentials object
                self.creds = Credentials(
                    token=token_data['access_token'],
                    refresh_token=refresh_token,
                    token_uri=client_config['web']['token_uri'],
                    client_id=client_id,
                    client_secret=client_secret,
                    scopes=self.scopes
                )
                
                self.save_credentials()
                print("✅ Authenticated with refresh token")
                return True
            else:
                print(f"⚠️ Failed to refresh token: {response.text}")
                return False
        except Exception as e:
            print(f"⚠️ Error authenticating with refresh token: {e}")
            return False
    
    def get_calendar_service(self):
        """Get authenticated Calendar service"""
        if not self.creds:
            if not self.get_stored_credentials():
                return None
        
        if not self.creds.valid:
            if not self.refresh_credentials():
                return None
        
        try:
            service = build('calendar', 'v3', credentials=self.creds)
            print("✅ Calendar service created successfully")
            return service
        except Exception as e:
            print(f"⚠️ Error creating calendar service: {e}")
            return None
    
    def is_authenticated(self):
        """Check if we have valid credentials"""
        if not self.creds:
            self.get_stored_credentials()
        
        if self.creds:
            if self.creds.valid:
                return True
            elif self.creds.expired and self.creds.refresh_token:
                return self.refresh_credentials()
        
        return False

# Automated authentication function
def get_authenticated_calendar_service():
    """Main function to get authenticated calendar service without manual intervention"""
    oauth_manager = AutomatedOAuthManager()
    
    # Try to authenticate with stored credentials
    if oauth_manager.is_authenticated():
        return oauth_manager.get_calendar_service()
    
    # If no stored credentials, try some automated approaches
    print("⚠️ No valid stored credentials found")
    
    # Check if refresh token is available in environment variables
    refresh_token = os.getenv('GOOGLE_REFRESH_TOKEN')
    if refresh_token:
        print("🔄 Attempting authentication with environment refresh token")
        if oauth_manager.authenticate_with_refresh_token(refresh_token):
            return oauth_manager.get_calendar_service()
    
    # If we reach here, we need to get authorization
    print("❌ Automated authentication failed. Manual authorization required.")
    print("To enable automated authentication:")
    print("1. Set GOOGLE_REFRESH_TOKEN environment variable with a valid refresh token")
    print("2. Or complete the OAuth flow once to store credentials")
    
    return None

# Function to handle OAuth callback
def handle_oauth_callback(auth_code):
    """Handle OAuth callback with authorization code"""
    oauth_manager = AutomatedOAuthManager()
    if oauth_manager.create_credentials_from_code(auth_code):
        return oauth_manager.get_calendar_service()
    return None
