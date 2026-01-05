# Mafia Game Simulation

A text-based Mafia game simulation where LLM agents play the classic social deduction game.

## Game Overview

- **10 Players**: 7 Civilians (1 Sheriff) vs 3 Mafia (1 Don)
- **Phases**: Alternating Day (discussion/voting) and Night (secret actions)
- **Win Conditions**: 
  - Red Team (Civilians) wins when all Mafia are eliminated
  - Black Team (Mafia) wins when numbers are equal or Mafia outnumber Civilians

## Project Structure

```
mafia-battle/
├── src/
│   ├── __init__.py
│   ├── core/               # Core game engine components
│   │   ├── __init__.py
│   │   ├── game_engine.py  # Game state and phase management
│   │   ├── judge.py        # Rule enforcement and moderation
│   │   ├── player.py       # Player model and status
│   │   └── roles.py        # Role definitions and abilities
│   ├── agents/             # Agent implementations
│   │   ├── __init__.py
│   │   └── llm_agent.py    # LLM agent framework and implementation
│   ├── config/             # Configuration
│   │   ├── __init__.py
│   │   └── game_config.py  # Game configuration and constants
│   └── phases/             # Phase handlers
│       ├── __init__.py
│       ├── day_phase.py    # Day phase handler
│       ├── night_phase.py  # Night phase handler (kills, checks)
│       └── voting.py       # Voting system and nominations
├── tests/                  # Test suite
├── GAME_SPECIFICATION.md   # Complete game rules specification
├── requirements.txt        # Python dependencies
└── main.py                # Entry point for running games
```

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables (create `.env` file):
```
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here  # Optional
```

3. Run a game:
```bash
python main.py
```

4. View game runs in browser:
```bash
# In a separate terminal, start the viewer server
python viewer.py

# Then open http://127.0.0.1:5000 in your browser
```

## Configuration

Key configurable parameters in `src/config/game_config.py`:
- **LLM limits**: Optional `max_speech_tokens`, `tie_break_speech_tokens`, and `max_action_tokens` (no limits by default)
- **LLM settings**: `llm_model`, `llm_temperature`
- **Timing**: Optional `night_action_timeout`, `voting_window` (no time limits by default)
- **Game limits**: `max_rounds` (maximum day/night cycles)
- **Logging**: `log_level`

## Game Runs and Viewer

Games are automatically saved to the `runs/` folder:
- Each game creates a unique run folder (e.g., `runs/run_20241126_011430/`)
- Events are saved to `events.jsonl` (JSON Lines format)
- Metadata is saved to `metadata.json`
- Use the viewer server to browse and view runs in the browser

### Running the Viewer

Start the viewer server in a separate terminal:
```bash
python viewer.py
# Or with custom port: python viewer.py --port 8080
```

Then open http://127.0.0.1:5000 in your browser to:
- Browse all game runs
- Select a run to view
- See real-time updates if the game is still running
- View LLM metadata (token counts, latency)

## Recent Changes

- **File-based event system**: 
  - Games save events to `runs/` folder
  - Separate viewer server for browsing runs
  - No WebSocket dependency in main game
- **Refactored structure**: 
  - Core engine logic moved to `src/core/`
  - Agent implementations moved to `src/agents/`
  - Phase handlers moved to `src/phases/`
- **Game flow**: Game now starts with DAY 1, followed by NIGHT 1, then alternating
- **Round limiting**: Added `max_rounds` parameter to prevent infinite games
- **Output formatting**: Improved player speech formatting (`[Player X]` vs `[JUDGE]` announcements)
- **Game summary**: Enhanced end-game summary with detailed player information

