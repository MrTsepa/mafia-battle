"""
Tests for Judge/Moderator system.
"""

import pytest
from src.core import Judge, NominationResult, GameState, GamePhase
from src.config.game_config import GameConfig


def test_parse_nomination_valid(judge):
    """Test parsing valid nominations."""
    test_cases = [
        ("I nominate player number 5", 5),
        ("I nominate number 3", 3),
        ("I nominate player 2", 2),
    ]
    
    for speech, expected_target in test_cases:
        result = judge.parse_nomination(speech, 1)
        assert result.success, f"Failed to parse: {speech}"
        assert result.target == expected_target


def test_parse_nomination_invalid(judge):
    """Test parsing invalid nominations."""
    invalid_speeches = [
        "I think player 5 is suspicious",
        "Let's vote for number 3",
        "Player 7 seems guilty",
        "I nominate player number 99",  # Invalid number
        "Nominating number 7",  # Doesn't start with "I nominate"
        "nominate number 9",  # Doesn't start with "I nominate"
        "counter-nominating 2 reads like trying to redirect heat",  # Compound word, not a nomination
        "I think counter-nominating 2 reads like trying to redirect heat",  # Descriptive phrase
    ]
    
    for speech in invalid_speeches:
        result = judge.parse_nomination(speech, 1)
        assert not result.success or result.target is None, f"Should not parse as nomination: {speech}"


def test_process_nomination(judge, game_state):
    """Test processing a nomination."""
    game_state.start_day()
    speaker = game_state.get_alive_players()[0]
    
    result = judge.process_nomination(speaker.player_number, "I nominate player number 5")
    
    assert result.success
    assert result.target == 5
    assert 5 in judge.get_nominated_players()


def test_validate_speech_ending(judge):
    """Test speech ending validation."""
    valid_endings = [
        "This is my speech. PASS",
        "I think player 3 is mafia. THANK YOU",
        "Let me analyze. pass",
        "Thank you",
    ]
    
    invalid_endings = [
        "This is my speech",
        "I think player 3 is mafia",
        "No ending here",
    ]
    
    for speech in valid_endings:
        assert judge.validate_speech_ending(speech), f"Should be valid: {speech}"
    
    for speech in invalid_endings:
        assert not judge.validate_speech_ending(speech), f"Should be invalid: {speech}"


def test_validate_speech_length(judge):
    """Test speech length validation."""
    short_speech = " ".join(["word"] * 50)
    long_speech = " ".join(["word"] * 300)
    
    is_valid, _ = judge.validate_speech_length(short_speech)
    assert is_valid
    
    # Long speeches also pass - token limits are enforced by LLM, not word count
    is_valid, message = judge.validate_speech_length(long_speech)
    assert is_valid  # Always returns True now since we removed word limits
    assert message == ""  # No error message


def test_can_vote_first_day(judge, game_state):
    """Test voting rules for first day."""
    game_state.start_day()
    game_state.day_number = 1
    
    # First day needs more than one nomination
    assert not judge.can_vote()
    
    # Add two nominations
    judge.process_nomination(1, "I nominate player number 5")
    judge.process_nomination(2, "I nominate player number 7")
    
    assert judge.can_vote()


def test_can_vote_subsequent_days(judge, game_state):
    """Test voting rules for subsequent days."""
    game_state.start_day()
    game_state.day_number = 2
    
    # Subsequent days can vote with one nomination
    judge.process_nomination(1, "I nominate player number 5")
    assert judge.can_vote()


def test_vote_counts(judge, game_state):
    """Test vote counting."""
    game_state.start_day()
    game_state.day_number = 1
    
    # Add nominations
    judge.process_nomination(1, "I nominate player number 5")
    judge.process_nomination(2, "I nominate player number 7")
    
    game_state.start_voting()
    
    # Add explicit votes
    judge.process_vote(3, 5)
    judge.process_vote(4, 5)
    judge.process_vote(5, 7)
    
    # Make all other players vote explicitly to avoid default votes
    alive_players = game_state.get_alive_players()
    for player in alive_players:
        if player.player_number not in [3, 4, 5]:
            # Other players vote for 5 so we can verify explicit vote counting
            judge.process_vote(player.player_number, 5)
    
    counts = judge.get_vote_counts()
    # With 10 players: players 3,4,1,2,6,7,8,9,10 vote for 5 (9 votes)
    # Player 5 votes for 7 (1 vote)
    assert counts[5] == 9  # Votes from all players except 5
    assert counts[7] == 1  # Only vote from 5


def test_default_votes(judge, game_state):
    """Test default vote assignment."""
    game_state.start_day()
    game_state.day_number = 2
    
    # Add one nomination
    judge.process_nomination(1, "I nominate player number 5")
    game_state.start_voting()
    
    # Only one player votes
    judge.process_vote(2, 5)
    
    # Other players should default to last nominated (5)
    counts = judge.get_vote_counts()
    alive_count = len(game_state.get_alive_players())
    # Should have at least the explicit vote + defaults
    assert counts[5] >= 2


def test_get_elimination_target(judge, game_state):
    """Test getting elimination target."""
    game_state.start_day()
    game_state.day_number = 2
    
    judge.process_nomination(1, "I nominate player number 5")
    game_state.start_voting()
    
    # All vote for 5
    for player in game_state.get_alive_players():
        if player.player_number != 5:
            judge.process_vote(player.player_number, 5)
    
    target = judge.get_elimination_target()
    assert target == 5


def test_tie_detection(judge, game_state):
    """Test tie detection."""
    game_state.start_day()
    game_state.day_number = 2
    
    judge.process_nomination(1, "I nominate player number 5")
    judge.process_nomination(2, "I nominate player number 7")
    game_state.start_voting()
    
    # Create a tie
    alive = game_state.get_alive_players()
    mid = len(alive) // 2
    for i, player in enumerate(alive):
        if i < mid:
            judge.process_vote(player.player_number, 5)
        else:
            judge.process_vote(player.player_number, 7)
    
    assert judge.check_tie()
    tied = judge.get_tied_players()
    assert 5 in tied
    assert 7 in tied

