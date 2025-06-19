"""
Standalone response server for handling interview accept/decline responses

Run this with: 
python -m app.response_server

This server will listen for accept/decline responses from email links
and update the interview_responses.json file accordingly.
"""

from flask import Flask, request, render_template_string
import json
import os
from app.utils.email_notification import load_responses, save_response

# Create Flask app
app = Flask(__name__)

# Set the port (use environment variable if available)
PORT = int(os.environ.get("RESPONSE_SERVER_PORT", 5000))

@app.route('/respond', methods=['GET'])
def respond():
    """Handle interview response (accept or decline)"""
    response_id = request.args.get('id')
    action = request.args.get('action')

    if not response_id or not action:
        return generate_error_html("Invalid request. Missing ID or action.")
    
    responses = load_responses()
    if response_id not in responses:
        return generate_error_html("Invalid response ID. This link may have expired.")
    
    response_data = responses[response_id]
    
    if action not in ["accept", "decline"]:
        return generate_error_html("Invalid action. Must be 'accept' or 'decline'.")
    
    # Update response status
    response_data['status'] = action
    response_data['response_time'] = True
    save_response(response_id, response_data)
    
    # Print notification to terminal for visibility
    print(f"\n🔔 NOTIFICATION: Interview {action.capitalize()}d")
    print(f"👤 Recipient: {response_data['recipient']}")
    print(f"⏰ Interview time: {response_data['start_time']} - {response_data['end_time']}")
    print(f"✅ Status: {action.capitalize()}d")
    if response_data.get('meet_link'):
        print(f"🔗 Meet link: {response_data['meet_link']}")
    print(f"📅 Event ID: {response_data.get('event_id', 'Not available')}\n")
    
    # Return HTML response
    if action == "accept":
        return generate_success_html(
            "Thank you for accepting the interview.",
            "Your response has been recorded. The interview has been confirmed.",
            response_data
        )
    else:
        return generate_success_html(
            "Interview declined.",
            "Your response has been recorded. The organizer will be notified.",
            response_data
        )


@app.route('/')
def index():
    """Index page with response tracking status"""
    responses = load_responses()
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Interview Response Tracker</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1000px;
                margin: 0 auto;
                padding: 20px;
            }}
            .container {{
                background-color: #f9f9f9;
                border-radius: 5px;
                padding: 20px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
            }}
            h1, h2 {{
                color: #4285f4;
                border-bottom: 1px solid #eee;
                padding-bottom: 10px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th, td {{
                padding: 10px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }}
            th {{
                background-color: #f2f2f2;
            }}
            .accepted {{
                color: green;
                font-weight: bold;
            }}
            .declined {{
                color: red;
                font-weight: bold;
            }}
            .pending {{
                color: orange;
                font-weight: bold;
            }}
            .success {{
                color: #4CAF50;
                font-weight: bold;
            }}
            .details {{
                background-color: #fff;
                padding: 15px;
                border-radius: 5px;
                margin: 15px 0;
                border-left: 4px solid #4285f4;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Interview Response Tracker</h1>
            <p>This server tracks responses to interview invitations sent via email.</p>
            
            <h2>Current Responses</h2>
            <table>
                <tr>
                    <th>Recipient</th>
                    <th>Start Time</th>
                    <th>End Time</th>
                    <th>Status</th>
                    <th>Action</th>
                    <th>Meet Link</th>
                </tr>
                {"".join([
                    f'''
                    <tr>
                        <td>{resp_data.get('recipient', 'Unknown')}</td>
                        <td>{resp_data.get('start_time', 'Not specified')}</td>
                        <td>{resp_data.get('end_time', 'Not specified')}</td>
                        <td class="{resp_data.get('status', 'pending')}">{resp_data.get('status', 'pending').capitalize()}</td>
                        <td>{resp_data.get('action', 'Unknown')}</td>
                        <td>{"<a href='" + resp_data.get('meet_link', '#') + "' target='_blank'>" + resp_data.get('meet_link', 'Not available') + "</a>" if resp_data.get('meet_link') else "Not available"}</td>
                    </tr>
                    '''
                    for resp_id, resp_data in responses.items()
                ])}
            </table>
            
            <div class="details">
                <h3>Test Response Links</h3>
                <p>Use these links to test the response functionality:</p>
                <ul>
                    <li><a href="/respond?id=test&action=accept">Test Accept</a></li>
                    <li><a href="/respond?id=test&action=decline">Test Decline</a></li>
                </ul>
                <p><b>Note:</b> The test links will only work if a 'test' response ID exists in the responses file.</p>
            </div>
            
            <p>The response server is running on port {PORT}.</p>
        </div>
    </body>
    </html>
    """


# Helper functions for HTML responses
def generate_success_html(title, message, data):
    """Generate HTML response for successful action"""
    meet_link = data.get('meet_link', '')
    meet_link_html = f"""
        <p><strong>Google Meet Link:</strong> <a href="{meet_link}" target="_blank">{meet_link}</a></p>
    """ if meet_link else ""
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Interview Response</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .container {{
                background-color: #f9f9f9;
                border-radius: 5px;
                padding: 20px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #4285f4;
                border-bottom: 1px solid #eee;
                padding-bottom: 10px;
            }}
            .details {{
                background-color: #fff;
                padding: 15px;
                border-radius: 5px;
                margin: 15px 0;
                border-left: 4px solid #4285f4;
            }}
            .success {{
                color: #4CAF50;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1 class="success">{title}</h1>
            <p>{message}</p>
            
            <div class="details">
                <p><strong>Start Time:</strong> {data.get('start_time', 'Not specified')}</p>
                <p><strong>End Time:</strong> {data.get('end_time', 'Not specified')}</p>
                {meet_link_html}
            </div>
            
            <p>This window will close automatically in a few seconds.</p>
            <p><a href="/">Return to Response Tracker</a></p>
        </div>
        
        <script>
            setTimeout(function() {{
                window.close();
            }}, 5000);
        </script>
    </body>
    </html>
    """


def generate_error_html(error_message):
    """Generate HTML response for error"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Error</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .container {{
                background-color: #f9f9f9;
                border-radius: 5px;
                padding: 20px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #f44336;
                border-bottom: 1px solid #eee;
                padding-bottom: 10px;
            }}
            .error {{
                color: #f44336;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Error</h1>
            <p class="error">{error_message}</p>
            <p>This window will close automatically in a few seconds.</p>
            <p><a href="/">Return to Response Tracker</a></p>
        </div>
        
        <script>
            setTimeout(function() {{
                window.close();
            }}, 5000);
        </script>
    </body>
    </html>
    """


if __name__ == '__main__':
    print(f"\n🚀 Starting Interview Response Server on port {PORT}")
    print(f"📊 Dashboard available at http://localhost:{PORT}/")
    print(f"⚠️ Make sure to configure your EMAIL_PASSWORD environment variable!")
    print(f"🔍 Response tracking file: {os.path.abspath('interview_responses.json')}")
    print(f"\n📫 Waiting for interview responses...\n")
    
    app.run(debug=True, port=PORT)
