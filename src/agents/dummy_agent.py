"""
Dummy Agent implementation with deterministic behavior.
"""

import random
from typing import Dict, Any

from .base_agent import BaseAgent, AgentContext
from ..core import Player, RoleType
from ..config.game_config import GameConfig, default_config


class DummyAgent(BaseAgent):
    """
    Simple dummy agent with deterministic behavior:
    - All players: Nominate a random alive player, then vote for that player
    - Sheriff: Check random alive player (not sheriff itself) who hasn't been checked before
    - Mafia: Kill random red (civilian) player who is alive
    - Don: Check random red (civilian) player who is alive and hasn't been checked before
    """
    
    def __init__(self, player: Player, config: GameConfig = default_config):
        super().__init__(player, config)
        # Use seed from config if provided, otherwise use None (non-deterministic)
        seed = config.random_seed
        if seed is not None:
            # Combine seed with player number to ensure each player has different but reproducible randomness
            self.random = random.Random(seed + player.player_number)
        else:
            self.random = random.Random()
        # Track which players have been checked (for sheriff and don)
        self.checked_players: set[int] = set()
        # Track nominated player for current day (to vote for them later)
        self.current_day_nomination: Dict[int, int] = {}  # {day_number: nominated_player}
    
    def get_day_speech(self, context: AgentContext) -> str:
        """
        Generate day speech - nominate a random alive player.
        
        Args:
            context: Current game context
            
        Returns:
            The speech text with nomination
        """
        # Get all alive players except self
        alive_players = context.game_state.get_alive_players()
        available_targets = [
            p.player_number for p in alive_players 
            if p.player_number != self.player.player_number
        ]
        
        if available_targets:
            # Pick a random target to nominate
            target = self.random.choice(available_targets)
            # Store nomination for this day
            self.current_day_nomination[context.game_state.day_number] = target
            return f"I am Player {self.player.player_number}. I nominate player number {target}. PASS"
        else:
            # Fallback if no other players (shouldn't happen)
            return f"I am Player {self.player.player_number}. Let me analyze the situation. PASS"
    
    def get_night_action(self, context: AgentContext) -> Dict[str, Any]:
        """
        Get night action based on role with deterministic behavior.
        
        Args:
            context: Current game context
            
        Returns:
            Dictionary containing action type and target
        """
        action = {}
        
        # Sheriff: Check random alive player (not sheriff itself) who hasn't been checked before
        if self.player.role.role_type == RoleType.SHERIFF:
            alive_players = context.game_state.get_alive_players()
            # Filter out sheriff itself and players already checked
            available_targets = [
                p.player_number for p in alive_players 
                if p.player_number != self.player.player_number 
                and p.player_number not in self.checked_players
            ]
            
            if available_targets:
                target = self.random.choice(available_targets)
                action["type"] = "sheriff_check"
                action["target"] = target
                # Track that we're checking this player
                self.checked_players.add(target)
            elif alive_players:
                # If all players have been checked, reset and pick randomly
                # (shouldn't happen in normal game, but handle edge case)
                available_targets = [
                    p.player_number for p in alive_players 
                    if p.player_number != self.player.player_number
                ]
                if available_targets:
                    target = self.random.choice(available_targets)
                    action["type"] = "sheriff_check"
                    action["target"] = target
        
        # Mafia: Kill random red (civilian) player who is alive
        # But first check if we need to make a kill decision (Don is eliminated)
        kill_claims = context.private_info.get("mafia_kill_claims", {})
        # Check if kill_claims has player numbers as keys (from process_mafia_kill)
        # vs night numbers as keys (from get_private_info - previous nights)
        # Night numbers are sequential (1, 2, 3...), player numbers are scattered (1-10)
        # If ALL keys are in alive players (or empty dict), it's likely current kill claims
        # If keys are sequential starting from 1, it's likely night numbers
        alive_player_numbers = {p.player_number for p in context.game_state.get_alive_players()}
        if isinstance(kill_claims, dict):
            keys = list(kill_claims.keys())
            if len(keys) == 0:
                # Empty dict from process_mafia_kill means no valid claims, but still a kill decision call
                is_kill_decision_call = True
            else:
                # Check if all keys are alive player numbers (current kill claims)
                all_keys_are_players = all(k in alive_player_numbers for k in keys)
                # Check if keys look like night numbers (sequential from 1)
                keys_sorted = sorted(keys)
                looks_like_night_numbers = keys_sorted == list(range(1, len(keys) + 1))
                is_kill_decision_call = all_keys_are_players and not looks_like_night_numbers
        else:
            is_kill_decision_call = False
        
        # If Don is eliminated and we're being asked to make a decision
        if is_kill_decision_call and self.player.is_mafia and self.player.role.role_type != RoleType.DON:
            # Check if Don is still alive
            don = next((p for p in context.game_state.get_mafia_players() 
                       if p.role.role_type == RoleType.DON and p.is_alive), None)
            
            # If Don is eliminated, this mafia player makes the decision
            if not don and "decide_kill" in context.available_actions:
                if kill_claims:
                    # Pick randomly from claimed targets
                    claimed_targets = list(kill_claims.values())
                    action["kill_decision"] = self.random.choice(claimed_targets)
                    action["type"] = "kill_decision"
                else:
                    # Fallback: kill random civilian
                    civilian_players = context.game_state.get_civilian_players()
                    if civilian_players:
                        action["kill_decision"] = self.random.choice(civilian_players).player_number
                        action["type"] = "kill_decision"
        elif self.player.is_mafia and self.player.role.role_type != RoleType.DON:
            # Normal kill claim (applies to regular mafia, but NOT Don)
            # Don's kill claim is handled separately below to avoid conflicts with don_check
            # Only make kill claim if this is NOT a kill decision call
            if not is_kill_decision_call:
                civilian_players = context.game_state.get_civilian_players()
                if civilian_players:
                    target = self.random.choice(civilian_players).player_number
                    action["type"] = "kill_claim"
                    action["target"] = target
        
        # Don: Check random red (civilian) player who is alive and hasn't been checked before
        # Also handles kill decision (after seeing all claims) and kill claim (like other mafia)
        if self.player.role.role_type == RoleType.DON:
            # Check if we're being called for the check (process_don_check) or kill decision (process_mafia_kill)
            # process_mafia_kill adds mafia_kill_claims as {player_number: target} dict to context.private_info
            # and sets _kill_decision_context = True to mark it as a kill decision call
            # get_private_info() returns mafia_kill_claims as {night_number: target} dict
            # So if kill_claims has player numbers as keys (not night numbers), we're in process_mafia_kill
            kill_claims = context.private_info.get("mafia_kill_claims", {})
            is_kill_decision_context = context.private_info.get("_kill_decision_context", False)
            
            # Check if kill_claims has player numbers as keys (from process_mafia_kill)
            # vs night numbers as keys (from get_private_info - previous nights)
            # Night numbers are sequential (1, 2, 3...), player numbers are scattered (1-10)
            # If ALL keys are in alive players, it's likely current kill claims
            # If keys are sequential starting from 1, it's likely night numbers
            alive_player_numbers = {p.player_number for p in context.game_state.get_alive_players()}
            if is_kill_decision_context:
                # Explicitly marked as kill decision call by process_mafia_kill
                is_kill_decision_call = True
            elif isinstance(kill_claims, dict):
                keys = list(kill_claims.keys())
                if len(keys) == 0:
                    # Empty dict from get_private_info() means no previous nights - NOT a kill decision call
                    is_kill_decision_call = False
                else:
                    # Check if all keys are alive player numbers (current kill claims from process_mafia_kill)
                    all_keys_are_players = all(k in alive_player_numbers for k in keys)
                    # Check if keys look like night numbers (sequential from 1)
                    keys_sorted = sorted(keys)
                    looks_like_night_numbers = keys_sorted == list(range(1, len(keys) + 1))
                    # If keys are player numbers (not night numbers), it's from process_mafia_kill
                    is_kill_decision_call = all_keys_are_players and not looks_like_night_numbers
            else:
                is_kill_decision_call = False
            
            # Priority 1: Don check (if this is a don check call, not kill decision)
            # Check if Don has already checked someone this night
            already_checked_this_night = context.game_state.night_number in self.player.don_checks
            
            if (not is_kill_decision_call and 
                "don_check" in context.available_actions and 
                not already_checked_this_night):
                civilian_players = context.game_state.get_civilian_players()
                
                # Filter out players already checked by don (use internal tracking)
                available_targets = [
                    p.player_number for p in civilian_players 
                    if p.player_number not in self.checked_players
                ]
                
                if available_targets:
                    target = self.random.choice(available_targets)
                    action["type"] = "don_check"
                    action["target"] = target
                    # Track that we're checking this player
                    self.checked_players.add(target)
                elif civilian_players:
                    # If all civilians have been checked, reset and pick randomly
                    available_targets = [p.player_number for p in civilian_players]
                    if available_targets:
                        target = self.random.choice(available_targets)
                        action["type"] = "don_check"
                        action["target"] = target
                        # Still track it
                        self.checked_players.add(target)
            
            # Priority 2: Kill decision (when called with kill claims in context)
            # This happens when process_mafia_kill calls the Don with kill_claims in context
            if is_kill_decision_call and "decide_kill" in context.available_actions:
                # Get all mafia kill claims from context
                kill_claims = context.private_info.get("mafia_kill_claims", {})
                if kill_claims:
                    # Pick randomly from claimed targets
                    claimed_targets = list(kill_claims.values())
                    action["kill_decision"] = self.random.choice(claimed_targets)
                    # Override any previous action type
                    action["type"] = "kill_decision"
                else:
                    # No claims (Don is only mafia or no valid claims) - kill random civilian
                    civilian_players = context.game_state.get_civilian_players()
                    if civilian_players:
                        action["kill_decision"] = self.random.choice(civilian_players).player_number
                        # Override any previous action type
                        action["type"] = "kill_decision"
            
            # Priority 3: Kill claim (only if we haven't already set don_check or kill_decision)
            # Don also makes a kill claim like other mafia during the kill claim phase
            if (not is_kill_decision_call and 
                action.get("type") not in ["don_check", "kill_decision"]):
                civilian_players = context.game_state.get_civilian_players()
                if civilian_players:
                    target = self.random.choice(civilian_players).player_number
                    action["type"] = "kill_claim"
                    action["target"] = target
        
        return action
    
    def get_vote_choice(self, context: AgentContext) -> int:
        """
        Get vote choice - vote for the player this agent nominated.
        
        Args:
            context: Current game context
            
        Returns:
            Player number to vote against (the player we nominated)
        """
        # Vote for the player we nominated this day
        day_number = context.game_state.day_number
        if day_number in self.current_day_nomination:
            nominated_player = self.current_day_nomination[day_number]
            # Verify the nominated player is still in the nominations list
            nominations = context.game_state.nominations.get(day_number, [])
            if nominated_player in nominations:
                return nominated_player
        
        # Fallback: vote for first nominated player if our nomination isn't available
        nominations = context.game_state.nominations.get(day_number, [])
        if nominations:
            return nominations[0]
        
        # Final fallback
        alive_players = context.game_state.get_alive_players()
        if alive_players:
            return self.random.choice([p.player_number for p in alive_players])
        return 1

