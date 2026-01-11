"""
Event emitter for recording game events to files.
"""

from typing import Dict, Any, Optional, List
from threading import Lock

from .run_recorder import RunRecorder


class EventEmitter:
    """Event emitter that records game events to files."""
    
    def __init__(self, run_recorder: Optional[RunRecorder] = None):
        self.run_recorder = run_recorder or RunRecorder()
        self._lock = Lock()
    
    def _emit(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit an event by recording it to file."""
        if self.run_recorder:
            try:
                self.run_recorder.record_event(event_type, data)
            except Exception as e:
                # Don't let recording errors break the game
                print(f"Error recording event: {e}")
    
    def emit_game_start(self, players: List[int], mafia: List[int], sheriff: int, agent_types: Optional[Dict[int, str]] = None) -> None:
        """Emit game start event."""
        self._emit("game_start", {
            "players": players,
            "mafia": mafia,
            "sheriff": sheriff,
            "agent_types": agent_types or {}
        })
    
    def emit_phase_change(self, phase: str, day_number: int, night_number: int) -> None:
        """Emit phase change event."""
        self._emit("phase_change", {
            "phase": phase,
            "day_number": day_number,
            "night_number": night_number
        })
    
    def emit_speech(self, player_number: int, speech: str, day_number: int, context: Optional[Dict[str, Any]] = None) -> None:
        """Emit player speech event."""
        self._emit("speech", {
            "player_number": player_number,
            "speech": speech,
            "day_number": day_number,
            "context": context  # Include LLM context/prompt if available
        })
    
    def emit_nomination(self, nominator: int, target: int, success: bool, day_number: int, context: Optional[Dict[str, Any]] = None) -> None:
        """Emit nomination event."""
        self._emit("nomination", {
            "nominator": nominator,
            "target": target,
            "success": success,
            "day_number": day_number,
            "context": context  # Include LLM context/prompt if available
        })
    
    def emit_voting_start(self, nominations: List[int], day_number: int) -> None:
        """Emit voting phase start event."""
        self._emit("voting_start", {
            "nominations": nominations,
            "day_number": day_number
        })
    
    def emit_vote(self, voter: int, target: int, day_number: int, context: Optional[Dict[str, Any]] = None) -> None:
        """Emit individual vote event."""
        self._emit("vote", {
            "voter": voter,
            "target": target,
            "day_number": day_number,
            "context": context  # Include LLM context/prompt if available
        })
    
    def emit_vote_results(self, vote_counts: Dict[int, int], voters: Dict[int, List[int]], day_number: int) -> None:
        """Emit voting results event."""
        self._emit("vote_results", {
            "vote_counts": vote_counts,
            "voters": voters,
            "day_number": day_number
        })
    
    def emit_tie(self, tied_players: List[int], day_number: int) -> None:
        """Emit tie detection event."""
        self._emit("tie", {
            "tied_players": tied_players,
            "day_number": day_number
        })
    
    def emit_elimination(self, player_number: int, reason: str, day_number: Optional[int] = None, 
                        night_number: Optional[int] = None, voters: Optional[List[int]] = None) -> None:
        """Emit player elimination event."""
        self._emit("elimination", {
            "player_number": player_number,
            "reason": reason,
            "day_number": day_number,
            "night_number": night_number,
            "voters": voters or []
        })
    
    def emit_night_kill_claim(self, player_number: int, target: int, night_number: int, context: Optional[Dict[str, Any]] = None) -> None:
        """Emit mafia kill claim event."""
        self._emit("night_kill_claim", {
            "player_number": player_number,
            "target": target,
            "night_number": night_number,
            "context": context  # Include LLM context/prompt if available
        })
    
    def emit_night_kill_decision(self, decision_maker: int, target: int, is_don: bool, night_number: int, context: Optional[Dict[str, Any]] = None) -> None:
        """Emit mafia kill decision event."""
        self._emit("night_kill_decision", {
            "decision_maker": decision_maker,
            "target": target,
            "is_don": is_don,
            "night_number": night_number,
            "context": context  # Include LLM context/prompt if available
        })
    
    def emit_don_check(self, target: int, result: str, night_number: int, context: Optional[Dict[str, Any]] = None) -> None:
        """Emit Don check event."""
        self._emit("don_check", {
            "target": target,
            "result": result,
            "night_number": night_number,
            "context": context  # Include LLM context/prompt if available
        })
    
    def emit_sheriff_check(self, target: int, result: str, night_number: int, context: Optional[Dict[str, Any]] = None) -> None:
        """Emit Sheriff check event."""
        self._emit("sheriff_check", {
            "target": target,
            "result": result,
            "night_number": night_number,
            "context": context  # Include LLM context/prompt if available
        })
    
    def emit_announcement(self, message: str, phase: str, day_number: int, night_number: int) -> None:
        """Emit judge announcement event."""
        self._emit("announcement", {
            "message": message,
            "phase": phase,
            "day_number": day_number,
            "night_number": night_number
        })
    
    def emit_game_state_update(self, game_state: Dict[str, Any]) -> None:
        """Emit game state update event."""
        self._emit("game_state_update", {
            "game_state": game_state
        })
    
    def emit_game_over(self, winner: Optional[str], reason: str, day_number: int, night_number: int) -> None:
        """Emit game over event."""
        self._emit("game_over", {
            "winner": winner,
            "reason": reason,
            "day_number": day_number,
            "night_number": night_number
        })
    
    def emit_fatal_error(self, error_message: str, player_number: Optional[int] = None, action_type: Optional[str] = None) -> None:
        """Emit fatal error event."""
        self._emit("fatal_error", {
            "error_message": error_message,
            "player_number": player_number,
            "action_type": action_type
        })
    
    def emit_llm_metadata(self, player_number: int, action_type: str, prompt_tokens: int, 
                         completion_tokens: int, total_tokens: int, latency_ms: float, 
                         model: str, reasoning_tokens: int = 0, reasoning_effort: Optional[str] = None) -> None:
        """Emit LLM API call metadata (tokens, latency, reasoning effort)."""
        self._emit("llm_metadata", {
            "player_number": player_number,
            "action_type": action_type,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "latency_ms": latency_ms,
            "model": model,
            "reasoning_tokens": reasoning_tokens,
            "reasoning_effort": reasoning_effort
        })

