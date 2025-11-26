"""
Main game loop for Mafia simulation.
"""

import argparse
import random
from typing import Dict, Optional

# Try to load from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, that's okay

from src.core import GameState, GamePhase, Judge, Player
from src.agents import BaseAgent, SimpleLLMAgent, DummyAgent
from src.agents.exceptions import LLMEmptyResponseError
from src.phases import DayPhaseHandler, VotingHandler, NightPhaseHandler
from src.config.game_config import default_config
from src.config.config_loader import load_config
from src.web import EventEmitter, RunRecorder


class MafiaGame:
    """Main game controller."""
    
    def __init__(self, config=None, event_emitter: EventEmitter = None, run_name: Optional[str] = None):
        self.config = config or default_config
        
        # Create run recorder and event emitter
        if event_emitter is None:
            run_recorder = RunRecorder()
            run_name = run_recorder.create_run(run_name)
            self.event_emitter = EventEmitter(run_recorder)
            self.run_recorder = run_recorder
            print(f"Recording game to: runs/{run_name}/")
        else:
            self.event_emitter = event_emitter
            self.run_recorder = event_emitter.run_recorder if hasattr(event_emitter, 'run_recorder') else None
        
        # Generate seed if not provided
        if self.config.random_seed is None:
            self.config.random_seed = random.randint(0, 2**31 - 1)
        
        # Pass random seed to game state for reproducible role assignment
        self.game_state = GameState(
            max_rounds=self.config.max_rounds,
            random_seed=self.config.random_seed,
            event_emitter=self.event_emitter
        )
        self.judge = Judge(self.game_state, self.config, event_emitter=self.event_emitter)
        self.agents: Dict[int, BaseAgent] = {}
        
        # Phase handlers (pass event emitter if available)
        self.day_handler = DayPhaseHandler(self.game_state, self.judge, event_emitter=self.event_emitter)
        self.voting_handler = VotingHandler(self.game_state, self.judge, event_emitter=self.event_emitter)
        self.night_handler = NightPhaseHandler(self.game_state, self.judge, event_emitter=self.event_emitter)
        
        # Initialize agents
        self._initialize_agents()
    
    def _initialize_agents(self):
        """Initialize agents for all players based on config."""
        # Check if per-player agent types are specified
        if self.config.agent_types:
            # Use per-player agent types
            for player in self.game_state.players:
                player_agent_type = self.config.agent_types.get(
                    player.player_number, 
                    self.config.agent_type
                ).lower()
                agent = self._create_agent(player, player_agent_type)
                self.agents[player.player_number] = agent
        else:
            # Use single agent type for all players
            agent_type = self.config.agent_type.lower()
            for player in self.game_state.players:
                agent = self._create_agent(player, agent_type)
                self.agents[player.player_number] = agent
        
    def _create_agent(self, player: Player, agent_type: str) -> BaseAgent:
        """Create an agent of the specified type for a player."""
        if agent_type == "dummy_agent":
            return DummyAgent(player, self.config)
        elif agent_type == "simple_llm_agent":
            return SimpleLLMAgent(player, self.config, event_emitter=self.event_emitter)
        else:
            raise ValueError(
                f"Unknown agent_type: {agent_type}. "
                f"Must be 'simple_llm_agent' or 'dummy_agent'"
            )
    
    def run_game(self) -> str:
        """
        Run the complete game until win condition.
        Returns winning team name.
        """
        players = [p.player_number for p in self.game_state.players]
        mafia = [p.player_number for p in self.game_state.get_mafia_players()]
        sheriff = [p.player_number for p in self.game_state.players if p.role.role_type.value == 'sheriff'][0]
        
        # Emit game start event
        if self.event_emitter:
            agent_types = {}
            if self.config.agent_types:
                for p, a in self.agents.items():
                    agent_types[p] = "llm" if isinstance(a, SimpleLLMAgent) else "dummy"
            self.event_emitter.emit_game_start(players, mafia, sheriff, agent_types)
            
            # Save initial metadata
            if self.run_recorder:
                self.run_recorder.save_metadata({
                    "players": players,
                    "mafia": mafia,
                    "sheriff": sheriff,
                    "agent_types": agent_types,
                    "config": {
                        "llm_model": self.config.llm_model,
                        "agent_type": self.config.agent_type,
                        "max_rounds": self.config.max_rounds,
                        "random_seed": self.config.random_seed
                    }
                })
        
        print("=" * 60)
        print("MAFIA GAME - Starting")
        print("=" * 60)
        print(f"Players: {players}")
        print(f"Mafia: {mafia}")
        print(f"Sheriff: {sheriff}")
        
        # Show agent types if mixed
        if self.config.agent_types:
            llm_players = [p for p, a in self.agents.items() if isinstance(a, SimpleLLMAgent)]
            dummy_players = [p for p, a in self.agents.items() if isinstance(a, DummyAgent)]
            print(f"LLM Agents: {llm_players}")
            print(f"Dummy Agents: {dummy_players}")
        
        print("=" * 60)
        print()
        
        # Game loop
        try:
            while self.game_state.phase != GamePhase.GAME_OVER and self.game_state.phase != GamePhase.FAILED:
                
                # Day Phase
                if self.game_state.phase == GamePhase.DAY:
                    print(f"\n--- DAY {self.game_state.day_number} ---")
                    if self.event_emitter:
                        self.event_emitter.emit_phase_change(
                            "day", 
                            self.game_state.day_number, 
                            self.game_state.night_number
                        )
                        self.game_state._emit_game_state_update()
                    self.day_handler.run_day_phase(self.agents)
                
                # Voting Phase
                if self.game_state.phase == GamePhase.VOTING:
                    print(f"\n--- VOTING (Day {self.game_state.day_number}) ---")
                    if self.event_emitter:
                        self.event_emitter.emit_phase_change(
                            "voting", 
                            self.game_state.day_number, 
                            self.game_state.night_number
                        )
                        self.game_state._emit_game_state_update()
                    self.voting_handler.run_voting_phase(self.agents)
                    
                    if self.game_state.phase == GamePhase.GAME_OVER or self.game_state.phase == GamePhase.FAILED:
                        break
                    
                    # Transition to night (after voting)
                    self.game_state.start_night()
                
                # Night Phase (happens after day/voting)
                if self.game_state.phase == GamePhase.NIGHT:
                    print(f"\n--- NIGHT {self.game_state.night_number} ---")
                    if self.event_emitter:
                        self.event_emitter.emit_phase_change(
                            "night", 
                            self.game_state.day_number, 
                            self.game_state.night_number
                        )
                        self.game_state._emit_game_state_update()
                    self.night_handler.run_night_phase(self.agents)
                    
                    if self.game_state.phase == GamePhase.GAME_OVER or self.game_state.phase == GamePhase.FAILED:
                        break
                    
                    # Transition to next day
                    self.game_state.start_day()
                
                # Check win condition after each phase (handles max_rounds)
                winner = self.game_state.check_win_condition()
                if winner:
                    # Determine if game ended due to max rounds
                    reason = "max_rounds" if (
                        self.game_state.max_rounds is not None and 
                        self.game_state.day_number >= self.game_state.max_rounds
                    ) else "win_condition"
                    self.game_state.end_game(winner, reason=reason)
                    break
                
                # Safety check
                alive_count = len(self.game_state.get_alive_players())
                if alive_count < 2:
                    break
        except LLMEmptyResponseError as e:
            # Fatal error: LLM returned empty response
            print(f"\n❌ FATAL ERROR: {e.message}")
            print(f"   Player: {e.player_number}")
            print(f"   Action: {e.action_type}")
            
            # Emit fatal error event (use the full error message from exception)
            if self.event_emitter:
                self.event_emitter.emit_fatal_error(
                    e.message,
                    e.player_number,
                    e.action_type
                )
            
            self.game_state.end_game(reason="failed")
            return "Failed"
        
        # Game over
        if self.game_state.phase == GamePhase.FAILED:
            if self.event_emitter:
                self.event_emitter.emit_game_over(
                    None, 
                    "failed", 
                    self.game_state.day_number, 
                    self.game_state.night_number
                )
            print("\n" + "=" * 60)
            print("GAME FAILED - Fatal Error")
            print("=" * 60)
            self._print_game_summary()
            return "Failed"
        
        winner = self.game_state.winner
        if winner:
            winner_name = "Civilians (Red Team)" if winner.value == "red" else "Mafia (Black Team)"
            if self.event_emitter:
                reason = "max_rounds" if (
                    self.game_state.max_rounds is not None and 
                    self.game_state.day_number >= self.game_state.max_rounds
                ) else "win_condition"
                self.event_emitter.emit_game_over(
                    winner.value, 
                    reason, 
                    self.game_state.day_number, 
                    self.game_state.night_number
                )
            print("\n" + "=" * 60)
            print(f"GAME OVER - {winner_name} WIN!")
            
            # Check if game ended due to max rounds
            if (self.game_state.max_rounds is not None and 
                self.game_state.day_number >= self.game_state.max_rounds):
                print(f"(Game ended at max rounds limit: {self.game_state.max_rounds})")
            
            print("=" * 60)
            self._print_game_summary()
            return winner_name
        else:
            print("\nGame ended without clear winner")
            return "Draw"
    
    def _print_game_summary(self) -> None:
        """Print a nicely formatted game summary."""
        alive_players = self.game_state.get_alive_players()
        mafia_players = self.game_state.get_mafia_players()
        civilian_players = self.game_state.get_civilian_players()
        
        print("\n📊 GAME SUMMARY")
        print("-" * 60)
        
        # Winner
        if self.game_state.winner:
            winner_display = "Civilians (Red Team)" if self.game_state.winner.value == "red" else "Mafia (Black Team)"
            print(f"Winner: {winner_display}")
        else:
            print("Winner: None (Draw)")
        
        # Game stats
        print(f"Total Days: {self.game_state.day_number}")
        print(f"Total Nights: {self.game_state.night_number}")
        
        # Random seed (always shown, was generated if not provided)
        print(f"Random Seed: {self.config.random_seed}")
        
        # Player counts
        print(f"\nFinal Player Count:")
        print(f"  • Alive: {len(alive_players)}")
        print(f"  • Mafia: {len(mafia_players)}")
        print(f"  • Civilians: {len(civilian_players)}")
        
        # Alive players breakdown
        if alive_players:
            print(f"\nAlive Players:")
            for player in sorted(alive_players, key=lambda p: p.player_number):
                role_name = player.role.role_type.value.title()
                team = "Red" if player.role.team.value == "red" else "Black"
                print(f"  • Player {player.player_number}: {role_name} ({team})")
        
        # Eliminated players
        eliminated = [p for p in self.game_state.players if not p.is_alive]
        if eliminated:
            print(f"\nEliminated Players ({len(eliminated)}):")
            for player in sorted(eliminated, key=lambda p: p.player_number):
                role_name = player.role.role_type.value.title()
                team = "Red" if player.role.team.value == "red" else "Black"
                
                # Find elimination details from action log
                elimination_info = None
                for action in self.game_state.action_log:
                    if (action.get("type") == "player_eliminated" and 
                        action.get("data", {}).get("player") == player.player_number):
                        elimination_info = action.get("data", {})
                        break
                
                # Format elimination details
                if elimination_info:
                    reason = elimination_info.get("reason", "")
                    night_num = elimination_info.get("night_number")
                    day_num = elimination_info.get("day_number")
                    voters = elimination_info.get("voters", [])
                    
                    if reason == "night kill" and night_num is not None:
                        details = f"killed by mafia on night {night_num}"
                    elif day_num is not None and voters:
                        details = f"eliminated by players {voters} on day {day_num}"
                    elif day_num is not None:
                        details = f"eliminated on day {day_num}"
                    else:
                        details = reason
                    
                    print(f"  • Player {player.player_number}: {role_name} ({team}) - {details}")
                else:
                    print(f"  • Player {player.player_number}: {role_name} ({team})")
    
    def get_game_summary(self) -> Dict:
        """Get final game summary as dictionary."""
        return {
            "winner": self.game_state.winner.value if self.game_state.winner else None,
            "rounds": self.game_state.day_number,
            "nights": self.game_state.night_number,
            "final_state": self.game_state.get_game_summary(),
            "action_log": self.game_state.action_log[-10:],  # Last 10 actions
        }


def main():
    """Entry point for running a game."""
    parser = argparse.ArgumentParser(
        description="Run a Mafia game simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                                    # Use default config
  python main.py --config configs/dummy_agent.yaml  # Use dummy agent
  python main.py --config configs/simple_llm_agent.yaml   # Use simple LLM agent
  python main.py --config configs/simple_llm_agent.yaml --model gpt-5-nano  # Override model
  python main.py --model gpt-4o-mini                # Override model with default config
        """
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="Path to YAML configuration file (default: use default config)"
    )
    parser.add_argument(
        "--seed",
        "-s",
        type=int,
        default=None,
        help="Random seed for reproducible behavior (if not provided, a random seed will be generated and shown)"
    )
    parser.add_argument(
        "--model",
        "-m",
        type=str,
        default=None,
        help="LLM model to use (e.g., 'gpt-5-mini', 'gpt-4o-mini', 'gpt-5-nano'). Overrides config file setting."
    )
    parser.add_argument(
        "--run-name",
        "-r",
        type=str,
        default=None,
        help="Custom name for this run (default: auto-generated timestamp)"
    )
    
    args = parser.parse_args()
    
    # Load config from YAML if provided, otherwise use default
    config = load_config(args.config) if args.config else default_config
    
    # Seed is only set via command line, ignore any seed in YAML config
    if args.seed is not None:
        config.random_seed = args.seed
    else:
        # Explicitly set to None so it will be auto-generated in MafiaGame
        config.random_seed = None
    
    # Model override from command line
    if args.model is not None:
        config.llm_model = args.model
    
    # Terminal mode (always console mode now)
    print("Mafia Game Simulation")
    print("=" * 60)
    if args.config:
        print(f"Using config: {args.config}")
        print(f"Agent type: {config.agent_type}")
    if args.model:
        print(f"Model override: {args.model}")
    print("=" * 60)
    
    game = MafiaGame(config=config, run_name=args.run_name)
    winner = game.run_game()
    
    # Summary already printed in run_game()
    # Additional detailed summary available via game.get_game_summary()
    
    if game.run_recorder:
        run_path = game.run_recorder.get_run_path()
        if run_path:
            print(f"\nGame events saved to: {run_path}")


if __name__ == "__main__":
    main()

