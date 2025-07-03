from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from datetime import datetime, timezone
import os
import json
from bson import ObjectId
from dotenv import load_dotenv

app = Flask(__name__)

# Load environment variables from .env file
load_dotenv()

# MongoDB Configuration
MONGO_URI = 'mongodb://localhost:27017'
client = MongoClient(MONGO_URI)
db = client['github_webhooks']
collection = db['events']


class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle ObjectId and datetime objects"""
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

app.json_encoder = JSONEncoder

def format_timestamp(timestamp_str):
    """Format timestamp to required format: 1st April 2021 - 9:30 PM UTC"""
    try:
        # Parse ISO format timestamp
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        
        # Format date with ordinal suffix
        day = dt.day
        if 4 <= day <= 20 or 24 <= day <= 30:
            suffix = "th"
        else:
            suffix = ["st", "nd", "rd"][day % 10 - 1]
        
        formatted_date = dt.strftime(f"{day}{suffix} %B %Y - %I:%M %p UTC")
        return formatted_date
    except Exception as e:
        print(f"Error formatting timestamp: {e}")
        return timestamp_str

def extract_webhook_data(payload, event_type):
    """Extract relevant data from GitHub webhook payload"""
    try:
        if event_type == 'push':
            return {
                'event_type': 'push',
                'author': payload['pusher']['name'],
                'to_branch': payload['ref'].split('/')[-1],  # Extract branch name from refs/heads/branch
                'timestamp': payload['head_commit']['timestamp'],
                'repository': payload['repository']['name']
            }
        
        elif event_type == 'pull_request':
            return {
                'event_type': 'pull_request',
                'author': payload['pull_request']['user']['login'],
                'from_branch': payload['pull_request']['head']['ref'],
                'to_branch': payload['pull_request']['base']['ref'],
                'timestamp': payload['pull_request']['created_at'],
                'repository': payload['repository']['name']
            }
        
        elif event_type == 'merge':
            # For merge events (when PR is merged)
            if payload.get('action') == 'closed' and payload['pull_request'].get('merged'):
                return {
                    'event_type': 'merge',
                    'author': payload['pull_request']['merged_by']['login'] if payload['pull_request']['merged_by'] else payload['pull_request']['user']['login'],
                    'from_branch': payload['pull_request']['head']['ref'],
                    'to_branch': payload['pull_request']['base']['ref'],
                    'timestamp': payload['pull_request']['merged_at'],
                    'repository': payload['repository']['name']
                }
        
        return None
    except KeyError as e:
        print(f"Error extracting webhook data: {e}")
        return None

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """Handle incoming GitHub webhooks"""
    try:
        # Get GitHub event type from headers
        event_type = request.headers.get('X-GitHub-Event')
        payload = request.json
        
        print(f"Received {event_type} event")
        
        # Extract data based on event type
        event_data = None
        
        if event_type == 'push':
            event_data = extract_webhook_data(payload, 'push')
        elif event_type == 'pull_request':
            if payload.get('action') == 'opened':
                event_data = extract_webhook_data(payload, 'pull_request')
            elif payload.get('action') == 'closed' and payload['pull_request'].get('merged'):
                event_data = extract_webhook_data(payload, 'merge')
        
        if event_data:
            # Add creation timestamp
            event_data['created_at'] = datetime.now(timezone.utc)
            
            # Store in MongoDB
            result = collection.insert_one(event_data)
            print(f"Stored event with ID: {result.inserted_id}")
            
            return jsonify({'status': 'success', 'message': 'Webhook processed'}), 200
        else:
            return jsonify({'status': 'ignored', 'message': 'Event not processed'}), 200
            
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/events', methods=['GET'])
def get_events():
    """API endpoint to get recent events for the UI"""
    try:
        # Get events from last 24 hours, sorted by creation time (newest first)
        events = list(collection.find().sort('created_at', -1).limit(50))
        
        # Format events for display
        formatted_events = []
        for event in events:
            formatted_event = {
                'id': str(event['_id']),
                'message': format_event_message(event),
                'timestamp': event['created_at'].isoformat() if isinstance(event['created_at'], datetime) else event['created_at'],
                'event_type': event['event_type'],
                'repository': event.get('repository', 'unknown')
            }
            formatted_events.append(formatted_event)
        
        return jsonify(formatted_events)
    except Exception as e:
        print(f"Error fetching events: {e}")
        return jsonify({'error': str(e)}), 500

def format_event_message(event):
    """Format event data into display message"""
    try:
        timestamp = format_timestamp(event['timestamp'])
        
        if event['event_type'] == 'push':
            return f"{event['author']} pushed to {event['to_branch']} on {timestamp}"
        elif event['event_type'] == 'pull_request':
            return f"{event['author']} submitted a pull request from {event['from_branch']} to {event['to_branch']} on {timestamp}"
        elif event['event_type'] == 'merge':
            return f"{event['author']} merged branch {event['from_branch']} to {event['to_branch']} on {timestamp}"
    except Exception as e:
        print(f"Error formatting event message: {e}")
        return "Error formatting message"

@app.route('/')
def index():
    """Serve the main UI"""
    return render_template('index.html')

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now(timezone.utc).isoformat()})

if __name__ == '__main__':
    # Create indexes for better performance
    collection.create_index([('created_at', -1)])
    collection.create_index([('event_type', 1)])
    
    app.run(host='0.0.0.0', port=5000, debug=True)