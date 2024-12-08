from flask import Flask, jsonify, request, send_from_directory, g
import asyncio
from recorder import record_website
import uuid
import os
import sqlite3
from pathlib import Path
from asgiref.wsgi import WsgiToAsgi

app = Flask(__name__)

# Configure static file serving
VIDEOS_DIR = Path("videos")
VIDEOS_DIR.mkdir(exist_ok=True)
app.config['STATIC_FOLDER'] = str(VIDEOS_DIR)

# Database configuration
DATABASE = 'recordings.db'

# Create a queue for video recording tasks
recording_queue = asyncio.Queue()

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    with app.app_context():
        db = get_db()
        with open('schema.sql', 'r') as f:
            db.executescript(f.read())
        db.commit()

def update_recording_status(request_id, status, video_url=None, error=None):
    db = get_db()
    try:
        db.execute(
            'INSERT OR REPLACE INTO recordings (request_id, status, video_url, error) VALUES (?, ?, ?, ?)',
            (request_id, status, video_url, error)
        )
        db.commit()
    finally:
        db.close()

def get_recording_status(request_id):
    db = get_db()
    try:
        result = db.execute('SELECT * FROM recordings WHERE request_id = ?', (request_id,)).fetchone()
        if result:
            return dict(result)
        return None
    finally:
        db.close()

async def process_recording_queue():
    """Background task to process the recording queue"""
    print("Queue processor started!")
    while True:
        try:
            print("Waiting for tasks...")
            task_data = await recording_queue.get()
            request_id = task_data['request_id']
            url = task_data['url']
            
            print(f"Processing request ID: {request_id} for URL: {url}")
            
            try:
                video_path = await record_website(url, request_id)
                print(f"Recording completed: {video_path}")
                with app.app_context():
                    update_recording_status(
                        request_id,
                        'completed',
                        f'videos/{request_id}/{os.path.basename(video_path)}'
                    )
            except Exception as e:
                print(f"Error recording website: {e}")
                with app.app_context():
                    update_recording_status(
                        request_id,
                        'failed',
                        error=str(e)
                    )
            finally:
                recording_queue.task_done()
                
        except Exception as e:
            print(f"Error processing queue: {e}")
            await asyncio.sleep(1)

@app.route('/record', methods=['POST'])
async def record():
    """
    Endpoint to queue a website recording
    Expected JSON body: {"url": "https://example.com"}
    """
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'URL is required'}), 400

        url = data['url']
        request_id = str(uuid.uuid4())
        
        # Initialize recording status in database
        update_recording_status(request_id, 'queued')
        
        # Add recording task to queue
        await recording_queue.put({'request_id': request_id, 'url': url})
        
        return jsonify({
            'success': True,
            'request_id': request_id,
            'status': 'queued',
            'message': 'Recording has been queued'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/status/<request_id>', methods=['GET'])
async def get_status(request_id):
    """Check the status of a recording request"""
    recording_status = get_recording_status(request_id)
    if not recording_status:
        return jsonify({'error': 'Request ID not found'}), 404
    
    response = {
        'status': recording_status['status'],
        'request_id': request_id,
    }
    
    if recording_status['video_url']:
        response['video_url'] = request.host_url + recording_status['video_url']
    if recording_status['error']:
        response['error'] = recording_status['error']
        
    return jsonify(response)

@app.route('/videos/<path:path>')
def serve_video(path):
    return send_from_directory(app.config['STATIC_FOLDER'], path)

if __name__ == '__main__':
    import uvicorn
    
    # Create event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Initialize the database
    init_db()
    
    # Wrap the Flask app with WsgiToAsgi
    asgi_app = WsgiToAsgi(app)
    
    # Start the background task explicitly
    loop.create_task(process_recording_queue())
    
    # Configure and start the server
    config = uvicorn.Config(
        asgi_app,
        host="0.0.0.0",
        port=8000,
        loop="asyncio"
    )
    server = uvicorn.Server(config)
    
    # Run the server
    loop.run_until_complete(server.serve()) 