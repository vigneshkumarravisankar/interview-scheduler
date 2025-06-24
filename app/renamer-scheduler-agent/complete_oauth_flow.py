"""
Complete OAuth Flow Handler
Extracts authorization code from URL and completes authentication
"""

import os
import sys
import urllib.parse
import requests
import json
from pathlib import Path
from calendar_api.automated_oauth import AutomatedOAuthManager

def extract_code_from_callback_url(callback_url):
    """Extract authorization code from Google OAuth callback URL"""
    try:
        parsed_url = urllib.parse.urlparse(callback_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        if 'code' in query_params:
            return query_params['code'][0]
        else:
            print("❌ No authorization code found in the URL")
            print("Available parameters:", list(query_params.keys()))
            return None
    except Exception as e:
        print(f"❌ Error parsing URL: {e}")
        return None

def exchange_code_for_tokens(auth_code):
    """Exchange authorization code for access and refresh tokens"""
    try:
        # Load credentials
        credentials_path = Path("credentials.json")
        if not credentials_path.exists():
            print("❌ credentials.json not found")
            return None
            
        with open(credentials_path, 'r') as f:
            client_config = json.load(f)
        
        client_id = client_config['web']['client_id']
        client_secret = client_config['web']['client_secret']
        
        # Exchange code for tokens
        token_url = 'https://oauth2.googleapis.com/token'
        data = {
            'client_id': client_id,
            'client_secret': client_secret,
            'code': auth_code,
            'grant_type': 'authorization_code',
            'redirect_uri': 'http://localhost:3000/'
        }
        
        print("🔄 Exchanging authorization code for tokens...")
        response = requests.post(token_url, data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            print("✅ Successfully obtained tokens!")
            
            # Save tokens to environment file
            if 'refresh_token' in token_data:
                save_refresh_token(token_data['refresh_token'])
            
            return token_data
        else:
            print(f"❌ Token exchange failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error exchanging code for tokens: {e}")
        return None

def save_refresh_token(refresh_token):
    """Save refresh token to .env file for future use"""
    try:
        env_path = Path("../../.env")
        
        # Read existing .env content
        env_content = ""
        if env_path.exists():
            with open(env_path, 'r') as f:
                env_content = f.read()
        
        # Add or update GOOGLE_REFRESH_TOKEN
        lines = env_content.strip().split('\n') if env_content.strip() else []
        updated = False
        
        for i, line in enumerate(lines):
            if line.startswith('GOOGLE_REFRESH_TOKEN='):
                lines[i] = f'GOOGLE_REFRESH_TOKEN={refresh_token}'
                updated = True
                break
        
        if not updated:
            lines.append(f'GOOGLE_REFRESH_TOKEN={refresh_token}')
        
        # Write back to .env
        with open(env_path, 'w') as f:
            f.write('\n'.join(lines) + '\n')
        
        print(f"✅ Refresh token saved to {env_path}")
        
    except Exception as e:
        print(f"⚠️ Error saving refresh token: {e}")

def test_authentication():
    """Test the authentication by trying to access Calendar API"""
    try:
        oauth_manager = AutomatedOAuthManager()
        service = oauth_manager.get_calendar_service()
        
        if service:
            # Test API call
            calendar_list = service.calendarList().list().execute()
            calendars = calendar_list.get('items', [])
            
            print(f"✅ Authentication successful!")
            print(f"📅 Found {len(calendars)} calendars:")
            for calendar in calendars[:3]:  # Show first 3 calendars
                print(f"  - {calendar.get('summary', 'Unknown')}")
            
            return True
        else:
            print("❌ Failed to create calendar service")
            return False
            
    except Exception as e:
        print(f"❌ Authentication test failed: {e}")
        return False

def main():
    """Main function"""
    print("🚀 Google Calendar OAuth Flow Completer")
    print("=" * 50)
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python complete_oauth_flow.py <callback_url_with_code>")
        print("  python complete_oauth_flow.py --test")
        print("\nExample callback URL:")
        print("  http://localhost:3000/?code=4/0AX4XfW...")
        return
    
    if sys.argv[1] == '--test':
        print("🧪 Testing existing authentication...")
        test_authentication()
        return
    
    callback_url = sys.argv[1]
    print(f"📥 Processing callback URL...")
    
    # Extract authorization code
    auth_code = extract_code_from_callback_url(callback_url)
    if not auth_code:
        return
    
    print(f"✅ Extracted authorization code: {auth_code[:20]}...")
    
    # Exchange code for tokens
    tokens = exchange_code_for_tokens(auth_code)
    if not tokens:
        return
    
    # Create OAuth manager and save credentials
    try:
        oauth_manager = AutomatedOAuthManager()
        if oauth_manager.create_credentials_from_code(auth_code):
            print("✅ Credentials saved successfully!")
            
            # Test the authentication
            print("\n🧪 Testing authentication...")
            test_authentication()
        else:
            print("❌ Failed to create and save credentials")
    except Exception as e:
        print(f"❌ Error creating credentials: {e}")

if __name__ == "__main__":
    # Change to the correct directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()
