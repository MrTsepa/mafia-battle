"""
Web server for viewing saved game runs.
"""

import os
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from flask import Flask, render_template, jsonify

from .run_recorder import RunRecorder


class ViewerServer:
    """Web server for viewing saved game runs."""
    
    def __init__(self, port: int = 5000, host: str = '127.0.0.1', runs_dir: str = "runs"):
        self.port = port
        self.host = host
        self.runs_dir = Path(runs_dir)
        self.run_recorder = RunRecorder(runs_dir=runs_dir)
        
        # Get the directory where this module is located
        base_dir = os.path.dirname(os.path.abspath(__file__))
        template_dir = os.path.join(base_dir, 'templates')
        static_dir = os.path.join(base_dir, 'static')
        
        self.app = Flask(__name__, 
                        template_folder=template_dir,
                        static_folder=static_dir)
        
        # Setup routes
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup Flask routes."""
        @self.app.route('/')
        def index():
            return render_template('run_viewer.html')
        
        @self.app.route('/api/runs')
        def list_runs():
            """List all available runs."""
            runs = self.run_recorder.list_runs()
            return jsonify(runs)
        
        @self.app.route('/api/runs/<run_name>/events')
        def get_events(run_name: str):
            """Get events for a specific run."""
            run_dir = self.runs_dir / run_name
            events_file = run_dir / "events.jsonl"
            
            if not events_file.exists():
                return jsonify({"error": "Run not found"}), 404
            
            events = []
            try:
                with open(events_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            events.append(json.loads(line))
            except Exception as e:
                return jsonify({"error": str(e)}), 500
            
            return jsonify(events)
        
        @self.app.route('/api/runs/<run_name>/metadata')
        def get_metadata(run_name: str):
            """Get metadata for a specific run."""
            run_dir = self.runs_dir / run_name
            metadata_file = run_dir / "metadata.json"
            
            if not metadata_file.exists():
                return jsonify({"error": "Run not found"}), 404
            
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                return jsonify(metadata)
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        @self.app.route('/api/runs/<run_name>/events/stream')
        def stream_events(run_name: str):
            """Stream events for a specific run (for live updates)."""
            from flask import request
            
            run_dir = self.runs_dir / run_name
            events_file = run_dir / "events.jsonl"
            
            if not events_file.exists():
                return jsonify({"error": "Run not found"}), 404
            
            # Read last position from query param
            last_position = int(request.args.get('last_position', 0))
            
            events = []
            current_position = 0
            try:
                with open(events_file, 'r') as f:
                    for line in f:
                        current_position += 1
                        if current_position > last_position and line.strip():
                            events.append(json.loads(line))
            except Exception as e:
                return jsonify({"error": str(e)}), 500
            
            return jsonify({
                "events": events,
                "position": current_position,
                "has_more": False  # For now, always return all remaining events
            })
    
    def start(self) -> None:
        """Start the web server."""
        print(f"\n{'='*60}")
        print(f"Starting viewer server on http://{self.host}:{self.port}")
        print(f"Runs directory: {self.runs_dir}")
        print(f"{'='*60}\n")
        self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False)

