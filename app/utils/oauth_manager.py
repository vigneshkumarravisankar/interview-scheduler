"""
OAuth manager for Gmail API
"""
import os
import json
import time
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from fastapi import HTTPException

# If modifying these scopes, delete the token.json file.
SCOPES = ['https://www.googleapis.com/auth/gmail.send']
REDIRECT_URI = 'http://localhost:8000'  # Must match GCP configuration

class OAuthManager:
    """
    Manages OAuth authentication for Gmail API
    """
    def __init__(self, token_file='app/config/gmail_token.json', credentials_file='app/config/gmail_credentials.json'):
        self.token_file = token_file
        self.credentials_file = credentials_file
        self.credentials = None
        self.token_expiry_buffer = 300  # 5 minutes buffer before actual expiry
        
        # Ensure relative paths work when running from any directory
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Convert paths to absolute if they are relative
        if not os.path.isabs(self.token_file):
            self.token_file = os.path.join(script_dir, self.token_file)
            
        if not os.path.isabs(self.credentials_file):
            self.credentials_file = os.path.join(script_dir, self.credentials_file)
        
        print(f"Using token file: {self.token_file}")
        print(f"Using credentials file: {self.credentials_file}")
       
    def get_credentials(self):
        """Get valid user credentials from storage."""
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, 'r') as token:
                    token_data = json.loads(token.read())
                    self.credentials = Credentials.from_authorized_user_info(token_data)
            except (ValueError, KeyError) as e:
                print(f"Error reading token file: {e}")
                self.credentials = None
       
        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                return self._refresh_token()
            return self._run_oauth_flow()
           
        return self.credentials
   
    def _is_token_expired_or_expiring_soon(self):
        """Check if the token is expired or will expire soon."""
        if not self.credentials or not self.credentials.expiry:
            return True
           
        expiry_timestamp = self.credentials.expiry.timestamp()
        current_time = time.time()
        return current_time + self.token_expiry_buffer >= expiry_timestamp
   
    def _refresh_token(self):
        """Refresh the access token using refresh token."""
        try:
            print("Refreshing access token...")
            self.credentials.refresh(Request())
            self._save_credentials()
            return self.credentials
        except RefreshError as e:
            print(f"Error refreshing token: {e}")
            return self._run_oauth_flow()
   
    def _run_oauth_flow(self):
        """Run the full OAuth flow to get new credentials or use pre-existing token."""
        try:
            # First, check if we have a pre-existing saved token we can just load directly
            # This is useful for development when we already have a token saved to disk
            if os.path.exists(self.token_file):
                try:
                    print(f"Loading pre-existing token from {self.token_file}")
                    with open(self.token_file, 'r') as f:
                        token_data = json.load(f)
                        
                    # Create credentials from token data
                    creds = Credentials.from_authorized_user_info(token_data)
                    
                    # Check if the token needs refreshing
                    if creds.expired and creds.refresh_token:
                        print("Token is expired, refreshing...")
                        creds.refresh(Request())
                        
                    self.credentials = creds
                    self._save_credentials()
                    print("Successfully loaded existing token")
                    return self.credentials
                except Exception as token_err:
                    print(f"Failed to load token from file: {token_err}")
            
            # If we reach here, either we don't have a token file or loading it failed
            print("Starting OAuth flow to get a new token")
            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_file,
                SCOPES,
                redirect_uri=REDIRECT_URI
            )
            
            # Use pre-existing token if we have one saved but couldn't parse it properly
            self.credentials = flow.run_local_server(
                port=8000,
                authorization_prompt_message='Please visit this URL: {url}',
                success_message='The auth flow is complete; you may close this window.',
                open_browser=True
            )
            
            self._save_credentials()
            return self.credentials
        except Exception as e:
            print(f"Error in OAuth flow: {e}")
            
            # As a last resort, try to manually create credentials from stored token values
            # This is a fallback for when the standard flow doesn't work
            try:
                # Check if we have the manually created token file with all the necessary fields
                if os.path.exists(self.token_file):
                    print("Attempting to create credentials directly from token file...")
                    with open(self.token_file, 'r') as f:
                        token_data = json.load(f)
                    
                    # Create credentials directly
                    if all(k in token_data for k in 
                           ['token', 'refresh_token', 'client_id', 'client_secret']):
                        creds = Credentials(
                            token=token_data.get('token'),
                            refresh_token=token_data.get('refresh_token'),
                            token_uri=token_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
                            client_id=token_data.get('client_id'),
                            client_secret=token_data.get('client_secret'),
                            scopes=token_data.get('scopes', SCOPES)
                        )
                        self.credentials = creds
                        print("Successfully created credentials from token data")
                        return self.credentials
            except Exception as fallback_err:
                print(f"Fallback authentication also failed: {fallback_err}")
            
            # If all attempts fail, raise exception
            raise HTTPException(
                status_code=500,
                detail=f"Authentication failed: {str(e)}. Please ensure your redirect URIs are properly configured in Google Cloud Console."
            )
   
    def _save_credentials(self):
        """Save credentials to the token file."""
        if self.credentials and self.credentials.valid:
            with open(self.token_file, 'w') as token:
                token.write(self.credentials.to_json())
            print("Credentials saved successfully")
           
    def revoke_token(self):
        """Revoke the current token."""
        if self.credentials and self.credentials.valid:
            try:
                request = Request()
                self.credentials.refresh(request)
                response = request.post(
                    'https://oauth2.googleapis.com/revoke',
                    params={'token': self.credentials.token},
                    headers={'content-type': 'application/x-www-form-urlencoded'}
                )
               
                if response.status_code == 200:
                    print("Token successfully revoked")
                    if os.path.exists(self.token_file):
                        os.remove(self.token_file)
                    return True
            except Exception as e:
                print(f"Error revoking token: {e}")
        return False
