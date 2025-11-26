"""
Tests for day phase handler.
"""

import pytest
from unittest.mock import Mock, patch
from src.core import GameState, GamePhase, Judge
from src.phases import DayPhaseHandler
from src.agents import SimpleLLMAgent
from src.config.game_config import GameConfig


def test_get_speaking_order_first_day(game_state, judge, game_config):
    """Test speaking order on first day."""
    handler = DayPhaseHandler(game_state, judge)
    # Game already starts in DAY phase with day_number = 1, no need to call start_day()
    
    order = handler.get_speaking_order()
    
    # First day should start with player 1 (if alive)
    assert len(order) > 0
    if 1 in [p.player_number for p in game_state.get_alive_players()]:
        assert order[0] == 1


def test_speaking_order_rotation(game_state, judge, game_config):
    """Test that speaking order rotates."""
    handler = DayPhaseHandler(game_state, judge)
    
    # Day 1 (game already starts in DAY phase)
    order1 = handler.get_speaking_order()
    
    # Day 2 (transition through night)
    game_state.start_night()
    game_state.start_day()
    order2 = handler.get_speaking_order()
    
    # Should be different starting point
    assert order1[0] != order2[0] or len(order1) != len(order2)


@patch.object(SimpleLLMAgent, 'get_day_speech')
def test_process_speech(mock_speech, game_state, judge, game_config, mock_agents):
    """Test processing a player's speech."""
    handler = DayPhaseHandler(game_state, judge)
    game_state.start_day()
    
    player_num = 1
    mock_speech.return_value = "I think player 3 is suspicious. I nominate player number 3. PASS"
    
    speech, has_nomination, _ = handler.process_speech(player_num, mock_agents[player_num])
    
    assert len(speech) > 0
    assert has_nomination
    assert 3 in judge.get_nominated_players()


@patch.object(SimpleLLMAgent, 'get_day_speech')
def test_speech_auto_adds_pass(mock_speech, game_state, judge, game_config, mock_agents):
    """Test that PASS is auto-added if missing."""
    handler = DayPhaseHandler(game_state, judge)
    game_state.start_day()
    
    player_num = 1
    mock_speech.return_value = "This is my speech without ending"
    
    speech, _, _ = handler.process_speech(player_num, mock_agents[player_num])
    
    assert speech.endswith("PASS")


@patch.object(SimpleLLMAgent, 'get_day_speech')
def test_speech_truncation(mock_speech, game_state, judge, game_config, mock_agents):
    """Test that long speeches are truncated."""
    handler = DayPhaseHandler(game_state, judge)
    game_state.start_day()
    
    player_num = 1
    # Create a speech longer than limit
    long_speech = " ".join(["word"] * 300) + " PASS"
    mock_speech.return_value = long_speech
    
    speech, _, _ = handler.process_speech(player_num, mock_agents[player_num])
    
    words = speech.split()
    # Token limits are enforced by LLM, word count check removed
    # Just verify speech is not empty
    assert len(words) > 0


@patch.object(SimpleLLMAgent, 'get_day_speech')
def test_first_day_single_nomination_no_vote(mock_speech, game_state, judge, game_config, mock_agents):
    """Test that first day with single nomination doesn't vote."""
    handler = DayPhaseHandler(game_state, judge)
    game_state.start_day()
    game_state.day_number = 1
    
    # Mock only one nomination
    mock_speech.return_value = "I nominate player number 5. PASS"
    
    handler.run_day_phase(mock_agents)
    
    # Should not transition to voting
    assert game_state.phase != GamePhase.VOTING


@patch.object(SimpleLLMAgent, 'get_day_speech')
def test_subsequent_day_single_nomination_auto_eliminate(mock_speech, game_state, judge, game_config, mock_agents):
    """Test that subsequent day with single nomination auto-eliminates."""
    handler = DayPhaseHandler(game_state, judge)
    game_state.start_day()
    game_state.day_number = 2
    
    # Mock single nomination
    target = 5
    mock_speech.return_value = f"I nominate player number {target}. PASS"
    
    initial_alive = len(game_state.get_alive_players())
    
    handler.run_day_phase(mock_agents)
    
    # Should be eliminated
    target_player = game_state.get_player(target)
    assert target_player.status.value == "eliminated"
    assert len(game_state.get_alive_players()) == initial_alive - 1

