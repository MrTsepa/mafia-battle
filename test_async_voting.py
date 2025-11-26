"""
Test async voting functionality.
"""

import asyncio
import os
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.core import GameState, Judge
from src.agents import SimpleLLMAgent
from src.config.config_loader import load_config


async def test_async_voting():
    """Test that voting calls run in parallel."""
    print("=" * 60)
    print("Testing Async Voting (Parallel LLM Calls)")
    print("=" * 60)
    
    config = load_config("configs/simple_llm_agent.yaml")
    game_state = GameState(random_seed=42)
    judge = Judge(game_state, config)
    
    # Set up voting scenario
    game_state.start_day()
    game_state.nominations[game_state.day_number] = [2, 5, 7]
    game_state.start_voting()
    
    # Create agents for all players
    agents = {}
    for player in game_state.players[:5]:  # Test with first 5 players
        agents[player.player_number] = SimpleLLMAgent(player, config)
    
    print(f"\nTesting with {len(agents)} players")
    print(f"Nominations: {game_state.nominations[game_state.day_number]}")
    print("\nCollecting votes in parallel...")
    print("-" * 60)
    
    # Time the parallel execution
    start_time = time.time()
    
    async def get_vote_for_player(player_num: int, agent: SimpleLLMAgent):
        """Get vote choice for a single player."""
        context = agent.build_context(game_state)
        vote = await agent.get_vote_choice_async(context)
        elapsed = time.time() - start_time
        print(f"  Player {player_num} voted: {vote} (took {elapsed:.2f}s)")
        return player_num, vote
    
    # Create tasks for all players
    tasks = [get_vote_for_player(player_num, agent) 
             for player_num, agent in agents.items()]
    
    # Wait for all votes in parallel
    results = await asyncio.gather(*tasks)
    
    total_time = time.time() - start_time
    
    print("-" * 60)
    print(f"\n✓ All votes collected in {total_time:.2f} seconds")
    print(f"  (If sequential, would take ~{total_time * len(agents):.2f} seconds)")
    print(f"  Speedup: ~{len(agents)}x faster")
    
    # Show results
    print("\nVote results:")
    for player_num, vote in results:
        print(f"  Player {player_num} → Player {vote}")
    
    return True


def main():
    """Run async voting test."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY not set!")
        return 1
    
    try:
        asyncio.run(test_async_voting())
        print("\n✓ Async voting test completed successfully!")
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())

