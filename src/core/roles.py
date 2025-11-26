"""
Role definitions and abilities for the Mafia game.
"""

from enum import Enum
from typing import List, Optional
from dataclasses import dataclass


class Team(Enum):
    """Player team affiliation."""
    RED = "red"  # Civilians
    BLACK = "black"  # Mafia


class RoleType(Enum):
    """Player role types."""
    CIVILIAN = "civilian"
    SHERIFF = "sheriff"
    MAFIA = "mafia"
    DON = "don"


@dataclass
class Role:
    """Represents a player's role in the game."""
    role_type: RoleType
    team: Team
    player_number: int
    
    def __str__(self) -> str:
        return f"{self.role_type.value} (Team: {self.team.value})"
    
    @property
    def is_mafia(self) -> bool:
        """Check if role is part of mafia team."""
        return self.team == Team.BLACK
    
    @property
    def is_civilian(self) -> bool:
        """Check if role is part of civilian team."""
        return self.team == Team.RED
    
    @property
    def has_night_action(self) -> bool:
        """Check if role has a night phase action."""
        return self.role_type in [RoleType.SHERIFF, RoleType.DON]
    
    @property
    def can_check(self) -> bool:
        """Check if role can perform checks."""
        return self.role_type in [RoleType.SHERIFF, RoleType.DON]


def create_role(role_type: RoleType, player_number: int) -> Role:
    """Create a role with appropriate team assignment."""
    team = Team.BLACK if role_type in [RoleType.MAFIA, RoleType.DON] else Team.RED
    return Role(role_type=role_type, team=team, player_number=player_number)


def get_role_distribution() -> List[RoleType]:
    """
    Get the standard role distribution for a 10-player game.
    Returns: 7 RED (6 civilians + 1 sheriff) and 3 BLACK (2 mafia + 1 don)
    """
    return [
        RoleType.CIVILIAN,
        RoleType.CIVILIAN,
        RoleType.CIVILIAN,
        RoleType.CIVILIAN,
        RoleType.CIVILIAN,
        RoleType.CIVILIAN,
        RoleType.SHERIFF,  # 1 Sheriff
        RoleType.MAFIA,
        RoleType.MAFIA,  # 2 Mafia
        RoleType.DON,  # 1 Don
    ]


def get_mafia_roles() -> List[RoleType]:
    """Get all mafia team roles."""
    return [RoleType.MAFIA, RoleType.DON]

