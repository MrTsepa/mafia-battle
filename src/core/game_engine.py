"""
Core game engine managing game state and phase transitions.
"""

import random
from enum import Enum
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass, field

from .roles import Role, RoleType, Team, get_role_distribution, create_role
from .player import Player, PlayerStatus

if TYPE_CHECKING:
    from ..web.event_emitter import EventEmitter


class GamePhase(Enum):
    """Current game phase."""
    SETUP = "setup"
    NIGHT = "night"
    DAY = "day"
    VOTING = "voting"
    GAME_OVER = "game_over"
    FAILED = "failed"  # Game failed due to fatal error (e.g., LLM API failure)


@dataclass
class GameState:
    """Complete game state."""
    phase: GamePhase = GamePhase.SETUP
    day_number: int = 0
    night_number: int = 0
    players: List[Player] = field(default_factory=list)
    
    # Day phase
    current_speaker: Optional[int] = None
    nominations: Dict[int, List[int]] = field(default_factory=dict)  # {day_number: [player_numbers]}
    votes: Dict[int, Dict[int, int]] = field(default_factory=dict)  # {day_number: {player: target}}
    
    # Night phase
    night_kills: Dict[int, Optional[int]] = field(default_factory=dict)  # {night_number: killed_player}
    
    # Game history
    action_log: List[Dict[str, Any]] = field(default_factory=list)
    
    # Win condition
    winner: Optional[Team] = None
    max_rounds: Optional[int] = None  # Maximum rounds (days) before game ends
    random_seed: Optional[int] = None  # Random seed for reproducible role assignment
    
    # Event emitter for web interface (optional)
    event_emitter: Optional['EventEmitter'] = None
    
    def __post_init__(self):
        """Initialize game state."""
        if not self.players:
            self.setup_game()
    
    def setup_game(self) -> None:
        """Initialize game with 10 players and random role assignment."""
        role_distribution = get_role_distribution()
        # Use seeded random if seed is provided
        if self.random_seed is not None:
            rng = random.Random(self.random_seed)
            rng.shuffle(role_distribution)
        else:
            random.shuffle(role_distribution)
        
        self.players = []
        for player_num in range(1, 11):
            role_type = role_distribution[player_num - 1]
            role = create_role(role_type, player_num)
            player = Player(player_number=player_num, role=role)
            self.players.append(player)
        
        # Provide mafia knowledge to mafia players
        self._provide_mafia_knowledge()
        
        # Start with DAY 1 (no night before first day)
        self.phase = GamePhase.DAY
        self.day_number = 1
        self.night_number = 0
        self._log_action("game_start", {"players": len(self.players)})
    
    def _provide_mafia_knowledge(self) -> None:
        """Provide all mafia identities to mafia team players."""
        mafia_players = [p for p in self.players if p.is_mafia]
        mafia_numbers = [p.player_number for p in mafia_players]
        
        for player in mafia_players:
            player.known_mafia = mafia_numbers.copy()
    
    def get_alive_players(self) -> List[Player]:
        """Get all alive players."""
        return [p for p in self.players if p.is_alive]
    
    def get_player(self, player_number: int) -> Optional[Player]:
        """Get player by number."""
        for player in self.players:
            if player.player_number == player_number:
                return player
        return None
    
    def get_mafia_players(self) -> List[Player]:
        """Get all alive mafia players."""
        return [p for p in self.get_alive_players() if p.is_mafia]
    
    def get_civilian_players(self) -> List[Player]:
        """Get all alive civilian players."""
        return [p for p in self.get_alive_players() if p.is_civilian]
    
    def start_night(self) -> None:
        """Transition to night phase."""
        self.phase = GamePhase.NIGHT
        self.night_number += 1
        self._log_action("night_start", {"night_number": self.night_number})
    
    def start_day(self) -> None:
        """Transition to day phase."""
        self.phase = GamePhase.DAY
        self.day_number += 1
        self.current_speaker = None
        self.nominations[self.day_number] = []
        self._log_action("day_start", {"day_number": self.day_number})
    
    def start_voting(self) -> None:
        """Transition to voting phase."""
        self.phase = GamePhase.VOTING
        self.votes[self.day_number] = {}
        self._log_action("voting_start", {"day_number": self.day_number})
    
    def check_win_condition(self) -> Optional[Team]:
        """
        Check if game has ended and return winning team.
        Returns None if game continues.
        """
        # Check max rounds limit
        if self.max_rounds is not None and self.day_number >= self.max_rounds:
            # Game ends due to max rounds - determine winner by current state
            alive_mafia = len(self.get_mafia_players())
            alive_civilians = len(self.get_civilian_players())
            
            # If mafia has majority or equal, they win
            if alive_mafia >= alive_civilians:
                return Team.BLACK
            # Otherwise civilians win
            return Team.RED
        
        alive_mafia = len(self.get_mafia_players())
        alive_civilians = len(self.get_civilian_players())
        
        # Red team wins: all mafia eliminated
        if alive_mafia == 0:
            return Team.RED
        
        # Black team wins: equal numbers or more mafia than civilians
        if alive_mafia >= alive_civilians:
            return Team.BLACK
        
        return None
    
    def eliminate_player(self, player_number: int, reason: str = "eliminated", 
                        night_number: Optional[int] = None, day_number: Optional[int] = None,
                        voters: Optional[List[int]] = None) -> None:
        """Eliminate a player."""
        player = self.get_player(player_number)
        if player and player.is_alive:
            player.eliminate()
            self._log_action("player_eliminated", {
                "player": player_number,
                "reason": reason,
                "night_number": night_number,
                "day_number": day_number,
                "voters": voters
            })
            
            # Emit elimination event
            if self.event_emitter:
                self.event_emitter.emit_elimination(
                    player_number, 
                    reason, 
                    day_number, 
                    night_number, 
                    voters
                )
                # Emit game state update
                self._emit_game_state_update()
            
            # Check win condition
            winner = self.check_win_condition()
            if winner:
                self.end_game(winner)
    
    def end_game(self, winner: Optional[Team] = None, reason: str = "win_condition") -> None:
        """End the game with a winner or failure."""
        if reason == "failed":
            self.phase = GamePhase.FAILED
            self.winner = None
        else:
            self.phase = GamePhase.GAME_OVER
            self.winner = winner
            self._log_action("game_over", {
                "winner": winner.value if winner else None,
                "reason": reason,
                "day_number": self.day_number,
                "night_number": self.night_number
            })
    
    def _log_action(self, action_type: str, data: Dict[str, Any]) -> None:
        """Log a game action."""
        self.action_log.append({
            "type": action_type,
            "phase": self.phase.value,
            "day": self.day_number,
            "night": self.night_number,
            "data": data
        })
    
    def get_game_summary(self) -> Dict[str, Any]:
        """Get a summary of the current game state."""
        alive_players = self.get_alive_players()
        return {
            "phase": self.phase.value,
            "day": self.day_number,
            "night": self.night_number,
            "alive_players": len(alive_players),
            "alive_mafia": len(self.get_mafia_players()),
            "alive_civilians": len(self.get_civilian_players()),
            "winner": self.winner.value if self.winner else None,
        }
    
    def _emit_game_state_update(self) -> None:
        """Emit game state update event."""
        if self.event_emitter:
            alive_players = self.get_alive_players()
            mafia_players = self.get_mafia_players()
            civilian_players = self.get_civilian_players()
            
            # Build player list with roles (always visible in viewer)
            players_data = []
            for player in self.players:
                role_name = player.role.role_type.value.title()
                team = "Red" if player.role.team.value == "red" else "Black"
                players_data.append({
                    "number": player.player_number,
                    "role": role_name,
                    "team": team,
                    "is_alive": player.is_alive
                })
            
            game_state = {
                "phase": self.phase.value,
                "day_number": self.day_number,
                "night_number": self.night_number,
                "alive_count": len(alive_players),
                "mafia_count": len(mafia_players),
                "civilian_count": len(civilian_players),
                "players": players_data,
                "winner": self.winner.value if self.winner else None
            }
            
            self.event_emitter.emit_game_state_update(game_state)

