# calendar_api/response_server.py
from flask import Flask, request, render_template_string
import json
import os
from calendar_api.email_notification import load_responses, save_response

app = Flask(__name__)

@app.route('/respond', methods=['GET'])
def respond():
    response_id = request.args.get('id')
    action = request.args.get('action')

    if not response_id or not action:
        return "Invalid request", 400

    responses = load_responses()
    if response_id not in responses:
        return "Invalid response ID", 404

    response_data = responses[response_id]

    if action == 'accept':
        response_data['status'] = 'accepted'
        save_response(response_id, response_data)

        # Print notification to terminal
        print(f"\n🔔 NOTIFICATION: Interview Accepted")
        print(f"👤 Recipient: {response_data['recipient']}")
        print(f"⏰ Interview time: {response_data['start_time']} - {response_data['end_time']}")
        print(f"✅ Status: Accepted")
        print(f"🔗 Meet link: {response_data['meet_link']}\n")

        # Return a minimal page
        return """
        <html>
        <body style="font-family: Arial, sans-serif; text-align: center; margin-top: 50px;">
            <h3>Thank you for accepting the interview.</h3>
            <p>You can close this window now.</p>
            <script>
                setTimeout(function() {
                    window.close();
                }, 2000);
            </script>
        </body>
        </html>
        """

    elif action == 'decline':
        response_data['status'] = 'declined'
        save_response(response_id, response_data)

        # Print notification to terminal
        print(f"\n🔔 NOTIFICATION: Interview Declined")
        print(f"👤 Recipient: {response_data['recipient']}")
        print(f"⏰ Interview time: {response_data['start_time']} - {response_data['end_time']}")
        print(f"❌ Status: Declined")
        print(f"🔗 Meet link: {response_data['meet_link']}\n")

        # Return a minimal page
        return """
        <html>
        <body style="font-family: Arial, sans-serif; text-align: center; margin-top: 50px;">
            <h3>You have declined the interview.</h3>
            <p>You can close this window now.</p>
            <script>
                setTimeout(function() {
                    window.close();
                }, 2000);
            </script>
        </body>
        </html>
        """

    return "Invalid action", 400

@app.route('/')
def index():
    return """
    <html>
    <body>
        <h1>Interview Response Server</h1>
        <p>This server handles interview acceptance and decline responses.</p>
        <p>To test:</p>
        <ul>
            <li><a href="/respond?id=test&action=accept">Test Accept</a></li>
            <li><a href="/respond?id=test&action=decline">Test Decline</a></li>
        </ul>
    </body>
    </html>
    """

if __name__ == '__main__':
    app.run(debug=True)