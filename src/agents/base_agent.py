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
        # Final speeches happen after elimination on the day of elimination
        
        # First, identify elimination days for each player
        elimination_days = {}  # {player_num: day_number}
        for action in game_state.action_log:
            if action["type"] == "player_eliminated":
                player_num = action["data"]["player"]
                day = action["data"].get("day_number")
                if day:
                    elimination_days[player_num] = day
        
        all_speeches = []
        for player in game_state.players:
            for i, speech in enumerate(player.speeches):
                all_speeches.append({
                    "type": "speech",
                    "player": player.player_number,
                    "speech": speech,
                    "index": i,
                    "is_final": False  # Will be determined below
                })
        
        # Identify final speeches: if a player was eliminated, their last speech(s) after elimination are final speeches
        for player_num, elim_day in elimination_days.items():
            player_speeches = [s for s in all_speeches if s["player"] == player_num]
            if not player_speeches:
                continue
            
            # Count how many speeches this player made before elimination
            # A player typically speaks once per day they're alive
            # If they have more speeches than days alive, the extra ones are final speeches
            # For simplicity, if eliminated on day X, speeches after index (X-1) are likely final speeches
            # But we'll use a simpler heuristic: the last speech of an eliminated player is their final speech
            # Actually, final speeches are added AFTER elimination, so they're always the last speech(s)
            # If a player was eliminated on day X, check if their last speech should be on day X (final speech)
            
            # Mark the last speech as final if player was eliminated
            if player_speeches:
                player_speeches[-1]["is_final"] = True
                player_speeches[-1]["elimination_day"] = elim_day
        
        # Match speeches to days
        # Strategy: Each player speaks once per day during day phases
        # Use nominations as anchors, then distribute remaining speeches evenly
        # Final speeches go to the day of elimination
        
        # Track speeches per player per day
        player_speech_counts = {}  # {player_num: {day: count}}
        for player in game_state.players:
            player_speech_counts[player.player_number] = {}
        
        # First pass: assign final speeches to elimination day
        for speech_data in all_speeches:
            if speech_data.get("is_final") and "elimination_day" in speech_data:
                speech_data["day"] = speech_data["elimination_day"]
                player_num = speech_data["player"]
                elim_day = speech_data["elimination_day"]
                if elim_day not in player_speech_counts[player_num]:
                    player_speech_counts[player_num][elim_day] = 0
                player_speech_counts[player_num][elim_day] += 1
        
        # Second pass: assign remaining speeches to days in order
        # Distribute speeches evenly across days, ensuring each player has at most one speech per day
        speeches_per_day = {}
        
        # Find all days that have occurred: from 1 to max day with any activity
        # Include days with nominations, votes, eliminations, or current day
        activity_days = [game_state.day_number]
        if game_state.nominations:
            activity_days.extend(game_state.nominations.keys())
        if game_state.votes:
            activity_days.extend(game_state.votes.keys())
        for action in game_state.action_log:
            if action["type"] == "player_eliminated" and action["data"].get("day_number"):
                activity_days.append(action["data"]["day_number"])
        
        max_day_with_activity = max(activity_days) if activity_days else game_state.day_number
        # Always include all days from 1 to max_day_with_activity (at least day 1)
        all_days = list(range(1, max(max_day_with_activity, 1) + 1))
        for d in all_days:
            speeches_per_day[d] = 0
        
        # Group speeches by player to assign them sequentially
        # Preserve original order by sorting by index
        speeches_by_player = {}  # {player_num: [speech_data]}
        for speech_data in all_speeches:
            if speech_data.get("day") is None:
                player_num = speech_data["player"]
                if player_num not in speeches_by_player:
                    speeches_by_player[player_num] = []
                speeches_by_player[player_num].append(speech_data)
        
        # Sort speeches by player by their original index to preserve order
        for player_num in speeches_by_player:
            speeches_by_player[player_num].sort(key=lambda s: s.get("index", 0))
        
        # Assign speeches sequentially: each player's speeches go to consecutive days
        # starting from the first day they were alive
        for player_num, unassigned_speeches in speeches_by_player.items():
            # Find first day this player was alive (they could speak)
            # A player is alive on day X if they weren't eliminated before day X
            player = game_state.get_player(player_num)
            if not player:
                continue
            
            # Find elimination day for this player
            elim_day = None
            for action in game_state.action_log:
                if action["type"] == "player_eliminated":
                    if action["data"]["player"] == player_num:
                        elim_day = action["data"].get("day_number")
                        break
            
            # Determine which days this player was alive
            # Player is alive on day X if elim_day is None or elim_day > X
            available_days = [d for d in all_days if elim_day is None or elim_day > d]
            
            # Assign speeches sequentially to available days
            # Each speech goes to the next available day where player hasn't spoken yet
            # Each player should have at most one regular speech per day
            for idx, speech_data in enumerate(unassigned_speeches):
                # Find next day where this player hasn't spoken yet
                day_for_speech = None
                for day in available_days:
                    # Check if player has already spoken on this day (including final speeches)
                    if day not in player_speech_counts[player_num]:
                        day_for_speech = day
                        break
                
                # If all available days are used, this shouldn't happen normally
                # (each player should have at most one speech per day they're alive)
                # but if it does, assign to the day with fewest total speeches
                if day_for_speech is None:
                    # This is an edge case - player has more speeches than days alive
                    # Assign to the day with fewest total speeches to minimize impact
                    day_for_speech = min(available_days, key=lambda d: speeches_per_day.get(d, 0)) if available_days else all_days[0]
                
                speech_data["day"] = day_for_speech
                # Track that this player has spoken on this day
                if day_for_speech not in player_speech_counts[player_num]:
                    player_speech_counts[player_num][day_for_speech] = 0
                player_speech_counts[player_num][day_for_speech] += 1
                speeches_per_day[day_for_speech] = speeches_per_day.get(day_for_speech, 0) + 1
        
        # Count already assigned speeches
        for speech_data in all_speeches:
            if speech_data.get("day") is not None:
                day = speech_data["day"]
                speeches_per_day[day] = speeches_per_day.get(day, 0) + 1
        
        # Add all speeches to history with approximate timestamps
        # Speeches happen in order during day phases, so assign sequential timestamps
        # Use day number and speech order to create approximate timestamps
        for idx, speech_data in enumerate(all_speeches):
            day = speech_data.get("day", game_state.day_number)
            is_final = speech_data.get("is_final", False)
            
            if is_final:
                # Final speeches happen after elimination, so they get a special timestamp
                # They should appear after eliminations in chronological order
                speech_data["timestamp"] = f"Day {day}, Final Speech"
            else:
                # Create approximate timestamp: speeches happen sequentially during the day
                # Count speeches on the same day that come before this one
                speech_index = sum(1 for i, s in enumerate(all_speeches) if i < idx and s.get("day") == day and not s.get("is_final", False)) + 1
                # Format: "Day X, Speech Y" or approximate time
                speech_data["timestamp"] = f"Day {day}, Speech #{speech_index}"
            
            history.append(speech_data)
        
        # Add nominations
        # First, collect nomination rounds from action_log (for tie-break scenarios)
        nomination_rounds_by_day = {}  # {day: [nomination_round_events]}
        for action in game_state.action_log:
            if action["type"] == "nomination_round":
                day = action["data"].get("day")
                if day:
                    if day not in nomination_rounds_by_day:
                        nomination_rounds_by_day[day] = []
                    nomination_rounds_by_day[day].append(action["data"])
        
        # Add nomination rounds from action_log (chronologically ordered by round number)
        for day in sorted(nomination_rounds_by_day.keys()):
            rounds = sorted(nomination_rounds_by_day[day], key=lambda r: r.get("round", 0))
            for round_data in rounds:
                nominations = round_data.get("nominations", [])
                for nom in nominations:
                    history.append({
                        "type": "nomination",
                        "day": day,
                        "target": nom,
                        "round": round_data.get("round", 1),
                        "is_tie_break": round_data.get("is_tie_break", False)
                    })
        
        # Add current nominations (for days that don't have nomination rounds logged yet)
        for day, nominations in game_state.nominations.items():
            # Skip if we already have nomination rounds for this day
            if day not in nomination_rounds_by_day:
                for nom in nominations:
                    history.append({
                        "type": "nomination",
                        "day": day,
                        "target": nom
                    })
        
        # Add votes (public after voting)
        # First, add vote rounds from action_log (for tie-break scenarios)
        vote_rounds_by_day = {}  # {day: [vote_round_events]}
        for action in game_state.action_log:
            if action["type"] == "vote_round":
                day = action["data"].get("day")
                if day:
                    if day not in vote_rounds_by_day:
                        vote_rounds_by_day[day] = []
                    vote_rounds_by_day[day].append(action["data"])
        
        # Add vote rounds from action_log (chronologically ordered by round number)
        for day in sorted(vote_rounds_by_day.keys()):
            rounds = sorted(vote_rounds_by_day[day], key=lambda r: r.get("round", 0))
            for round_data in rounds:
                history.append({
                    "type": "votes",
                    "day": day,
                    "votes": round_data.get("votes", {}).copy(),
                    "round": round_data.get("round", 1),
                    "is_tie_break": round_data.get("is_tie_break", False)
                })
        
        # Add current votes (for days that don't have vote rounds logged yet)
        for day, votes in game_state.votes.items():
            # Skip if we already have vote rounds for this day
            if day not in vote_rounds_by_day and votes:
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
