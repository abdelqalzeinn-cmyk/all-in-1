from flask import Flask, request, jsonify, send_from_directory, url_for, session, copy_current_request_context
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from dotenv import load_dotenv
import os
import cohere
import json
import asyncio
import threading
import logging
from werkzeug.utils import secure_filename
from datetime import datetime
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, static_folder='.', static_url_path='')
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET', 'dev-secret-key')
CORS(app)

# Initialize SocketIO with CORS
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', logger=True, engineio_logger=True)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'txt', 'mp4', 'mp3'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create uploads directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Initialize Cohere with your API key
co = cohere.Client(os.getenv('COHERE_API_KEY'))

# Serve index.html at the root URL
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')
    emit('connected', {'data': 'Connected to WebSocket'})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')

@socketio.on('send_message')
def handle_send_message(data):
    """Handle messages from the web client"""
    logger.info(f'Received message from client: {data}')
    # Forward the message to all clients in the same channel
    emit('new_message', {
        'user': data.get('user', 'Anonymous'),
        'content': data.get('content', ''),
        'channel': data.get('channel', 'general'),
        'timestamp': datetime.utcnow().isoformat()
    }, broadcast=True, include_self=False)

    # Here you would typically forward the message to the Discord bot
    # For now, we'll just echo it back
    emit('new_message', {
        'user': 'Bot',
        'content': f'You said: {data.get("content", "")}',
        'channel': data.get('channel', 'general'),
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# API endpoint for chat
@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        response = co.chat(
            message=data['prompt'],
            model='command-a-03-2025',
            temperature=0.7,
            max_tokens=1024,
            k=0,
            stop_sequences=[]
        )
        return jsonify({'response': response.text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        # Generate a unique filename to prevent overwrites
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        
        # Get file URL
        file_url = url_for('uploaded_file', filename=unique_filename, _external=True)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'url': file_url,
            'type': file.content_type,
            'size': os.path.getsize(filepath)
        })
    
    return jsonify({'error': 'File type not allowed'}), 400

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == '__main__':
    # Start Flask-SocketIO in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        os._exit(0)
