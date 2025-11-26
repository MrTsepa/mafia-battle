"""
Pytest fixtures for Mafia game tests.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import Dict

from src.core import (
    GameState, GamePhase, Player, PlayerStatus,
    Role, RoleType, Team, create_role, Judge
)
from src.agents import SimpleLLMAgent, AgentContext
from src.config.game_config import GameConfig


@pytest.fixture(autouse=True)
def mock_llm_calls():
    """
    Automatically mock all LLM API calls for all tests.
    
    This fixture ensures that no real API calls are ever made during testing,
    even if a test accidentally doesn't mock the high-level methods
    (get_day_speech, get_night_action, get_vote_choice).
    
    All tests should still mock the high-level methods for proper behavior,
    but this provides an extra safety layer to prevent any real API calls.
    """
    with patch.object(SimpleLLMAgent, '_call_llm', return_value=""):
        yield


@pytest.fixture
def game_config():
    """Test game configuration."""
    return GameConfig(
        max_speech_tokens=400,
        tie_break_speech_tokens=200,
        use_judge_announcements=False  # Disable for cleaner test output
    )


@pytest.fixture
def game_state():
    """Create a fresh game state."""
    state = GameState()
    state.setup_game()
    return state


@pytest.fixture
def judge(game_state, game_config):
    """Create a judge instance."""
    return Judge(game_state, game_config)


@pytest.fixture
def mock_agents(game_state, game_config) -> Dict[int, SimpleLLMAgent]:
    """Create mock LLM agents for all players."""
    agents = {}
    for player in game_state.players:
        agent = SimpleLLMAgent(player, game_config)
        agents[player.player_number] = agent
    return agents


@pytest.fixture
def mafia_player(game_state) -> Player:
    """Get a mafia player."""
    mafia_players = game_state.get_mafia_players()
    return mafia_players[0] if mafia_players else None


@pytest.fixture
def civilian_player(game_state) -> Player:
    """Get a civilian player."""
    civilians = game_state.get_civilian_players()
    return civilians[0] if civilians else None


@pytest.fixture
def sheriff_player(game_state) -> Player:
    """Get the sheriff player."""
    for player in game_state.players:
        if player.role.role_type == RoleType.SHERIFF:
            return player
    return None


@pytest.fixture
def don_player(game_state) -> Player:
    """Get the don player."""
    for player in game_state.players:
        if player.role.role_type == RoleType.DON:
            return player
    return None


def create_mock_agent_response(response_text: str):
    """Helper to create a mock LLM response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = response_text
    return mock_response

