"""
Base agent interface for Mafia game players.
"""

from typing import Dict, List, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..core import Player, GameState, GamePhase, RoleType
from ..config.game_config import GameConfig, default_config


@dataclass
class AgentContext:
    """Context information provided to an agent."""
    player: Player
    game_state: GameState
    public_history: List[Dict[str, Any]]
    private_info: Dict[str, Any]
    current_phase: GamePhase
    available_actions: List[str]


class BaseAgent(ABC):
    """
    Abstract base class for all player agents.
    
    This defines the interface that all agent implementations must follow.
    """
    
    def __init__(self, player: Player, config: GameConfig = default_config):
        """
        Initialize the agent.
        
        Args:
            player: The player this agent represents
            config: Game configuration
        """
        self.player = player
        self.config = config
    
    @abstractmethod
    def get_day_speech(self, context: AgentContext) -> str:
        """
        Generate a day phase speech.
        
        Args:
            context: Current game context
            
        Returns:
            The speech text
        """
        pass
    
    @abstractmethod
    def get_night_action(self, context: AgentContext) -> Dict[str, Any]:
        """
        Get night phase action (kill claim, check, etc.).
        
        Args:
            context: Current game context
            
        Returns:
            Dictionary containing action type and target
        """
        pass
    
    def get_final_speech(self, context: AgentContext) -> str:
        """
        Generate a final speech when eliminated.
        
        Args:
            context: Current game context
            
        Returns:
            The final speech text
        """
        # Default implementation: use day speech
        return self.get_day_speech(context)
    
    @abstractmethod
    def get_vote_choice(self, context: AgentContext) -> int:
        """
        Get voting choice.
        
        Args:
            context: Current game context
            
        Returns:
            Player number to vote against
        """
        pass
    
    def build_context(self, game_state: GameState) -> AgentContext:
        """
        Build context for the agent.
        
        Args:
            game_state: Current game state
            
        Returns:
            AgentContext with all relevant information
        """
        # Get public history (speeches, nominations, votes, eliminations)
        public_history = self._get_public_history(game_state)
        
        # Get private information
        private_info = self.player.get_private_info()
        
        # Determine available actions based on phase
        available_actions = self._get_available_actions(game_state)
        
        return AgentContext(
            player=self.player,
            game_state=game_state,
            public_history=public_history,
            private_info=private_info,
            current_phase=game_state.phase,
            available_actions=available_actions
        )
    
    def _get_public_history(self, game_state: GameState) -> List[Dict[str, Any]]:
        """
        Extract public game history.
        
        Args:
            game_state: Current game state
            
        Returns:
            List of public game events
        """
        history = []
        
        # Add speeches with day information
        # Match speeches to days: speeches happen before nominations in the same day
        # Strategy: If a player nominated on day X, their speech on that day happened before the nomination
        all_speeches = []
        for player in game_state.players:
            for i, speech in enumerate(player.speeches):
                all_speeches.append({
                    "type": "speech",
                    "player": player.player_number,
                    "speech": speech,
                    "index": i
                })
        
        # Match speeches to days
        # Strategy: Each player speaks once per day during day phases
        # Use nominations as anchors, then distribute remaining speeches evenly
        
        # Track speeches per player per day
        player_speech_counts = {}  # {player_num: {day: count}}
        for player in game_state.players:
            player_speech_counts[player.player_number] = {}
        
        # First pass: match speeches to days based on nominations
        # If a player nominated on day X, their first speech is likely from that day
        for speech_data in all_speeches:
            player_num = speech_data["player"]
            day_for_speech = None
            
            # Check if this player nominated on any day
            for day in sorted(game_state.nominations.keys()):
                if player_num in game_state.nominations[day]:
                    # Count how many speeches this player has made so far (before this one)
                    player_speech_index = sum(1 for s in all_speeches[:all_speeches.index(speech_data)] if s["player"] == player_num)
                    # If this is their first speech, it's likely from the day they nominated
                    if player_speech_index == 0:
                        day_for_speech = day
                        break
            
            speech_data["day"] = day_for_speech
            if day_for_speech:
                if day_for_speech not in player_speech_counts[player_num]:
                    player_speech_counts[player_num][day_for_speech] = 0
                player_speech_counts[player_num][day_for_speech] += 1
        
        # Second pass: assign remaining speeches to days in order
        # Distribute speeches evenly across days, ensuring each player has at most one speech per day
        speeches_per_day = {}
        all_days = sorted(set(game_state.nominations.keys()) | {game_state.day_number})
        for d in all_days:
            speeches_per_day[d] = 0
        
        for speech_data in all_speeches:
            if speech_data.get("day") is None:
                player_num = speech_data["player"]
                # Find a day where this player hasn't spoken yet
                day_for_speech = None
                
                # Try to assign to existing days first
                for day in all_days:
                    if day not in player_speech_counts[player_num]:
                        day_for_speech = day
                        break
                
                # If player has spoken on all days, assign to day with fewest total speeches
                if day_for_speech is None:
                    day_for_speech = min(all_days, key=lambda d: speeches_per_day.get(d, 0))
                
                speech_data["day"] = day_for_speech
                if day_for_speech not in player_speech_counts[player_num]:
                    player_speech_counts[player_num][day_for_speech] = 0
                player_speech_counts[player_num][day_for_speech] += 1
                speeches_per_day[day_for_speech] = speeches_per_day.get(day_for_speech, 0) + 1
            else:
                # Already assigned, count it
                day = speech_data["day"]
                speeches_per_day[day] = speeches_per_day.get(day, 0) + 1
        
        # Add all speeches to history with approximate timestamps
        # Speeches happen in order during day phases, so assign sequential timestamps
        # Use day number and speech order to create approximate timestamps
        for idx, speech_data in enumerate(all_speeches):
            day = speech_data.get("day", game_state.day_number)
            # Create approximate timestamp: speeches happen sequentially during the day
            # Count speeches on the same day that come before this one
            speech_index = sum(1 for i, s in enumerate(all_speeches) if i < idx and s.get("day") == day) + 1
            # Format: "Day X, Speech Y" or approximate time
            speech_data["timestamp"] = f"Day {day}, Speech #{speech_index}"
            history.append(speech_data)
        
        # Add nominations
        for day, nominations in game_state.nominations.items():
            for nom in nominations:
                history.append({
                    "type": "nomination",
                    "day": day,
                    "target": nom
                })
        
        # Add votes (public after voting)
        for day, votes in game_state.votes.items():
            history.append({
                "type": "votes",
                "day": day,
                "votes": votes.copy()
            })
        
        # Add eliminations (with day information and voters)
        for action in game_state.action_log:
            if action["type"] == "player_eliminated":
                history.append({
                    "type": "elimination",
                    "player": action["data"]["player"],
                    "reason": action["data"]["reason"],
                    "day": action["data"].get("day_number"),  # Include day number if available
                    "night": action["data"].get("night_number"),  # Include night number if available
                    "voters": action["data"].get("voters", [])  # Include voters if available
                })
        
        return history
    
    def _get_available_actions(self, game_state: GameState) -> List[str]:
        """
        Get available actions for current phase.
        
        Args:
            game_state: Current game state
            
        Returns:
            List of available action names
        """
        actions = []
        
        if game_state.phase == GamePhase.DAY:
            actions.append("speak")
            actions.append("nominate")
        
        elif game_state.phase == GamePhase.VOTING:
            actions.append("vote")
        
        elif game_state.phase == GamePhase.NIGHT:
            if self.player.is_mafia:
                actions.append("claim_kill_target")
                # Check if Don is eliminated - if so, any mafia can decide kill
                don = next((p for p in game_state.get_mafia_players() 
                           if p.role.role_type == RoleType.DON and p.is_alive), None)
                if not don:
                    actions.append("decide_kill")  # Mafia can decide if Don is eliminated
            if self.player.role.role_type == RoleType.DON:
                actions.append("don_check")
                actions.append("decide_kill")  # Don decides final kill
            if self.player.role.role_type == RoleType.SHERIFF:
                actions.append("sheriff_check")
        
        return actions

