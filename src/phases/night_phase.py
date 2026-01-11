"""
Night phase handler for mafia kills and role checks.
"""

from typing import List, Dict, Optional, Any, TYPE_CHECKING
from ..core import GameState, GamePhase, Judge, RoleType
from ..agents import BaseAgent

if TYPE_CHECKING:
    from ..web.event_emitter import EventEmitter


class NightPhaseHandler:
    """Handles night phase operations: mafia kills, Don checks, Sheriff checks."""
    
    def __init__(self, game_state: GameState, judge: Judge, event_emitter: Optional['EventEmitter'] = None):
        self.game_state = game_state
        self.judge = judge
        self.event_emitter = event_emitter
    
    def process_mafia_kill(self, agents: dict[int, BaseAgent]) -> Optional[int]:
        """
        Process mafia kill phase.
        All mafia make claims, Don makes final decision.
        Returns killed player number or None.
        """
        self.judge.announce("The mafia goes hunting.")
        
        mafia_players = self.game_state.get_mafia_players()
        if not mafia_players:
            return None
        
        # Collect kill claims from all mafia
        kill_claims = {}
        for player in mafia_players:
            if player.player_number in agents:
                agent = agents[player.player_number]
                context = agent.build_context(self.game_state)
                
                # Capture context for LLM agents
                context_data = None
                if hasattr(agent, 'build_strategic_prompt'):
                    try:
                        prompt = agent.build_strategic_prompt(context, "kill_claim")
                        context_data = {
                            "prompt": prompt,
                            "player_role": agent.player.role.role_type.value,
                            "player_team": agent.player.role.team.value
                        }
                    except:
                        pass
                
                action = agent.get_night_action(context)
                
                # Add reasoning to context_data (after LLM call)
                # Always create context_data for LLM agents to show reasoning section in UI
                if context_data is None:
                    context_data = {}
                if hasattr(agent, 'last_reasoning') and agent.last_reasoning:
                    context_data["reasoning"] = agent.last_reasoning
                elif "reasoning" not in context_data:
                    context_data["reasoning"] = None  # Explicitly set to None so UI knows to show message
                
                if action.get("type") == "kill_claim":
                    target = action.get("target")
                    if target and self._is_valid_target(target):
                        kill_claims[player.player_number] = target
                        player.add_mafia_kill_claim(self.game_state.night_number, target)
                        # Log kill claim
                        print(f"[MAFIA] Player {player.player_number} claims kill on Player {target}.")
                        # Emit kill claim event
                        if self.event_emitter:
                            self.event_emitter.emit_night_kill_claim(
                                player.player_number, 
                                target, 
                                self.game_state.night_number,
                                context_data
                            )
        
        # Don makes final decision (or another mafia if Don is eliminated)
        don = next((p for p in mafia_players if p.role.role_type == RoleType.DON and p.is_alive), None)
        
        # If Don is eliminated, select first alive mafia to make decision
        if not don or don.player_number not in agents:
            # Find first alive mafia player
            alive_mafia = [p for p in mafia_players if p.is_alive and p.player_number in agents]
            if not alive_mafia:
                self.judge.announce("The mafia leaves.")
                return None
            
            decision_maker = alive_mafia[0]
            is_don = False
        else:
            decision_maker = don
            is_don = True
        
        # Decision maker sees all claims and decides
        decision_agent = agents[decision_maker.player_number]
        context = decision_agent.build_context(self.game_state)
        
        # Add claims to context for decision maker
        # Mark this as a kill decision call (even if kill_claims is empty)
        context.private_info["mafia_kill_claims"] = kill_claims
        context.private_info["_kill_decision_context"] = True
        
        # Capture context for LLM agents
        context_data = None
        if hasattr(decision_agent, 'build_strategic_prompt'):
            try:
                prompt = decision_agent.build_strategic_prompt(context, "kill_decision")
                context_data = {
                    "prompt": prompt,
                    "player_role": decision_agent.player.role.role_type.value,
                    "player_team": decision_agent.player.role.team.value
                }
            except:
                pass
        
        action = decision_agent.get_night_action(context)
        
        # Add reasoning to context_data (after LLM call)
        # Always create context_data for LLM agents to show reasoning section in UI
        if context_data is None:
            context_data = {}
        if hasattr(decision_agent, 'last_reasoning') and decision_agent.last_reasoning:
            context_data["reasoning"] = decision_agent.last_reasoning
        elif "reasoning" not in context_data:
            context_data["reasoning"] = None  # Explicitly set to None so UI knows to show message
        
        if action.get("type") == "kill_decision" or "kill_decision" in action:
            target = action.get("kill_decision") or action.get("target")
            
            if target and self._is_valid_target(target):
                # Log decision
                if is_don:
                    print(f"[DON] Decides to kill Player {target}.")
                    decision_maker.add_mafia_kill_decision(self.game_state.night_number, target)
                else:
                    print(f"[MAFIA] Player {decision_maker.player_number} decides to kill Player {target}.")
                    # Store decision (mafia player making decision when Don is eliminated)
                    decision_maker.add_mafia_kill_decision(self.game_state.night_number, target)
                
                # Emit kill decision event
                if self.event_emitter:
                    self.event_emitter.emit_night_kill_decision(
                        decision_maker.player_number,
                        target,
                        is_don,
                        self.game_state.night_number,
                        context_data
                    )
                
                self.game_state.night_kills[self.game_state.night_number] = target
                return target
        
        # No valid kill
        self.judge.announce("The mafia leaves.")
        return None
    
    def process_don_check(self, agents: dict[int, BaseAgent]) -> Optional[Dict[str, Any]]:
        """
        Process Don's check for Sheriff.
        Returns check result or None.
        """
        don = next((p for p in self.game_state.get_mafia_players() 
                   if p.role.role_type == RoleType.DON), None)
        
        if not don or don.player_number not in agents:
            return None
        
        self.judge.announce("The Don wakes up, you have ten seconds.")
        
        agent = agents[don.player_number]
        context = agent.build_context(self.game_state)
        
        # Capture context for LLM agents
        context_data = None
        if hasattr(agent, 'build_strategic_prompt'):
            try:
                prompt = agent.build_strategic_prompt(context, "don_check")
                context_data = {
                    "prompt": prompt,
                    "player_role": agent.player.role.role_type.value,
                    "player_team": agent.player.role.team.value
                }
            except:
                pass
        
        action = agent.get_night_action(context)
        
        # Add reasoning to context_data (after LLM call)
        # Always create context_data for LLM agents to show reasoning section in UI
        if context_data is None:
            context_data = {}
        if hasattr(agent, 'last_reasoning') and agent.last_reasoning:
            context_data["reasoning"] = agent.last_reasoning
        elif "reasoning" not in context_data:
            context_data["reasoning"] = None  # Explicitly set to None so UI knows to show message
        
        if action.get("type") == "don_check":
            target = action.get("target")
            
            if target and self._is_valid_target(target):
                # Announce Don's check
                print(f"[DON] Checking Player {target}...")
                
                # Check if target is Sheriff
                target_player = self.game_state.get_player(target)
                is_sheriff = target_player and target_player.role.role_type == RoleType.SHERIFF
                
                result = "Sheriff" if is_sheriff else "Not the Sheriff"
                don.add_don_check(self.game_state.night_number, target, result)
                
                # Emit Don check event
                if self.event_emitter:
                    self.event_emitter.emit_don_check(target, result, self.game_state.night_number, context_data)
                
                # Announce result
                self.judge.announce(f"Player {target} is {result}.")
                self.judge.announce("The Don goes to sleep.")
                
                return {"target": target, "result": result}
        
        return None
    
    def process_sheriff_check(self, agents: dict[int, BaseAgent]) -> Optional[Dict[str, Any]]:
        """
        Process Sheriff's check.
        Returns check result or None.
        """
        sheriff = next((p for p in self.game_state.get_civilian_players() 
                       if p.role.role_type == RoleType.SHERIFF), None)
        
        if not sheriff or sheriff.player_number not in agents:
            return None
        
        self.judge.announce("The Sheriff wakes up, you have ten seconds.")
        
        agent = agents[sheriff.player_number]
        context = agent.build_context(self.game_state)
        
        # Capture context for LLM agents
        context_data = None
        if hasattr(agent, 'build_strategic_prompt'):
            try:
                prompt = agent.build_strategic_prompt(context, "sheriff_check")
                context_data = {
                    "prompt": prompt,
                    "player_role": agent.player.role.role_type.value,
                    "player_team": agent.player.role.team.value
                }
            except:
                pass
        
        action = agent.get_night_action(context)
        
        # Add reasoning to context_data (after LLM call)
        # Always create context_data for LLM agents to show reasoning section in UI
        if context_data is None:
            context_data = {}
        if hasattr(agent, 'last_reasoning') and agent.last_reasoning:
            context_data["reasoning"] = agent.last_reasoning
        elif "reasoning" not in context_data:
            context_data["reasoning"] = None  # Explicitly set to None so UI knows to show message
        
        if action.get("type") == "sheriff_check":
            target = action.get("target")
            
            if target and self._is_valid_target(target):
                # Announce Sheriff's check
                print(f"[SHERIFF] Checking Player {target}...")
                
                # Check if target is mafia
                target_player = self.game_state.get_player(target)
                is_mafia = target_player and target_player.is_mafia
                
                result = "Black" if is_mafia else "Red"
                sheriff.add_sheriff_check(self.game_state.night_number, target, result)
                
                # Emit Sheriff check event
                if self.event_emitter:
                    self.event_emitter.emit_sheriff_check(target, result, self.game_state.night_number, context_data)
                
                # Announce result
                self.judge.announce(f"Player {target} is {result}.")
                self.judge.announce("The Sheriff goes to sleep.")
                
                return {"target": target, "result": result}
        
        return None
    
    def _is_valid_target(self, target: int) -> bool:
        """Check if target is valid (alive and exists)."""
        if target < 1 or target > 10:
            return False
        
        player = self.game_state.get_player(target)
        return player is not None and player.is_alive
    
    def run_night_phase(self, agents: dict[int, BaseAgent]) -> None:
        """
        Run complete night phase.
        Sequence: Sheriff Check -> Mafia Kill -> Don Check
        Validates that all required actions are performed.
        """
        # Only start night if we're transitioning from another phase
        # (night is already started by day_phase or main loop)
        if self.game_state.phase != GamePhase.NIGHT:
            self.judge.start_night()
        else:
            # Already in NIGHT phase, just announce
            self.judge.announce("Night falls.")
        
        # Track which actions were performed
        mafia_kill_performed = False
        don_check_performed = False
        sheriff_check_performed = False
        
        # Check who should be alive BEFORE processing actions (to know what's required)
        mafia_players_before = self.game_state.get_mafia_players()
        don_before = next((p for p in mafia_players_before if p.role.role_type == RoleType.DON and p.is_alive), None)
        sheriff_before = next((p for p in self.game_state.get_civilian_players() 
                              if p.role.role_type == RoleType.SHERIFF and p.is_alive), None)
        
        # Track if don/sheriff were alive at start (for validation)
        don_was_alive = don_before is not None and don_before.is_alive and don_before.player_number in agents
        sheriff_was_alive = sheriff_before is not None and sheriff_before.is_alive and sheriff_before.player_number in agents
        mafia_was_alive = len([p for p in mafia_players_before if p.is_alive and p.player_number in agents]) > 0
        
        # 1. Sheriff Check (first, so sheriff can check even if killed this night)
        if self.game_state.phase == GamePhase.NIGHT:
            sheriff_check_result = self.process_sheriff_check(agents)
            if sheriff_check_result is not None:
                sheriff_check_performed = True
            
            # Check win condition after Sheriff check
            if self.game_state.phase == GamePhase.GAME_OVER or self.game_state.phase == GamePhase.FAILED:
                return
        
        # 2. Mafia Kill
        killed = self.process_mafia_kill(agents)
        if killed:
            mafia_kill_performed = True
            self.game_state.eliminate_player(
                killed, 
                "night kill",
                night_number=self.game_state.night_number
            )
            player = self.game_state.get_player(killed)
            if player and killed in agents:
                self.judge.announce(f"Player {killed} has been killed.")
                # Collect final speech from eliminated player
                agent = agents[killed]
                context = agent.build_context(self.game_state)
                final_speech = agent.get_final_speech(context)
                
                # Add to player history
                player.add_speech(final_speech)
                
                # Emit final speech event
                if self.event_emitter:
                    # Capture context for LLM agents
                    from ..agents.llm_agent import SimpleLLMAgent
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
                    
                    self.event_emitter.emit_speech(killed, final_speech, self.game_state.day_number, context_data)
        
        # Check win condition after kill - if game ended, skip remaining night actions
        if self.game_state.phase == GamePhase.GAME_OVER or self.game_state.phase == GamePhase.FAILED:
            return
        
        # 3. Don Check (every night) - only if game hasn't ended
        if self.game_state.phase == GamePhase.NIGHT:
            don_check_result = self.process_don_check(agents)
            if don_check_result is not None:
                don_check_performed = True
            
            # Check win condition again after Don check
            if self.game_state.phase == GamePhase.GAME_OVER or self.game_state.phase == GamePhase.FAILED:
                return
        
        # Validate required actions - only if game is still ongoing
        if self.game_state.phase == GamePhase.NIGHT:
            errors = []
            
            # Check if Don is still alive (after kill) but no check was made
            don_still_alive = don_before and don_before.is_alive and don_before.player_number in agents
            if don_still_alive and not don_check_performed:
                errors.append(f"FATAL ERROR: Don (Player {don_before.player_number}) is alive but no Don check was made.")
            
            # Check if any mafia is still alive (after kill) but no kill was made
            mafia_players_after = self.game_state.get_mafia_players()
            alive_mafia_after = [p for p in mafia_players_after if p.is_alive and p.player_number in agents]
            if alive_mafia_after and not mafia_kill_performed:
                mafia_numbers = [p.player_number for p in alive_mafia_after]
                errors.append(f"FATAL ERROR: Mafia players {mafia_numbers} are alive but no kill was made.")
            
            # Check if Sheriff is still alive (after kill) but no check was made
            sheriff_still_alive = sheriff_before and sheriff_before.is_alive and sheriff_before.player_number in agents
            if sheriff_still_alive and not sheriff_check_performed:
                errors.append(f"FATAL ERROR: Sheriff (Player {sheriff_before.player_number}) is alive but no Sheriff check was made.")
            
            # If any validation errors, fail the game
            if errors:
                for error in errors:
                    print(f"\n❌ {error}")
                self.game_state.end_game(reason="failed")
                return

