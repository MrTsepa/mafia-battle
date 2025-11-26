"""
Game configuration and constants.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict


@dataclass
class GameConfig:
    """Configuration for game parameters."""
    
    # Speech limits
    max_speech_tokens: int = 16000  # Max tokens for speeches (gpt-5 models need extra for reasoning)
    tie_break_speech_tokens: int = 1000  # Max tokens for tie-break speeches
    
    # Time limits (for LLM response time)
    night_action_timeout: int = 10  # seconds
    voting_window: float = 1.5  # seconds
    
    # LLM settings
    llm_model: str = "gpt-4"
    llm_temperature: float = 0.7
    max_retries: int = 3
    max_action_tokens: int = 16000  # Max tokens for night actions and voting (gpt-5 models need extra for reasoning)
    
    # Game settings
    total_players: int = 10
    log_level: str = "INFO"
    max_rounds: int = 10  # Maximum number of day/night cycles before game ends
    
    # Judge announcements
    use_judge_announcements: bool = True

    # Agent settings
    agent_type: str = "simple_llm_agent"  # Options: "simple_llm_agent" or "dummy_agent" (used if agent_types not specified)
    agent_types: Optional[Dict[int, str]] = field(default=None)  # Per-player agent types: {player_number: "agent_type"}
    random_seed: Optional[int] = None  # Random seed for reproducible behavior (used by dummy_agent)


# Default configuration instance
default_config = GameConfig()

