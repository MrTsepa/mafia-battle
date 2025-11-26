"""
Judge/Moderator system for rule enforcement and game management.
"""

import re
from typing import List, Optional, Dict, Tuple, TYPE_CHECKING
from dataclasses import dataclass

from .game_engine import GameState, GamePhase
from .player import Player
from ..config.game_config import GameConfig, default_config

if TYPE_CHECKING:
    from ..web.event_emitter import EventEmitter


@dataclass
class NominationResult:
    """Result of a nomination attempt."""
    success: bool
    target: Optional[int] = None
    message: str = ""
    first_nominator: Optional[int] = None  # Who nominated this target first (if already nominated)


class Judge:
    """Judge/Moderator that enforces rules and manages game flow."""
    
    def __init__(self, game_state: GameState, config: GameConfig = default_config, event_emitter: Optional['EventEmitter'] = None):
        self.game_state = game_state
        self.config = config
        self.event_emitter = event_emitter
        self.announcements = []
        # Track who nominated each player: {day_number: {target: nominator}}
        self.nomination_sources: Dict[int, Dict[int, int]] = {}
    
    def announce(self, message: str) -> None:
        """Make a judge announcement."""
        if self.config.use_judge_announcements:
            self.announcements.append(message)
            print(f"[JUDGE] {message}")
            # Emit announcement event
            if self.event_emitter:
                self.event_emitter.emit_announcement(
                    message,
                    self.game_state.phase.value,
                    self.game_state.day_number,
                    self.game_state.night_number
                )
    
    def player_speaks(self, player_number: int, speech: str) -> None:
        """Announce a player's speech."""
        if self.config.use_judge_announcements:
            self.announcements.append(f"Player {player_number}: {speech}")
            print(f"[Player {player_number}] {speech}")
    
    def start_night(self) -> None:
        """Announce night phase start."""
        self.game_state.start_night()
        self.announce("Night falls.")
    
    def start_day(self) -> None:
        """Announce day phase start."""
        self.game_state.start_day()
        alive_players = [p.player_number for p in self.game_state.get_alive_players()]
        self.announce(f"Morning has come (in the city). Players alive: {alive_players}")
    
    def start_voting(self) -> None:
        """Announce voting phase start."""
        self.game_state.start_voting()
        self.announce("It is voting time.")
    
    def parse_nomination(self, speech: str, speaker_number: int) -> NominationResult:
        """
        Parse a nomination from speech text.
        Looks for patterns like "I nominate player number X" or "Nominating number X"
        """
        # Normalize speech
        speech_lower = speech.lower().strip()
        
        # Patterns to match
        patterns = [
            r"i nominate (?:player )?number (\d+)",
            r"i nominate (?:player )?(\d+)",
            r"nominating (?:player )?number (\d+)",
            r"nominating (?:player )?(\d+)",
            r"nominate (?:player )?number (\d+)",
            r"nominate (?:player )?(\d+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, speech_lower)
            if match:
                target_number = int(match.group(1))
                
                # Validate target
                if target_number < 1 or target_number > 10:
                    return NominationResult(
                        success=False,
                        message=f"Invalid player number: {target_number}"
                    )
                
                # Prevent self-nomination
                if target_number == speaker_number:
                    return NominationResult(
                        success=False,
                        message="You cannot nominate yourself"
                    )
                
                # Check if target is alive
                target_player = self.game_state.get_player(target_number)
                if not target_player or not target_player.is_alive:
                    return NominationResult(
                        success=False,
                        message=f"Player {target_number} is not available for nomination"
                    )
                
                # Check if speaker already nominated today
                speaker = self.game_state.get_player(speaker_number)
                if not speaker:
                    return NominationResult(success=False, message="Speaker not found")
                
                # Check if this is first nomination of the day
                day_nominations = self.game_state.nominations.get(self.game_state.day_number, [])
                if target_number in day_nominations:
                    # Find who nominated this player first
                    day = self.game_state.day_number
                    first_nominator = self.nomination_sources.get(day, {}).get(target_number, None)
                    return NominationResult(
                        success=False,
                        target=target_number,
                        message="Already nominated",
                        first_nominator=first_nominator
                    )
                
                # Check if speaker already nominated someone today
                if speaker_number in [p.player_number for p in self.game_state.get_alive_players() 
                                     if target_number in speaker.nominations_made]:
                    # Actually, we need to check if speaker made a nomination this day
                    # For now, allow it if target is new
                    pass
                
                return NominationResult(
                    success=True,
                    target=target_number,
                    message="Accepted"
                )
        
        return NominationResult(success=False, message="No valid nomination found")
    
    def process_nomination(self, speaker_number: int, speech: str, announce: bool = True) -> NominationResult:
        """
        Process a nomination from a player's speech.
        Returns NominationResult with success status.
        
        Args:
            speaker_number: Player making the nomination
            speech: Speech text containing the nomination
            announce: Whether to announce the result immediately (default: True)
        """
        if self.game_state.phase != GamePhase.DAY:
            return NominationResult(success=False, message="Not in day phase")
        
        result = self.parse_nomination(speech, speaker_number)
        
        if result.success and result.target:
            # Add to game state
            day = self.game_state.day_number
            if day not in self.game_state.nominations:
                self.game_state.nominations[day] = []
            
            if result.target not in self.game_state.nominations[day]:
                self.game_state.nominations[day].append(result.target)
                
                # Track who nominated this player
                if day not in self.nomination_sources:
                    self.nomination_sources[day] = {}
                self.nomination_sources[day][result.target] = speaker_number
                
                # Record in player history
                speaker = self.game_state.get_player(speaker_number)
                if speaker:
                    speaker.nominate(result.target, day)
                
                if announce:
                    self.announce(f"Accepted. Player {result.target} has been nominated by Player {speaker_number}.")
        elif not result.success and result.target and result.first_nominator:
            # Already nominated - prepare rejection message
            if announce:
                self.announce(f"Rejected. Player {result.target} is already nominated by Player {result.first_nominator}.")
        
        return result
    
    def validate_speech_ending(self, speech: str) -> bool:
        """Check if speech ends with PASS or THANK YOU."""
        speech_upper = speech.strip().upper()
        return speech_upper.endswith("PASS") or speech_upper.endswith("THANK YOU")
    
    def validate_speech_length(self, speech: str, is_tie_break: bool = False) -> Tuple[bool, str]:
        """
        Validate speech length against token limits.
        Returns (is_valid, message)
        
        Note: Actual token counting would require tiktoken or similar.
        This is a simplified validation that always passes.
        The LLM is responsible for respecting token limits.
        """
        # Token count would require actual tokenization, simplified for now
        # In production, use tiktoken or similar
        # The LLM call already respects max_speech_tokens, so this is just a pass-through
        
        return True, ""
    
    def get_nominated_players(self, day_number: Optional[int] = None) -> List[int]:
        """Get list of nominated players for a day."""
        if day_number is None:
            day_number = self.game_state.day_number
        
        return self.game_state.nominations.get(day_number, [])
    
    def can_vote(self) -> bool:
        """Check if voting can proceed."""
        day = self.game_state.day_number
        nominations = self.get_nominated_players(day)
        
        # First day: need more than one nomination
        if day == 1:
            return len(nominations) > 1
        
        # Subsequent days: any number of nominations
        # If only one, automatic elimination
        return len(nominations) >= 1
    
    def process_vote(self, voter_number: int, target_number: int) -> bool:
        """
        Process a vote from a player.
        Returns True if vote is valid.
        """
        if self.game_state.phase != GamePhase.VOTING:
            return False
        
        voter = self.game_state.get_player(voter_number)
        if not voter or not voter.is_alive:
            return False
        
        # Check if target is nominated
        nominations = self.get_nominated_players()
        if target_number not in nominations:
            return False
        
        # Record vote
        day = self.game_state.day_number
        if day not in self.game_state.votes:
            self.game_state.votes[day] = {}
        
        self.game_state.votes[day][voter_number] = target_number
        voter.vote(target_number, day)
        
        return True
    
    def get_vote_counts(self, day_number: Optional[int] = None) -> Dict[int, int]:
        """Get vote counts for nominated players."""
        if day_number is None:
            day_number = self.game_state.day_number
        
        nominations = self.get_nominated_players(day_number)
        votes = self.game_state.votes.get(day_number, {})
        
        counts = {nom: 0 for nom in nominations}
        
        # Count votes
        for voter, target in votes.items():
            if target in counts:
                counts[target] += 1
        
        # Handle default votes (non-voters vote for last nominated)
        alive_players = [p.player_number for p in self.game_state.get_alive_players()]
        voters = set(votes.keys())
        non_voters = [p for p in alive_players if p not in voters]
        
        if nominations and non_voters:
            last_nominated = nominations[-1]
            for non_voter in non_voters:
                counts[last_nominated] += 1
        
        return counts
    
    def get_elimination_target(self) -> Optional[int]:
        """
        Determine who should be eliminated based on votes.
        Returns player number or None if tie needs resolution.
        """
        counts = self.get_vote_counts()
        if not counts:
            return None
        
        max_votes = max(counts.values())
        candidates = [player for player, votes in counts.items() if votes == max_votes]
        
        if len(candidates) == 1:
            return candidates[0]
        
        # Tie - needs tie-breaking
        return None
    
    def check_tie(self) -> bool:
        """Check if there's a tie in voting."""
        counts = self.get_vote_counts()
        if not counts:
            return False  # No votes, can't be a tie
        max_votes = max(counts.values())
        candidates = [player for player, votes in counts.items() if votes == max_votes]
        return len(candidates) > 1 and bool(self.get_nominated_players())
    
    def get_tied_players(self) -> List[int]:
        """Get list of tied players."""
        counts = self.get_vote_counts()
        if not counts:
            return []
        
        max_votes = max(counts.values())
        return [player for player, votes in counts.items() if votes == max_votes]

