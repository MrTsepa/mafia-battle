"""
Player class representing a game participant.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

from .roles import Role, Team


class PlayerStatus(Enum):
    """Player status in the game."""
    ALIVE = "alive"
    ELIMINATED = "eliminated"
    DISQUALIFIED = "disqualified"


@dataclass
class Player:
    """Represents a player in the game."""
    player_number: int
    role: Role
    status: PlayerStatus = PlayerStatus.ALIVE
    
    # Game history
    speeches: List[str] = field(default_factory=list)
    nominations_made: List[int] = field(default_factory=list)  # Player numbers nominated
    votes_cast: Dict[int, int] = field(default_factory=dict)  # {day_number: voted_player}
    
    # Private information (role-specific)
    known_mafia: List[int] = field(default_factory=list)  # For mafia players
    sheriff_checks: Dict[int, Dict[str, Any]] = field(default_factory=dict)  # {night_number: {"target": player_num, "result": "Red"/"Black"}}
    don_checks: Dict[int, Dict[str, Any]] = field(default_factory=dict)  # {night_number: {"target": player_num, "result": "Sheriff"/"Not the Sheriff"}}
    
    # Night actions
    mafia_kill_claims: Dict[int, int] = field(default_factory=dict)  # {night_number: target}
    mafia_kill_decisions: Dict[int, int] = field(default_factory=dict)  # {night_number: target} (Don only)
    
    def __str__(self) -> str:
        return f"Player {self.player_number} ({self.role.role_type.value})"
    
    @property
    def is_alive(self) -> bool:
        """Check if player is alive."""
        return self.status == PlayerStatus.ALIVE
    
    @property
    def is_mafia(self) -> bool:
        """Check if player is mafia team."""
        return self.role.is_mafia
    
    @property
    def is_civilian(self) -> bool:
        """Check if player is civilian team."""
        return self.role.is_civilian
    
    def add_speech(self, speech: str) -> None:
        """Add a speech to player's history."""
        self.speeches.append(speech)
    
    def nominate(self, target_number: int, day_number: int) -> bool:
        """
        Record a nomination.
        Returns True if nomination is valid (first nomination of the day).
        """
        if target_number not in self.nominations_made:
            self.nominations_made.append(target_number)
            return True
        return False
    
    def vote(self, target_number: int, day_number: int) -> None:
        """Record a vote."""
        self.votes_cast[day_number] = target_number
    
    def add_sheriff_check(self, night_number: int, target: int, result: str) -> None:
        """Record a Sheriff check result."""
        self.sheriff_checks[night_number] = {"target": target, "result": result}
    
    def add_don_check(self, night_number: int, target: int, result: str) -> None:
        """Record a Don check result."""
        self.don_checks[night_number] = {"target": target, "result": result}
    
    def add_mafia_kill_claim(self, night_number: int, target: int) -> None:
        """Record a mafia kill claim."""
        self.mafia_kill_claims[night_number] = target
    
    def add_mafia_kill_decision(self, night_number: int, target: int) -> None:
        """Record a Don's kill decision."""
        self.mafia_kill_decisions[night_number] = target
    
    def eliminate(self) -> None:
        """Mark player as eliminated."""
        self.status = PlayerStatus.ELIMINATED
    
    def disqualify(self) -> None:
        """Mark player as disqualified."""
        self.status = PlayerStatus.DISQUALIFIED
    
    def get_private_info(self) -> Dict[str, Any]:
        """Get player's private information based on their role."""
        info = {}
        
        if self.is_mafia:
            info["known_mafia"] = self.known_mafia
            info["mafia_kill_claims"] = self.mafia_kill_claims
            if self.role.role_type.value == "don":
                info["don_checks"] = self.don_checks
                info["mafia_kill_decisions"] = self.mafia_kill_decisions
        
        if self.role.role_type.value == "sheriff":
            info["sheriff_checks"] = self.sheriff_checks
        
        return info

