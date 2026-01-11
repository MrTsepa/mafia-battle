"""
Day phase handler for discussion and nominations.
"""

from typing import List, Optional, Dict, TYPE_CHECKING
from ..core import GameState, GamePhase, Player, Judge
from ..core.judge import NominationResult
from ..agents import BaseAgent, SimpleLLMAgent

if TYPE_CHECKING:
    from ..web.event_emitter import EventEmitter


class DayPhaseHandler:
    """Handles day phase operations: speeches and nominations."""
    
    def __init__(self, game_state: GameState, judge: Judge, event_emitter: Optional['EventEmitter'] = None):
        self.game_state = game_state
        self.judge = judge
        self.event_emitter = event_emitter
    
    def get_speaking_order(self) -> List[int]:
        """
        Get the speaking order for the current day.
        First day: starts with player 1
        Subsequent days: starts with next player after previous day's starter
        """
        alive_players = [p.player_number for p in self.game_state.get_alive_players()]
        
        if not alive_players:
            return []
        
        if self.game_state.day_number == 1:
            # First day: start with player 1 (if alive), otherwise first alive
            if 1 in alive_players:
                start_index = alive_players.index(1)
            else:
                start_index = 0
        else:
            # Find previous day's starter
            # For simplicity, we'll track this in game state
            # For now, rotate: start with next player
            prev_start = getattr(self.game_state, 'last_day_starter', 1)
            if prev_start in alive_players:
                start_index = (alive_players.index(prev_start) + 1) % len(alive_players)
            else:
                start_index = 0
        
        # Rotate list to start at start_index
        return alive_players[start_index:] + alive_players[:start_index]
    
    def process_speech(self, player_number: int, agent: BaseAgent) -> tuple[str, Optional[NominationResult], Optional[Dict]]:
        """
        Process a player's speech.
        Returns (speech_text, nomination_result, context_data)
        """
        context = agent.build_context(self.game_state)
        
        # Capture prompt/context for LLM agents before generating speech
        context_data = None
        if hasattr(agent, 'build_strategic_prompt'):
            try:
                prompt = agent.build_strategic_prompt(context, "speech")
                context_data = {
                    "prompt": prompt,
                    "player_role": agent.player.role.role_type.value,
                    "player_team": agent.player.role.team.value
                }
            except:
                pass
        
        speech = agent.get_day_speech(context)
        
        # Add reasoning to context_data (after LLM call)
        # Always create context_data for LLM agents to show reasoning section in UI
        if hasattr(agent, 'build_strategic_prompt'):
            if context_data is None:
                context_data = {}
            # Add reasoning if available, otherwise set to None so UI can show "No reasoning available"
            if hasattr(agent, 'last_reasoning') and agent.last_reasoning:
                context_data["reasoning"] = agent.last_reasoning
            elif "reasoning" not in context_data:
                context_data["reasoning"] = None  # Explicitly set to None so UI knows to show message
        
        # Validate speech ending
        if not self.judge.validate_speech_ending(speech):
            speech += " PASS"  # Auto-add if missing
        
        # Validate length (token limits are enforced by LLM, this is just a check)
        is_valid, message = self.judge.validate_speech_length(speech)
        if not is_valid:
            # Should not happen with token-based limits, but handle gracefully
            # Token limits are enforced by the LLM call itself
            pass
        
        # Add to player history
        player = self.game_state.get_player(player_number)
        if player:
            player.add_speech(speech)
        
        # Check for nomination (but don't announce yet - we'll announce after speech is displayed)
        nomination_result = self.judge.process_nomination(player_number, speech, announce=False)
        
        return speech, nomination_result, context_data
    
    def run_day_phase(self, agents: dict[int, BaseAgent]) -> None:
        """
        Run the complete day phase.
        Each alive player gets a turn to speak.
        """
        # Only start day if we're transitioning from another phase
        # (game starts in DAY phase with day_number=1, so first call shouldn't increment)
        if self.game_state.phase != GamePhase.DAY:
            self.judge.start_day()
        else:
            # Already in DAY phase, just announce (don't increment day_number)
            alive_players = [p.player_number for p in self.game_state.get_alive_players()]
            self.judge.announce(f"Morning has come (in the city). Players alive: {alive_players}")
        
        speaking_order = self.get_speaking_order()
        
        if not speaking_order:
            return
        
        # Store starter for next day
        self.game_state.last_day_starter = speaking_order[0]
        
        # Process each player's speech
        for player_number in speaking_order:
            if player_number not in agents:
                continue
            
            agent = agents[player_number]
            player = self.game_state.get_player(player_number)
            
            if not player or not player.is_alive:
                continue
            
            speech, nomination_result, context_data = self.process_speech(player_number, agent)
            
            # Emit speech event with context
            if self.event_emitter:
                self.event_emitter.emit_speech(player_number, speech, self.game_state.day_number, context_data)
            
            # Display speech first
            self.judge.player_speaks(player_number, speech)
            
            # Then announce nomination result
            if nomination_result and (nomination_result.success or nomination_result.target is not None):
                # Emit nomination event (no context needed - nomination is parsed from speech which already has context)
                if self.event_emitter and nomination_result.target:
                    self.event_emitter.emit_nomination(
                        player_number,
                        nomination_result.target,
                        nomination_result.success,
                        self.game_state.day_number
                    )
                
                # Announce the nomination result
                if nomination_result.success and nomination_result.target:
                    self.judge.announce(f"Accepted. Player {nomination_result.target} has been nominated by Player {player_number}.")
                elif nomination_result.target and nomination_result.first_nominator:
                    self.judge.announce(f"Rejected. Player {nomination_result.target} is already nominated by Player {nomination_result.first_nominator}.")
        
        # Check if voting can proceed
        nominations = self.judge.get_nominated_players()
        
        if len(nominations) == 0:
            # No nominations - skip voting and go directly to night
            self.judge.announce("No nominations made. Proceeding to night phase.")
            self.judge.start_night()
            return
        
        if self.game_state.day_number == 1 and len(nominations) == 1:
            # First day: single nomination = no vote
            self.judge.announce("Only one player nominated on first day. No vote will occur.")
            self.judge.start_night()
            return
        
        if len(nominations) == 1 and self.game_state.day_number > 1:
            # Subsequent days: single nomination = automatic elimination
            target = nominations[0]
            self.judge.announce(f"Only one player nominated. Player {target} is automatically eliminated.")
            # All alive players voted (unanimous)
            voters = [p.player_number for p in self.game_state.get_alive_players() if p.player_number != target]
            self.game_state.eliminate_player(
                target, 
                "unanimous nomination",
                day_number=self.game_state.day_number,
                voters=voters
            )
            # Collect final speech from eliminated player
            player = self.game_state.get_player(target)
            if player and target in agents:
                self.judge.announce(f"Player {target} has been eliminated. This is your final speech.")
                agent = agents[target]
                context = agent.build_context(self.game_state)
                final_speech = agent.get_final_speech(context)
                
                # Add to player history
                player.add_speech(final_speech)
                
                # Emit final speech event
                if self.event_emitter:
                    # Capture context for LLM agents
                    context_data = None
                    if isinstance(agent, SimpleLLMAgent):
                        try:
                            prompt = agent.build_strategic_prompt(context, "final_speech")
                            context_data = {
                                "prompt": prompt,
                                "player_role": agent.player.role.role_type.value,
                                "player_team": agent.player.role.team.value
                            }
                        except:
                            pass
                    
                    # Add reasoning to context_data (after LLM call)
                    # Always create context_data for LLM agents to show reasoning section in UI
                    if context_data is None:
                        context_data = {}
                    if hasattr(agent, 'last_reasoning') and agent.last_reasoning:
                        context_data["reasoning"] = agent.last_reasoning
                    elif "reasoning" not in context_data:
                        context_data["reasoning"] = None  # Explicitly set to None so UI knows to show message
                    
                    self.event_emitter.emit_speech(target, final_speech, self.game_state.day_number, context_data)
            
            # After elimination, check if game continues, then go to night
            if self.game_state.phase != GamePhase.GAME_OVER:
                self.judge.start_night()
            return
        
        # Proceed to voting
        if len(nominations) > 0:
            self.judge.start_voting()

