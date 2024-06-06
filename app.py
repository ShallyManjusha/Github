import os
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request
import logging

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Load environment variables from .env file
load_dotenv()

# Retrieve environment variables
GLPI_API_URL = os.getenv('GLPI_API_URL')
GLPI_API_TOKEN = os.getenv('GLPI_API_TOKEN')
GLPI_APP_TOKEN = os.getenv('GLPI_APP_TOKEN')

# Function to check GLPI connection
def check_glpi_connection():
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'user_token {GLPI_API_TOKEN}',
        'App-Token': GLPI_APP_TOKEN
    }

    try:
        response = requests.get(f'{GLPI_API_URL}/initSession', headers=headers)
        
        if response.status_code == 200:
            return {"status": "success", "session_token": response.json()['session_token']}
        else:
            return {"status": "fail", "message": response.json(), "status_code": response.status_code}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": str(e)}

# Function to raise a ticket in GLPI
def raise_ticket(subject, description, session_token):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'user_token {GLPI_API_TOKEN}',
        'App-Token': GLPI_APP_TOKEN,
        'Session-Token': session_token
    }

    ticket_data = {
        "input": {
            "name": subject,
            "content": description,
            "status": 1,
            "urgency": 3
        }
    }

    try:
        response = requests.post(f'{GLPI_API_URL}/Ticket', headers=headers, json=ticket_data)
        
        if response.status_code == 201:
            return {"status": "success", "ticket": response.json()}
        else:
            return {"status": "fail", "message": response.json(), "status_code": response.status_code}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": str(e)}

@app.route('/', methods=['GET'])
def home():
    return jsonify({"message": "Welcome to the GLPI API, your Ticket has been successfully generated!!"}), 200

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/check_connection', methods=['GET'])
def check_connection():
    result = check_glpi_connection()
    return jsonify(result)

@app.route('/raise_ticket', methods=['POST'])
def api_raise_ticket():
    data = request.get_json()
    subject = data.get('subject')
    description = data.get('description')

    if not subject or not description:
        return jsonify({"status": "error", "message": "Subject and description are required"}), 400

    session_result = check_glpi_connection()
    if session_result['status'] == 'success':
        session_token = session_result['session_token']
        ticket_result = raise_ticket(subject, description, session_token)
        return jsonify(ticket_result)
    else:
        return jsonify(session_result)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)

