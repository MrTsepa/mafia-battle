"""
Web server for live game viewing.
"""

import os
import threading
import time
from typing import Optional, Dict, Any
from flask import Flask, render_template
from flask_socketio import SocketIO, emit

from .event_emitter import EventEmitter


class GameServer:
    """Web server for streaming game events to browser clients."""
    
    def __init__(self, port: int = 5000, host: str = '127.0.0.1', event_emitter: Optional[EventEmitter] = None):
        self.port = port
        self.host = host
        
        # Get the directory where this module is located
        base_dir = os.path.dirname(os.path.abspath(__file__))
        template_dir = os.path.join(base_dir, 'templates')
        static_dir = os.path.join(base_dir, 'static')
        
        self.app = Flask(__name__, 
                        template_folder=template_dir,
                        static_folder=static_dir)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode='threading')
        self.event_emitter = event_emitter or EventEmitter()
        self.game_thread: Optional[threading.Thread] = None
        self.game_instance = None
        self.clients_connected = 0
        
        # Register event emitter listener
        self.event_emitter.register_listener(self._broadcast_event)
        
        # Setup routes
        self._setup_routes()
        
        # Setup socketio handlers
        self._setup_socketio()
    
    def _setup_routes(self):
        """Setup Flask routes."""
        @self.app.route('/')
        def index():
            return render_template('game_view.html')
    
    def _setup_socketio(self):
        """Setup SocketIO event handlers."""
        @self.socketio.on('connect')
        def handle_connect():
            self.clients_connected += 1
            print(f"Client connected. Total clients: {self.clients_connected}")
            
            # Send current game state if game is running
            if self.game_instance:
                game_state = self._get_game_state()
                emit('game_state_update', {'game_state': game_state})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            self.clients_connected -= 1
            print(f"Client disconnected. Total clients: {self.clients_connected}")
    
    def _broadcast_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Broadcast an event to all connected clients."""
        if self.clients_connected > 0:
            self.socketio.emit(event_type, data)
    
    def _get_game_state(self) -> Dict[str, Any]:
        """Get current game state for initial connection."""
        if not self.game_instance:
            return {}
        
        game_state = self.game_instance.game_state
        alive_players = game_state.get_alive_players()
        mafia_players = game_state.get_mafia_players()
        civilian_players = game_state.get_civilian_players()
        
        # Build player list with roles (hidden for alive players)
        players_data = []
        for player in game_state.players:
            role_name = player.role.role_type.value.title() if not player.is_alive else "Unknown"
            team = "Red" if player.role.team.value == "red" else "Black"
            players_data.append({
                "number": player.player_number,
                "role": role_name,
                "team": team,
                "is_alive": player.is_alive
            })
        
        return {
            "phase": game_state.phase.value,
            "day_number": game_state.day_number,
            "night_number": game_state.night_number,
            "alive_count": len(alive_players),
            "mafia_count": len(mafia_players),
            "civilian_count": len(civilian_players),
            "players": players_data,
            "winner": game_state.winner.value if game_state.winner else None
        }
    
    def run_game_in_background(self, game_instance) -> None:
        """Run game in background thread."""
        self.game_instance = game_instance
        
        def run_game():
            try:
                winner = game_instance.run_game(web_mode=True)
                print(f"\nGame completed. Winner: {winner}")
            except Exception as e:
                print(f"\nError running game: {e}")
                import traceback
                traceback.print_exc()
        
        self.game_thread = threading.Thread(target=run_game, daemon=True)
        self.game_thread.start()
    
    def start(self) -> None:
        """Start the web server."""
        print(f"\n{'='*60}")
        print(f"Starting web server on http://{self.host}:{self.port}")
        print(f"{'='*60}\n")
        self.socketio.run(self.app, host=self.host, port=self.port, debug=False, allow_unsafe_werkzeug=True)
    
    def wait_for_game_completion(self) -> None:
        """Wait for game thread to complete."""
        if self.game_thread:
            self.game_thread.join()

