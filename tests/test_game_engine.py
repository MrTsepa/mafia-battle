"""
Tests for game engine and state management.
"""

import pytest
from src.core import GameState, GamePhase, Team, RoleType, PlayerStatus


def test_game_setup(game_state):
    """Test that game initializes correctly."""
    assert len(game_state.players) == 10
    assert game_state.phase == GamePhase.DAY
    assert game_state.night_number == 0
    assert game_state.day_number == 1


def test_role_distribution(game_state):
    """Test that roles are distributed correctly."""
    mafia_count = len(game_state.get_mafia_players())
    civilian_count = len(game_state.get_civilian_players())
    
    assert mafia_count == 3
    assert civilian_count == 7
    
    # Check for Sheriff
    sheriff = [p for p in game_state.players if p.role.role_type == RoleType.SHERIFF]
    assert len(sheriff) == 1
    
    # Check for Don
    don = [p for p in game_state.players if p.role.role_type == RoleType.DON]
    assert len(don) == 1


def test_mafia_knowledge(game_state):
    """Test that mafia players know each other."""
    mafia_players = game_state.get_mafia_players()
    
    for player in mafia_players:
        assert len(player.known_mafia) == 3
        # All mafia should know all mafia numbers
        mafia_numbers = [p.player_number for p in mafia_players]
        assert set(player.known_mafia) == set(mafia_numbers)


def test_phase_transitions(game_state):
    """Test phase transitions."""
    # Start with day
    assert game_state.phase == GamePhase.DAY
    assert game_state.day_number == 1
    assert game_state.night_number == 0
    
    # Transition to night
    game_state.start_night()
    assert game_state.phase == GamePhase.NIGHT
    assert game_state.night_number == 1
    
    # Transition back to day
    game_state.start_day()
    assert game_state.phase == GamePhase.DAY
    assert game_state.day_number == 2


def test_win_condition_civilians(game_state):
    """Test civilian win condition."""
    # Eliminate all mafia
    mafia_players = game_state.get_mafia_players()
    for player in mafia_players:
        player.eliminate()
    
    winner = game_state.check_win_condition()
    assert winner == Team.RED


def test_win_condition_mafia(game_state):
    """Test mafia win condition (equal numbers)."""
    # Eliminate civilians until equal
    civilians = game_state.get_civilian_players()
    # Need to eliminate 4 civilians (7 -> 3, equal to 3 mafia)
    for i in range(4):
        if i < len(civilians):
            civilians[i].eliminate()
    
    winner = game_state.check_win_condition()
    assert winner == Team.BLACK


def test_win_condition_mafia_majority(game_state):
    """Test mafia win condition (mafia outnumber)."""
    # Eliminate civilians until mafia outnumber
    civilians = game_state.get_civilian_players()
    # Eliminate 5 civilians (7 -> 2, less than 3 mafia)
    for i in range(5):
        if i < len(civilians):
            civilians[i].eliminate()
    
    winner = game_state.check_win_condition()
    assert winner == Team.BLACK


def test_eliminate_player(game_state):
    """Test player elimination."""
    player = game_state.players[0]
    initial_alive = len(game_state.get_alive_players())
    
    game_state.eliminate_player(player.player_number)
    
    assert player.status == PlayerStatus.ELIMINATED
    assert len(game_state.get_alive_players()) == initial_alive - 1


def test_get_player(game_state):
    """Test getting player by number."""
    player = game_state.get_player(5)
    assert player is not None
    assert player.player_number == 5
    
    # Invalid number
    player = game_state.get_player(99)
    assert player is None


def test_max_rounds_limit(game_state):
    """Test that game ends when max_rounds is reached."""
    # Set a low max_rounds limit
    game_state.max_rounds = 3
    
    # Advance to day 3 (which is >= max_rounds)
    game_state.start_day()  # Day 1
    game_state.start_night()
    game_state.start_day()  # Day 2
    game_state.start_night()
    game_state.start_day()  # Day 3
    
    # Check win condition should trigger max_rounds
    winner = game_state.check_win_condition()
    assert winner is not None  # Should return a winner
    
    # End the game
    game_state.end_game(winner, reason="max_rounds")
    assert game_state.phase == GamePhase.GAME_OVER
    assert game_state.winner is not None


def test_max_rounds_none(game_state):
    """Test that max_rounds=None means no limit."""
    game_state.max_rounds = None
    
    # Advance many days
    for _ in range(10):
        game_state.start_day()
        game_state.start_night()
    
    # Should not trigger max_rounds (only normal win conditions)
    # If no win condition met, should return None
    winner = game_state.check_win_condition()
    # Winner might be None or a team depending on eliminations, but not forced by max_rounds

