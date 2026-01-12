"""
Simulate a full 10-player game and show context at different stages.
Uses dummy agents (no API calls) to demonstrate what the context looks like.
"""

from src.core import GameState, GamePhase, Judge
from src.agents import BaseAgent, DummyAgent
from src.agents.xml_formatter import format_game_history_xml
from src.config.game_config import default_config
from src.config.config_loader import load_config
from src.phases import DayPhaseHandler, VotingHandler, NightPhaseHandler
from src.web import EventEmitter, RunRecorder


def simulate_game_and_show_context():
    """Run a simulated game and show context at key stages."""
    
    # Use dummy agent config
    config = load_config("configs/dummy_agent.yaml")
    config.random_seed = 42  # Fixed seed for reproducibility
    
    # Create game state
    game_state = GameState(
        max_rounds=config.max_rounds,
        random_seed=config.random_seed
    )
    
    judge = Judge(game_state, config)
    
    # Initialize agents (all dummy - no API calls)
    agents = {}
    for player in game_state.players:
        agents[player.player_number] = DummyAgent(player, config)
    
    # Phase handlers
    day_handler = DayPhaseHandler(game_state, judge)
    voting_handler = VotingHandler(game_state, judge)
    night_handler = NightPhaseHandler(game_state, judge)
    
    print("=" * 80)
    print("MAFIA GAME SIMULATION - Context Demonstration")
    print("=" * 80)
    print(f"Players: {[p.player_number for p in game_state.players]}")
    print(f"Mafia: {[p.player_number for p in game_state.get_mafia_players()]}")
    sheriff = next((p for p in game_state.players if p.role.role_type.value == 'sheriff'), None)
    if sheriff:
        print(f"Sheriff: {sheriff.player_number}")
    print(f"Random Seed: {config.random_seed}")
    print("=" * 80)
    print()
    
    # Track context snapshots
    context_snapshots = []
    
    # Game loop - run a few rounds to show context evolution
    max_rounds_to_show = 3  # Show first 3 days
    round_count = 0
    
    while (game_state.phase != GamePhase.GAME_OVER and 
           game_state.phase != GamePhase.FAILED and
           round_count < max_rounds_to_show):
        
        # Day Phase
        if game_state.phase == GamePhase.DAY:
            print(f"\n{'='*80}")
            print(f"DAY {game_state.day_number}")
            print(f"{'='*80}")
            
            day_handler.run_day_phase(agents)
        
        # Voting Phase
        if game_state.phase == GamePhase.VOTING:
            print(f"\n--- VOTING (Day {game_state.day_number}) ---")
            voting_handler.run_voting_phase(agents)
            
            # Capture context after voting phase (eliminations happen during voting)
            if game_state.day_number <= max_rounds_to_show:
                # Build context for a player (let's use player 1, or first alive player)
                alive_players = game_state.get_alive_players()
                if alive_players:
                    player = alive_players[0]
                    agent = agents[player.player_number]
                    context = agent.build_context(game_state)
                    context_snapshots.append({
                        "stage": f"After Day {game_state.day_number} Voting",
                        "day": game_state.day_number,
                        "night": game_state.night_number,
                        "context": context
                    })
            
            if game_state.phase == GamePhase.GAME_OVER or game_state.phase == GamePhase.FAILED:
                break
            
            # Transition to night
            game_state.start_night()
        
        # Night Phase
        if game_state.phase == GamePhase.NIGHT:
            print(f"\n--- NIGHT {game_state.night_number} ---")
            night_handler.run_night_phase(agents)
            
            if game_state.phase == GamePhase.GAME_OVER or game_state.phase == GamePhase.FAILED:
                break
            
            # Transition to next day
            game_state.start_day()
            round_count += 1
        
        # Check win condition
        winner = game_state.check_win_condition()
        if winner:
            game_state.end_game(winner)
            break
    
    # Now show the context snapshots
    print("\n" + "=" * 80)
    print("CONTEXT SNAPSHOTS - Game History XML")
    print("=" * 80)
    print()
    
    for i, snapshot in enumerate(context_snapshots, 1):
        print(f"\n{'='*80}")
        print(f"SNAPSHOT {i}: {snapshot['stage']}")
        print(f"Day: {snapshot['day']}, Night: {snapshot['night']}")
        print(f"{'='*80}")
        print()
        
        # Format and display the game history XML
        context = snapshot['context']
        xml_history = format_game_history_xml(context, include_current_day=True)
        
        print("GAME HISTORY (XML format):")
        print("-" * 80)
        print(xml_history)
        print("-" * 80)
        print()
        
        # Also show some context stats
        print(f"Context Stats:")
        print(f"  - Total events in history: {len(context.public_history)}")
        print(f"  - Speeches: {sum(1 for e in context.public_history if e.get('type') == 'speech')}")
        print(f"  - Nominations: {sum(1 for e in context.public_history if e.get('type') == 'nomination')}")
        print(f"  - Votes: {sum(1 for e in context.public_history if e.get('type') == 'votes')}")
        print(f"  - Eliminations: {sum(1 for e in context.public_history if e.get('type') == 'elimination')}")
        print(f"  - Night kills: {len([k for k in game_state.night_kills.values() if k is not None])}")
        print()
    
    # Final summary
    print("\n" + "=" * 80)
    print("FINAL GAME STATE")
    print("=" * 80)
    print(f"Phase: {game_state.phase.value}")
    print(f"Day: {game_state.day_number}")
    print(f"Night: {game_state.night_number}")
    print(f"Alive players: {[p.player_number for p in game_state.get_alive_players()]}")
    if game_state.winner:
        print(f"Winner: {game_state.winner.value}")
    print("=" * 80)


if __name__ == "__main__":
    simulate_game_and_show_context()

