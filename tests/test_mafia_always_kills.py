"""
Test that mafia always kills at night.
Runs extensive simulations to verify the fix for the bug where mafia sometimes didn't kill.
"""

import pytest
from src.core import GameState, GamePhase, Judge, RoleType
from src.agents import DummyAgent
from src.phases import NightPhaseHandler
from src.config.game_config import default_config


def test_mafia_always_kills_extensive():
    """
    Test that mafia always kills at night across 1000 simulations.
    This test verifies the fix for the bug where mafia sometimes didn't kill
    when kill_claims was empty.
    """
    no_kill_nights = []
    num_simulations = 1000
    
    for sim in range(num_simulations):
        # Create game state with unique seed for each simulation
        config = default_config
        config.random_seed = sim
        game_state = GameState(random_seed=sim)
        judge = Judge(game_state, config)
        
        # Initialize agents
        agents = {}
        for player in game_state.players:
            agent = DummyAgent(player, config)
            agents[player.player_number] = agent
        
        # Run several nights per simulation
        for night in range(1, 6):  # Test up to 5 nights
            game_state.start_night()
            
            handler = NightPhaseHandler(game_state, judge)
            killed = handler.process_mafia_kill(agents)
            
            if not killed:
                no_kill_nights.append({
                    "simulation": sim + 1,
                    "night": night,
                    "alive_players": [p.player_number for p in game_state.get_alive_players()],
                    "mafia_players": [p.player_number for p in game_state.get_mafia_players()],
                })
            
            # Eliminate killed player if any
            if killed:
                game_state.eliminate_player(killed, "night kill", night_number=night)
            
            # Check win condition
            if game_state.check_win_condition():
                break
    
    # Assert that there were no nights without kills
    assert len(no_kill_nights) == 0, (
        f"Found {len(no_kill_nights)} nights where mafia didn't kill. "
        f"First few incidents: {no_kill_nights[:10]}"
    )


def test_mafia_kills_with_empty_claims():
    """
    Test that mafia kills even when kill_claims is empty (Don is only mafia or no valid claims).
    This is the specific edge case that was fixed.
    """
    config = default_config
    config.random_seed = 999
    game_state = GameState(random_seed=999)
    judge = Judge(game_state, config)
    
    agents = {}
    for player in game_state.players:
        agent = DummyAgent(player, config)
        agents[player.player_number] = agent
    
    # Eliminate all mafia except Don
    mafia_players = game_state.get_mafia_players()
    don = next((p for p in mafia_players if p.role.role_type == RoleType.DON), None)
    if don:
        for mafia in mafia_players:
            if mafia.player_number != don.player_number:
                game_state.eliminate_player(mafia.player_number, "test")
    
    game_state.start_night()
    
    handler = NightPhaseHandler(game_state, judge)
    killed = handler.process_mafia_kill(agents)
    
    # Don should still make a kill decision even when alone
    assert killed is not None, "Don should kill even when no other mafia members are alive"
    assert killed >= 1 and killed <= 10, f"Killed player number should be valid, got {killed}"


def test_mafia_kills_with_empty_kill_claims_dict():
    """
    Test that Don makes kill decision when kill_claims dict is empty.
    This tests the specific bug fix where empty dict wasn't recognized as kill decision call.
    """
    config = default_config
    config.random_seed = 1000
    game_state = GameState(random_seed=1000)
    judge = Judge(game_state, config)
    
    agents = {}
    for player in game_state.players:
        agent = DummyAgent(player, config)
        agents[player.player_number] = agent
    
    game_state.start_night()
    handler = NightPhaseHandler(game_state, judge)
    
    # Get Don
    mafia_players = game_state.get_mafia_players()
    don = next((p for p in mafia_players if p.role.role_type == RoleType.DON), None)
    
    if don:
        # Build context for Don with empty kill_claims (simulating the bug scenario)
        don_agent = agents[don.player_number]
        context = don_agent.build_context(game_state)
        context.private_info["mafia_kill_claims"] = {}  # Empty dict
        context.private_info["_kill_decision_context"] = True  # Mark as kill decision call
        
        action = don_agent.get_night_action(context)
        
        # Don should make kill decision even with empty claims
        assert "kill_decision" in action or action.get("type") == "kill_decision", (
            f"Don should make kill decision with empty claims, got action: {action}"
        )

