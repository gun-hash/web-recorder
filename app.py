from flask import Flask, jsonify, request, send_from_directory
import asyncio
from recorder import record_website
import uuid
import os
from pathlib import Path
from asgiref.wsgi import WsgiToAsgi  # Import the adapter

app = Flask(__name__)

# Configure static file serving
VIDEOS_DIR = Path("videos")
VIDEOS_DIR.mkdir(exist_ok=True)
app.config['STATIC_FOLDER'] = str(VIDEOS_DIR)

# Create a queue for video recording tasks
recording_queue = asyncio.Queue()
# Track active recordings
current_recordings = {}

async def process_recording_queue():
    """Background task to process the recording queue"""
    print("Queue processor started!")
    while True:
        try:
            # Get the next recording task from the queue
            task_data = await recording_queue.get()
            request_id = task_data['request_id']
            url = task_data['url']
            
            try:
                # Record the website
                video_path = await record_website(url, request_id)
                # Store the result
                current_recordings[request_id] = {
                    'status': 'completed',
                    'video_url': f'videos/{request_id}/{os.path.basename(video_path)}',
                    'error': None
                }
            except Exception as e:
                current_recordings[request_id] = {
                    'status': 'failed',
                    'video_url': None,
                    'error': str(e)
                }
            finally:
                recording_queue.task_done()
                
        except Exception as e:
            print(f"Error processing queue: {e}")
            await asyncio.sleep(1)  # Prevent tight loop on persistent errors

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
        
        # Add recording task to queue
        current_recordings[request_id] = {'status': 'queued', 'video_url': None, 'error': None}
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
    if request_id not in current_recordings:
        return jsonify({'error': 'Request ID not found'}), 404
    
    recording_status = current_recordings[request_id]
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