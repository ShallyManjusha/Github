import os
import requests
from dotenv import load_dotenv
import logging
import uuid
from datetime import datetime
from flask import Flask, request, jsonify

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Load environment variables from .env file
load_dotenv()

# Retrieve environment variables
GLPI_API_URL = os.getenv('GLPI_API_URL')
GLPI_API_TOKEN = os.getenv('GLPI_API_TOKEN')
GLPI_APP_TOKEN = os.getenv('GLPI_APP_TOKEN')

# Global variable to store the ticket title
created_ticket_title = None

# Status and Request Source Mapping
STATUS_MAPPING = {
    "New": 1,
    "Processing (assigned)": 2,
    "Processing (planned)": 3,
    "Pending": 4,
    "Solved": 5,
    "Closed": 6
}

REQUEST_SOURCE_MAPPING = {
    "------": 7,
    "Direct": 4,
    "Email": 2,
    "Helpdesk": 1,
    "Other": 6,
    "Phone": 3,
    "Written": 5
}

app = Flask(__name__)

# Function to check GLPI connection
def check_glpi_connection():
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'user_token {GLPI_API_TOKEN}',
        'App-Token': GLPI_APP_TOKEN
    }
    try:
        response = requests.get(f'{GLPI_API_URL}/initSession', headers=headers)
        logging.debug(f'GLPI initSession response: {response.json()}')
        
        if response.status_code == 200:
            return {"status": "success", "session_token": response.json()['session_token']}
        else:
            return {"status": "fail", "message": response.json(), "status_code": response.status_code}
    except requests.exceptions.RequestException as e:
        logging.error(f'Error checking GLPI connection: {str(e)}')
        return {"status": "error", "message": str(e)}

# Function to add a new user
def add_user(session_token, email, is_active="1"):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'user_token {GLPI_API_TOKEN}',
        'App-Token': GLPI_APP_TOKEN,
        'Session-Token': session_token
    }
    # Use email as the username
    user_data = {
        "input": {
            "name": email,
            "email": email,
            "is_active": is_active
        }
    }
    try:
        response = requests.post(f'{GLPI_API_URL}/User', headers=headers, json=user_data)
        logging.debug(f'GLPI add user response: {response.json()}')

        if response.status_code == 201:
            return {"status": "success", "user_id": response.json()["id"]}
        else:
            return {"status": "fail", "message": response.json(), "status_code": response.status_code}
    except requests.exceptions.RequestException as e:
        logging.error(f'Error adding user: {str(e)}')
        return {"status": "error", "message": str(e)}

# Function to raise a ticket
def raise_ticket(description, session_token, status, date, request_source, requester_id):
    global created_ticket_title  # Use the global variable

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'user_token {GLPI_API_TOKEN}',
        'App-Token': GLPI_APP_TOKEN,
        'Session-Token': session_token
    }

    # Generate a unique and random ticket name
    ticket_name = str(uuid.uuid4())

    ticket_data = {
        "input": {
            "name": ticket_name,
            "content": description,
            "status": status,
            "urgency": 3,
            "date": date,
            "requesttypes_id": request_source,
            "_users_id_requester": requester_id,  # Use requester ID
            "type": 1
        }
    }

    logging.debug(f'GLPI ticket data: {ticket_data}')

    try:
        response = requests.post(f'{GLPI_API_URL}/Ticket', headers=headers, json=ticket_data)
        logging.debug(f'GLPI raise ticket response: {response.json()}')

        if response.status_code == 201:
            ticket_id = response.json()["id"]
            created_ticket_title = ticket_name  # Store the ticket title
            return {"status": "success", "user_id": requester_id, "ticket_number": ticket_id, "ticket_title": ticket_name}
        else:
            return {"status": "fail", "message": response.json(), "status_code": response.status_code}
    except requests.exceptions.RequestException as e:
        logging.error(f'Error raising ticket: {str(e)}')
        return {"status": "error", "message": str(e)}

# Function to check if a user exists
def check_user_exists(session_token, email):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'user_token {GLPI_API_TOKEN}',
        'App-Token': GLPI_APP_TOKEN,
        'Session-Token': session_token
    }
    try:
        response = requests.get(f'{GLPI_API_URL}/User', headers=headers)
        logging.debug(f'GLPI check user response: {response.json()}')
        
        if response.status_code == 200:
            users = response.json()
            for user in users:
                if user["name"] == email:
                    user_id = user["id"]
                    user_name = user["name"]
                    return {"status": "success", "user_id": user_id, "user_name": user_name}
            return {"status": "fail", "message": "User not found"}
        else:
            return {"status": "fail", "message": response.json(), "status_code": response.status_code}
    except requests.exceptions.RequestException as e:
        logging.error(f'Error checking user: {str(e)}')
        return {"status": "error", "message": str(e)}

def parse_and_format_date(date_str):
    try:
        # Attempt to parse date in YYYY-MM-DD format
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        try:
            # Attempt to parse date in DD-MM-YYYY format
            date_obj = datetime.strptime(date_str, '%d-%m-%Y')
        except ValueError:
            try:
                # Attempt to parse date in MM-DD-YYYY format
                date_obj = datetime.strptime(date_str, '%m-%d-%Y')
            except ValueError:
                raise ValueError("Invalid date format. Use YYYY-MM-DD, DD-MM-YYYY, or MM-DD-YYYY.")
    
    # Convert to standard format YYYY-MM-DD HH:MM:SS
    return date_obj.strftime('%Y-%m-%d 00:00:00')

# Main function to add user and raise ticket
def add_user_and_raise_ticket(data):
    user_email = data.get('email')
    description = data.get('description')
    status = data.get('status')
    date = data.get('date')
    request_source = data.get('request_source')

    logging.debug(f'Function add_user_and_raise_ticket received data: {data}')

    # Validate required fields
    if not all([user_email, description, status, date, request_source]):
        return {"status": "error", "message": "Email, description, status, date, and request_source are required"}

    # Map status and request source to internal IDs
    status_id = STATUS_MAPPING.get(status)
    request_source_id = REQUEST_SOURCE_MAPPING.get(request_source)

    if status_id is None:
        return {"status": "error", "message": f"Invalid status: {status}"}
    if request_source_id is None:
        return {"status": "error", "message": f"Invalid request source: {request_source}"}

    try:
        # Check GLPI connection
        session_result = check_glpi_connection()
        if session_result['status'] == 'success':
            session_token = session_result['session_token']

            # Parse and format date
            try:
                formatted_date = parse_and_format_date(date)
            except ValueError as e:
                return {"status": "error", "message": str(e)}
            
            # Check if user exists
            user_check_result = check_user_exists(session_token, user_email)
            if user_check_result['status'] == 'success':
                requester_id = user_check_result['user_id']
            else:
                # Add user
                user_result = add_user(session_token, user_email)
                if user_result['status'] == 'success':
                    requester_id = user_result['user_id']
                else:
                    return user_result
            
            # Raise ticket
            ticket_result = raise_ticket(description, session_token, status_id, formatted_date, request_source_id, requester_id)
            return ticket_result
        else:
            return session_result
    except ValueError as e:
        logging.error(f'ValueError: {str(e)}')
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logging.error(f'Exception: {str(e)}')
        return {"status": "error", "message": str(e)}

# Function to fetch created ticket title
def fetch_created_ticket_title():
    if created_ticket_title:
        return {"ticket_title": created_ticket_title}
    else:
        return {"status": "fail", "message": "No ticket title available"}

# Flask Routes
@app.route('/api/check_glpi_connection', methods=['GET'])
def api_check_glpi_connection():
    result = check_glpi_connection()
    return jsonify(result)

@app.route('/add_user_and_raise_ticket', methods=['POST'])
def api_add_user_and_raise_ticket():
    data = request.json
    result = add_user_and_raise_ticket(data)
    return jsonify(result)

@app.route('/fetch_created_ticket_title', methods=['GET'])
def get_created_ticket_title():
    ticket_title_result = fetch_created_ticket_title()
    return jsonify(ticket_title_result)

# Test the function directly if run as a script
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
