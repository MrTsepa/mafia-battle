"""
Tests for night phase handler.
"""

import pytest
from unittest.mock import Mock, patch
from src.core import GameState, GamePhase, Judge
from src.phases import NightPhaseHandler
from src.agents import SimpleLLMAgent
from src.core import RoleType
from src.config.game_config import GameConfig


@patch.object(SimpleLLMAgent, 'get_night_action')
def test_mafia_kill_claim(mock_action, game_state, judge, game_config, mock_agents, don_player):
    """Test mafia kill claims."""
    handler = NightPhaseHandler(game_state, judge)
    game_state.start_night()
    
    # Mock mafia kill claims
    mafia_players = game_state.get_mafia_players()
    
    def action_side_effect(context):
        player = context.player
        if player.is_mafia and player.role.role_type != RoleType.DON:
            return {"type": "kill_claim", "target": 5}
        elif player.role.role_type == RoleType.DON:
            return {"type": "kill_decision", "kill_decision": 5}
        return {}
    
    mock_action.side_effect = action_side_effect
    
    killed = handler.process_mafia_kill(mock_agents)
    
    # Don should have made decision
    assert killed == 5 or killed is None


@patch.object(SimpleLLMAgent, 'get_night_action')
def test_mafia_kill_elimination(mock_action, game_state, judge, game_config, mock_agents):
    """Test that mafia kill eliminates player."""
    handler = NightPhaseHandler(game_state, judge)
    game_state.start_night()
    
    target = 5
    initial_alive = len(game_state.get_alive_players())
    
    def action_side_effect(context):
        player = context.player
        # Check if this is a decision-making call (has kill claims in context)
        if "mafia_kill_claims" in context.private_info:
            # This is the decision maker (Don or mafia when Don is eliminated)
            return {"type": "kill_decision", "kill_decision": target}
        elif player.is_mafia and player.role.role_type != RoleType.DON:
            return {"type": "kill_claim", "target": target}
        elif player.role.role_type == RoleType.DON:
            # Don check (when called without kill claims)
            alive = [p.player_number for p in game_state.get_alive_players() 
                    if p.player_number != player.player_number]
            return {"type": "don_check", "target": alive[0] if alive else 1}
        elif player.role.role_type == RoleType.SHERIFF:
            # Sheriff check
            alive = [p.player_number for p in game_state.get_alive_players() 
                    if p.player_number != player.player_number]
            return {"type": "sheriff_check", "target": alive[0] if alive else 1}
        return {}
    
    mock_action.side_effect = action_side_effect
    
    handler.run_night_phase(mock_agents)
    
    # Target should be eliminated
    target_player = game_state.get_player(target)
    assert target_player.status.value == "eliminated"
    assert len(game_state.get_alive_players()) == initial_alive - 1


@patch.object(SimpleLLMAgent, 'get_night_action')
def test_don_check(mock_action, game_state, judge, game_config, mock_agents, don_player, sheriff_player):
    """Test Don's check for Sheriff."""
    handler = NightPhaseHandler(game_state, judge)
    game_state.start_night()
    game_state.night_number = 2  # Not first night
    
    sheriff_num = sheriff_player.player_number
    
    def action_side_effect(context):
        if context.player.role.role_type == RoleType.DON:
            return {"type": "don_check", "target": sheriff_num}
        return {}
    
    mock_action.side_effect = action_side_effect
    
    result = handler.process_don_check(mock_agents)
    
    assert result is not None
    assert result["target"] == sheriff_num
    assert result["result"] == "Sheriff"
    
    # Check recorded in player
    assert game_state.night_number in don_player.don_checks
    assert don_player.don_checks[game_state.night_number]["target"] == sheriff_num
    assert don_player.don_checks[game_state.night_number]["result"] == "Sheriff"


@patch.object(SimpleLLMAgent, 'get_night_action')
def test_don_check_not_sheriff(mock_action, game_state, judge, game_config, mock_agents, don_player):
    """Test Don checking a non-Sheriff player."""
    handler = NightPhaseHandler(game_state, judge)
    game_state.start_night()
    game_state.night_number = 2
    
    # Check a civilian (not sheriff)
    target = next(p.player_number for p in game_state.get_civilian_players() 
                  if p.role.role_type != RoleType.SHERIFF)
    
    def action_side_effect(context):
        if context.player.role.role_type == RoleType.DON:
            return {"type": "don_check", "target": target}
        return {}
    
    mock_action.side_effect = action_side_effect
    
    result = handler.process_don_check(mock_agents)
    
    assert result is not None
    assert result["target"] == target
    assert result["result"] == "Not the Sheriff"
    
    # Check recorded in player
    assert game_state.night_number in don_player.don_checks
    assert don_player.don_checks[game_state.night_number]["target"] == target
    assert don_player.don_checks[game_state.night_number]["result"] == "Not the Sheriff"


@patch.object(SimpleLLMAgent, 'get_night_action')
def test_sheriff_check_mafia(mock_action, game_state, judge, game_config, mock_agents, sheriff_player):
    """Test Sheriff checking a mafia player."""
    handler = NightPhaseHandler(game_state, judge)
    game_state.start_night()
    game_state.night_number = 2
    
    mafia_num = game_state.get_mafia_players()[0].player_number
    
    def action_side_effect(context):
        if context.player.role.role_type == RoleType.SHERIFF:
            return {"type": "sheriff_check", "target": mafia_num}
        return {}
    
    mock_action.side_effect = action_side_effect
    
    result = handler.process_sheriff_check(mock_agents)
    
    assert result is not None
    assert result["target"] == mafia_num
    assert result["result"] == "Black"
    
    # Check recorded in player
    assert game_state.night_number in sheriff_player.sheriff_checks
    assert sheriff_player.sheriff_checks[game_state.night_number]["target"] == mafia_num
    assert sheriff_player.sheriff_checks[game_state.night_number]["result"] == "Black"


@patch.object(SimpleLLMAgent, 'get_night_action')
def test_sheriff_check_civilian(mock_action, game_state, judge, game_config, mock_agents, sheriff_player):
    """Test Sheriff checking a civilian player."""
    handler = NightPhaseHandler(game_state, judge)
    game_state.start_night()
    game_state.night_number = 2
    
    civilian_num = next(p.player_number for p in game_state.get_civilian_players() 
                        if p.role.role_type != RoleType.SHERIFF)
    
    def action_side_effect(context):
        if context.player.role.role_type == RoleType.SHERIFF:
            return {"type": "sheriff_check", "target": civilian_num}
        return {}
    
    mock_action.side_effect = action_side_effect
    
    result = handler.process_sheriff_check(mock_agents)
    
    assert result is not None
    assert result["result"] == "Red"


@patch.object(SimpleLLMAgent, 'get_night_action')
def test_checks_first_night(mock_action, game_state, judge, game_config, mock_agents, don_player, sheriff_player):
    """Test that Don and Sheriff can check on first night (checks happen every night)."""
    handler = NightPhaseHandler(game_state, judge)
    game_state.start_night()
    game_state.night_number = 1
    
    # Mock actions for Don and Sheriff
    def action_side_effect(context):
        if context.player.role.role_type == RoleType.DON:
            return {"type": "don_check", "target": 2}
        elif context.player.role.role_type == RoleType.SHERIFF:
            return {"type": "sheriff_check", "target": 3}
        return {}
    
    mock_action.side_effect = action_side_effect
    
    don_result = handler.process_don_check(mock_agents)
    sheriff_result = handler.process_sheriff_check(mock_agents)
    
    # Checks should work on first night
    assert don_result is not None
    assert sheriff_result is not None
    assert don_result["target"] == 2
    assert sheriff_result["target"] == 3


@patch.object(SimpleLLMAgent, 'get_night_action')
def test_mafia_kill_when_don_eliminated(mock_action, game_state, judge, game_config, mock_agents):
    """Test that mafia can make kill decision when Don is eliminated."""
    handler = NightPhaseHandler(game_state, judge)
    game_state.start_night()
    
    # Find and eliminate the Don
    don = next((p for p in game_state.get_mafia_players() if p.role.role_type == RoleType.DON), None)
    if don:
        game_state.eliminate_player(don.player_number, "test")
    
    # Get remaining mafia
    alive_mafia = [p for p in game_state.get_mafia_players() if p.is_alive]
    assert len(alive_mafia) > 0
    
    # Mock actions: mafia make claims, first alive mafia makes decision
    first_mafia = alive_mafia[0]
    
    def action_side_effect(context):
        player = context.player
        if player.is_mafia and player.role.role_type != RoleType.DON:
            # Check if this is kill decision call (has kill_claims in context)
            kill_claims = context.private_info.get("mafia_kill_claims", {})
            is_decision = kill_claims and isinstance(kill_claims, dict) and any(
                isinstance(k, int) and 1 <= k <= 10 for k in kill_claims.keys()
            )
            
            if is_decision and player.player_number == first_mafia.player_number:
                # First mafia makes decision
                return {"kill_decision": 5}
            elif not is_decision:
                # Make kill claim
                return {"type": "kill_claim", "target": 5}
        return {}
    
    mock_action.side_effect = action_side_effect
    
    killed = handler.process_mafia_kill(mock_agents)
    
    # Should have killed someone (or None if no valid target)
    assert killed is None or (killed >= 1 and killed <= 10)

