"""
Script to run dummy agent multiple times and analyze results.
"""

import sys
from collections import defaultdict
from typing import List, Dict, Any

from src.core import GameState, GamePhase, Judge, Player
from src.agents import DummyAgent
from src.phases import DayPhaseHandler, VotingHandler, NightPhaseHandler
from src.config.game_config import default_config
from src.config.config_loader import load_config
from main import MafiaGame


def run_multiple_games(config_path: str, num_games: int = 20) -> List[Dict[str, Any]]:
    """
    Run multiple games and collect results.
    
    Args:
        config_path: Path to config file
        num_games: Number of games to run
        
    Returns:
        List of game summary dictionaries
    """
    results = []
    
    print(f"Running {num_games} games with dummy agent...")
    print("=" * 60)
    
    for i in range(num_games):
        print(f"\n[Game {i+1}/{num_games}]")
        print("-" * 60)
        
        # Load config
        config = load_config(config_path)
        # Don't set seed so each game is different
        config.random_seed = None
        
        # Run game (suppress output)
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            game = MafiaGame(config=config)
            winner = game.run_game()
        
        # Get summary
        summary = game.get_game_summary()
        summary["winner_name"] = winner
        
        # Extract additional stats
        game_state = game.game_state
        summary["final_alive_count"] = len(game_state.get_alive_players())
        summary["final_mafia_count"] = len(game_state.get_mafia_players())
        summary["final_civilian_count"] = len(game_state.get_civilian_players())
        summary["total_eliminations"] = len([p for p in game_state.players if not p.is_alive])
        
        # Count eliminations by type
        eliminations_by_type = defaultdict(int)
        for action in game_state.action_log:
            if action.get("type") == "player_eliminated":
                reason = action.get("data", {}).get("reason", "unknown")
                eliminations_by_type[reason] += 1
        
        summary["eliminations_by_type"] = dict(eliminations_by_type)
        
        results.append(summary)
        
        # Print brief summary
        winner_short = "Mafia" if summary["winner"] == "black" else "Civilians"
        print(f"Winner: {winner_short} | Rounds: {summary['rounds']} | Nights: {summary['nights']}")
    
    return results


def analyze_results(results: List[Dict[str, Any]]) -> None:
    """
    Analyze and print statistics from game results.
    
    Args:
        results: List of game summary dictionaries
    """
    print("\n" + "=" * 60)
    print("ANALYSIS RESULTS")
    print("=" * 60)
    
    # Basic counts
    total_games = len(results)
    mafia_wins = sum(1 for r in results if r["winner"] == "black")
    civilian_wins = sum(1 for r in results if r["winner"] == "red")
    draws = sum(1 for r in results if r["winner"] is None)
    
    print(f"\n📊 WIN STATISTICS")
    print("-" * 60)
    print(f"Total Games: {total_games}")
    print(f"Mafia Wins: {mafia_wins} ({mafia_wins/total_games*100:.1f}%)")
    print(f"Civilian Wins: {civilian_wins} ({civilian_wins/total_games*100:.1f}%)")
    print(f"Draws: {draws} ({draws/total_games*100:.1f}%)")
    
    # Game length statistics
    rounds = [r["rounds"] for r in results]
    nights = [r["nights"] for r in results]
    
    print(f"\n⏱️  GAME LENGTH STATISTICS")
    print("-" * 60)
    print(f"Rounds (Days):")
    print(f"  Average: {sum(rounds)/len(rounds):.2f}")
    print(f"  Min: {min(rounds)}")
    print(f"  Max: {max(rounds)}")
    print(f"  Median: {sorted(rounds)[len(rounds)//2]}")
    print(f"\nNights:")
    print(f"  Average: {sum(nights)/len(nights):.2f}")
    print(f"  Min: {min(nights)}")
    print(f"  Max: {max(nights)}")
    print(f"  Median: {sorted(nights)[len(nights)//2]}")
    
    # Winner-specific statistics
    mafia_win_games = [r for r in results if r["winner"] == "black"]
    civilian_win_games = [r for r in results if r["winner"] == "red"]
    
    if mafia_win_games:
        mafia_rounds = [r["rounds"] for r in mafia_win_games]
        print(f"\n🎯 MAFIA WINS (n={len(mafia_win_games)})")
        print("-" * 60)
        print(f"  Average Rounds: {sum(mafia_rounds)/len(mafia_rounds):.2f}")
        print(f"  Average Nights: {sum(r['nights'] for r in mafia_win_games)/len(mafia_win_games):.2f}")
        print(f"  Average Final Mafia Count: {sum(r['final_mafia_count'] for r in mafia_win_games)/len(mafia_win_games):.2f}")
        print(f"  Average Final Civilian Count: {sum(r['final_civilian_count'] for r in mafia_win_games)/len(mafia_win_games):.2f}")
    
    if civilian_win_games:
        civilian_rounds = [r["rounds"] for r in civilian_win_games]
        print(f"\n🛡️  CIVILIAN WINS (n={len(civilian_win_games)})")
        print("-" * 60)
        print(f"  Average Rounds: {sum(civilian_rounds)/len(civilian_rounds):.2f}")
        print(f"  Average Nights: {sum(r['nights'] for r in civilian_win_games)/len(civilian_win_games):.2f}")
        print(f"  Average Final Mafia Count: {sum(r['final_mafia_count'] for r in civilian_win_games)/len(civilian_win_games):.2f}")
        print(f"  Average Final Civilian Count: {sum(r['final_civilian_count'] for r in civilian_win_games)/len(civilian_win_games):.2f}")
    
    # Elimination statistics
    total_eliminations = sum(r["total_eliminations"] for r in results)
    eliminations_by_type_all = defaultdict(int)
    for r in results:
        for elim_type, count in r.get("eliminations_by_type", {}).items():
            eliminations_by_type_all[elim_type] += count
    
    print(f"\n💀 ELIMINATION STATISTICS")
    print("-" * 60)
    print(f"Total Eliminations: {total_eliminations}")
    print(f"Average Eliminations per Game: {total_eliminations/total_games:.2f}")
    print(f"\nEliminations by Type:")
    for elim_type, count in sorted(eliminations_by_type_all.items()):
        print(f"  {elim_type}: {count} ({count/total_eliminations*100:.1f}%)")
    
    # Distribution of rounds
    print(f"\n📈 ROUND DISTRIBUTION")
    print("-" * 60)
    round_dist = defaultdict(int)
    for r in rounds:
        round_dist[r] += 1
    for round_num in sorted(round_dist.keys()):
        count = round_dist[round_num]
        bar = "█" * (count * 50 // total_games)
        print(f"  {round_num:2d} rounds: {count:3d} games {bar}")
    
    # Early vs late game wins
    early_wins = sum(1 for r in results if r["rounds"] <= 3)
    mid_wins = sum(1 for r in results if 3 < r["rounds"] <= 6)
    late_wins = sum(1 for r in results if r["rounds"] > 6)
    
    print(f"\n⏰ GAME TIMING")
    print("-" * 60)
    print(f"Early Wins (≤3 rounds): {early_wins} ({early_wins/total_games*100:.1f}%)")
    print(f"Mid Wins (4-6 rounds): {mid_wins} ({mid_wins/total_games*100:.1f}%)")
    print(f"Late Wins (>6 rounds): {late_wins} ({late_wins/total_games*100:.1f}%)")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Run multiple games and analyze results"
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default="configs/dummy_agent.yaml",
        help="Path to config file (default: configs/dummy_agent.yaml)"
    )
    parser.add_argument(
        "--num-games",
        "-n",
        type=int,
        default=20,
        help="Number of games to run (default: 20)"
    )
    
    args = parser.parse_args()
    
    # Run games
    results = run_multiple_games(args.config, args.num_games)
    
    # Analyze
    analyze_results(results)
    
    print("\n" + "=" * 60)
    print("Analysis complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()

