"""
Tests for voting system.
"""

import pytest
from unittest.mock import Mock, patch
from src.core import GameState, GamePhase, Judge
from src.phases import VotingHandler
from src.agents import SimpleLLMAgent
from src.config.game_config import GameConfig


@patch.object(SimpleLLMAgent, 'get_vote_choice_async')
def test_collect_votes(mock_vote_async, game_state, judge, game_config, mock_agents):
    """Test vote collection."""
    handler = VotingHandler(game_state, judge)
    game_state.start_day()
    game_state.day_number = 2
    
    # Add nominations
    judge.process_nomination(1, "I nominate player number 5")
    judge.process_nomination(2, "I nominate player number 7")
    game_state.start_voting()
    
    # Mock votes
    async def vote_async(context):
        return 5
    mock_vote_async.side_effect = vote_async
    
    handler.collect_votes(mock_agents)
    
    # Check votes were recorded
    votes = game_state.votes.get(game_state.day_number, {})
    assert len(votes) > 0


@patch.object(SimpleLLMAgent, 'get_vote_choice_async')
def test_process_voting_elimination(mock_vote_async, game_state, judge, game_config, mock_agents):
    """Test voting results in elimination."""
    handler = VotingHandler(game_state, judge)
    game_state.start_day()
    game_state.day_number = 2
    
    target = 5
    judge.process_nomination(1, f"I nominate player number {target}")
    game_state.start_voting()
    
    # All vote for target
    async def vote_async(context):
        return target
    mock_vote_async.side_effect = vote_async
    
    initial_alive = len(game_state.get_alive_players())
    handler.run_voting_phase(mock_agents)
    
    # Should be eliminated
    target_player = game_state.get_player(target)
    assert target_player.status.value == "eliminated"
    assert len(game_state.get_alive_players()) == initial_alive - 1


@patch.object(SimpleLLMAgent, 'get_vote_choice_async')
@patch.object(SimpleLLMAgent, 'get_day_speech')
def test_tie_breaking(mock_speech, mock_vote_async, game_state, judge, game_config, mock_agents):
    """Test tie-breaking procedure."""
    handler = VotingHandler(game_state, judge)
    game_state.start_day()
    game_state.day_number = 2
    
    judge.process_nomination(1, "I nominate player number 5")
    judge.process_nomination(2, "I nominate player number 7")
    game_state.start_voting()
    
    # Create a tie
    alive = game_state.get_alive_players()
    mid = len(alive) // 2
    
    async def vote_side_effect(context):
        voter_num = context.player.player_number
        voter_index = [p.player_number for p in game_state.get_alive_players()].index(voter_num)
        return 5 if voter_index < mid else 7
    
    mock_vote_async.side_effect = vote_side_effect
    mock_speech.return_value = "Tie-break speech. PASS"
    
    # First vote creates tie
    handler.collect_votes(mock_agents)
    
    # Should detect tie
    assert judge.check_tie()
    
    # Run tie-breaking
    tied = judge.get_tied_players()
    result = handler.handle_tie(tied, mock_agents)
    
    # Should have some result (either elimination or keep all)
    assert result is not None or len(tied) == 0


@patch.object(SimpleLLMAgent, 'get_vote_choice_async')
@patch.object(SimpleLLMAgent, 'get_day_speech')
def test_eliminate_all_on_persistent_tie(mock_speech, mock_vote_async, game_state, judge, game_config, mock_agents):
    """Test eliminating all tied players after persistent tie."""
    handler = VotingHandler(game_state, judge)
    game_state.start_day()
    game_state.day_number = 2
    
    judge.process_nomination(1, "I nominate player number 5")
    judge.process_nomination(2, "I nominate player number 7")
    game_state.start_voting()
    
    alive_numbers = [p.player_number for p in game_state.get_alive_players()]
    alive_count = len(alive_numbers)
    mid = alive_count // 2
    call_index = 0
    
    async def vote_side_effect(context):
        nonlocal call_index
        round_index = call_index // alive_count
        call_index += 1
        voter_num = context.player.player_number
        voter_index = alive_numbers.index(voter_num)
        if round_index < 2:
            return 5 if voter_index < mid else 7
        return 5
    
    mock_vote_async.side_effect = vote_side_effect
    mock_speech.return_value = "Tie-break speech. PASS"
    
    handler.run_voting_phase(mock_agents)
    
    assert game_state.get_player(5).status.value == "eliminated"
    assert game_state.get_player(7).status.value == "eliminated"


@patch.object(SimpleLLMAgent, 'get_vote_choice_async')
def test_non_voters_included_in_elimination_voters(mock_vote_async, game_state, judge, game_config, mock_agents):
    """Test non-voters are included in elimination voter list."""
    handler = VotingHandler(game_state, judge)
    game_state.start_day()
    game_state.day_number = 2
    
    judge.process_nomination(1, "I nominate player number 5")
    judge.process_nomination(2, "I nominate player number 7")
    game_state.start_voting()
    
    async def vote_async(context):
        return 7
    mock_vote_async.side_effect = vote_async
    
    limited_agents = {k: v for k, v in mock_agents.items() if k not in {8, 9}}
    handler.run_voting_phase(limited_agents)
    
    elimination_actions = [
        action for action in game_state.action_log
        if action["type"] == "player_eliminated" and action["data"].get("day_number") == game_state.day_number
    ]
    assert elimination_actions
    voters = elimination_actions[-1]["data"]["voters"]
    assert 8 in voters
    assert 9 in voters


@patch.object(SimpleLLMAgent, 'get_vote_choice_async')
@patch.object(SimpleLLMAgent, 'get_day_speech')
def test_tie_break_revote_single_elimination(mock_speech, mock_vote_async, game_state, judge, game_config, mock_agents):
    """Test tie-break revote resolves to a single eliminated player."""
    handler = VotingHandler(game_state, judge)
    game_state.start_day()
    game_state.day_number = 2
    
    judge.process_nomination(1, "I nominate player number 5")
    judge.process_nomination(2, "I nominate player number 7")
    game_state.start_voting()
    
    alive_numbers = [p.player_number for p in game_state.get_alive_players()]
    alive_count = len(alive_numbers)
    mid = alive_count // 2
    call_index = 0
    
    async def vote_side_effect(context):
        nonlocal call_index
        round_index = call_index // alive_count
        call_index += 1
        voter_num = context.player.player_number
        voter_index = alive_numbers.index(voter_num)
        if round_index == 0:
            return 5 if voter_index < mid else 7
        return 5
    
    mock_vote_async.side_effect = vote_side_effect
    mock_speech.return_value = "Tie-break speech. PASS"
    
    handler.collect_votes(mock_agents)
    tied = judge.get_tied_players()
    result = handler.handle_tie(tied, mock_agents)
    
    assert result == [5]
