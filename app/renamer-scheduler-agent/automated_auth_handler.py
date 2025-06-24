"""
Automated OAuth Handler
Handles OAuth authentication flow without manual browser interaction
"""

import os
import sys
import json
import urllib.parse
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time
from calendar_api.automated_oauth import AutomatedOAuthManager, handle_oauth_callback

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback"""
    
    def do_GET(self):
        """Handle GET request from OAuth callback"""
        # Parse the callback URL
        parsed_url = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        if 'code' in query_params:
            auth_code = query_params['code'][0]
            print(f"✅ Received authorization code: {auth_code[:20]}...")
            
            # Store the auth code for processing
            self.server.auth_code = auth_code
            
            # Send response to browser
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
            <html>
            <body>
                <h2>Authentication Successful!</h2>
                <p>You can close this window now.</p>
                <script>window.close();</script>
            </body>
            </html>
            """)
        elif 'error' in query_params:
            error = query_params['error'][0]
            print(f"❌ OAuth error: {error}")
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(f"<html><body><h2>Error: {error}</h2></body></html>".encode())
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<html><body><h2>Invalid callback</h2></body></html>")
    
    def log_message(self, format, *args):
        """Suppress log messages"""
        pass

def start_callback_server(port=3000, timeout=60):
    """Start HTTP server to capture OAuth callback"""
    server = HTTPServer(('localhost', port), OAuthCallbackHandler)
    server.auth_code = None
    
    print(f"🌐 Starting callback server on http://localhost:{port}")
    
    # Start server in a separate thread
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    # Wait for auth code or timeout
    start_time = time.time()
    while server.auth_code is None and (time.time() - start_time) < timeout:
        time.sleep(1)
    
    server.shutdown()
    return server.auth_code

def extract_code_from_url(url):
    """Extract authorization code from callback URL"""
    try:
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        if 'code' in params:
            return params['code'][0]
    except Exception as e:
        print(f"⚠️ Error extracting code from URL: {e}")
    return None

def authenticate_with_url(auth_url):
    """Authenticate using the provided authorization URL"""
    print("🔐 Starting automated OAuth authentication...")
    
    # Check if this is already a callback URL with code
    auth_code = extract_code_from_url(auth_url)
    if auth_code:
        print(f"✅ Found authorization code in URL: {auth_code[:20]}...")
        return complete_authentication(auth_code)
    
    # If it's an authorization URL, we need to simulate the flow
    print("⚠️ This appears to be an authorization URL, not a callback URL")
    print("To complete authentication automatically, you need:")
    print("1. Visit the URL in a browser")
    print("2. Grant permissions")
    print("3. Copy the callback URL that contains the 'code' parameter")
    print("4. Run this script with that callback URL")
    
    return False

def complete_authentication(auth_code):
    """Complete authentication with authorization code"""
    try:
        # Change to the correct directory
        os.chdir('app/renamer-scheduler-agent')
        
        # Use the automated OAuth manager
        oauth_manager = AutomatedOAuthManager()
        if oauth_manager.create_credentials_from_code(auth_code):
            service = oauth_manager.get_calendar_service()
            if service:
                print("✅ Authentication completed successfully!")
                
                # Test the service
                try:
                    calendar_list = service.calendarList().list().execute()
                    print(f"📅 Found {len(calendar_list.get('items', []))} calendars")
                    return True
                except Exception as e:
                    print(f"⚠️ Error testing calendar service: {e}")
                    return False
            else:
                print("❌ Failed to create calendar service")
                return False
        else:
            print("❌ Failed to create credentials from authorization code")
            return False
    except Exception as e:
        print(f"❌ Error completing authentication: {e}")
        return False

def main():
    """Main function to handle automated authentication"""
    if len(sys.argv) < 2:
        print("Usage: python automated_auth_handler.py <auth_url_or_callback_url>")
        print("Or: python automated_auth_handler.py --server (to start callback server)")
        return
    
    if sys.argv[1] == '--server':
        # Start callback server mode
        print("🚀 Starting OAuth callback server...")
        auth_code = start_callback_server()
        
        if auth_code:
            complete_authentication(auth_code)
        else:
            print("⏰ Callback server timed out without receiving authorization code")
    else:
        # Handle provided URL
        url = sys.argv[1]
        authenticate_with_url(url)

if __name__ == "__main__":
    main()
