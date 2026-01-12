# Configuration Files

This directory contains example YAML configuration files for running Mafia game simulations.

## Available Configurations

### `dummy_agent.yaml`
Uses the `DummyAgent` which has deterministic behavior:
- All players say "I am Player X. Let me analyze the situation. PASS"
- Sheriff checks random alive players (not itself) who haven't been checked before
- Mafia kills random civilian players
- Don checks random civilian players who haven't been checked before

**Usage:**
```bash
python main.py --config configs/dummy_agent.yaml
```

### `simple_llm_agent.yaml`
Uses the `SimpleLLMAgent` for all players with strategic LLM-based decision making.

**Usage:**
```bash
python main.py --config configs/simple_llm_agent.yaml
python main.py --config configs/simple_llm_agent.yaml --model gpt-4o-mini  # Override model
```

### `mixed_agents.yaml`
Uses a mix of 2 LLM agents (players 1 and 2) and 8 dummy agents (players 3-10). This speeds up gameplay significantly while still having some strategic LLM behavior.

**Usage:**
```bash
python main.py --config configs/mixed_agents.yaml
python main.py --config configs/mixed_agents.yaml --model gpt-4o-mini  # Override model for LLM agents
```

## Configuration Options

All configuration files support the following options:

### Agent Settings
- `agent_type`: Either `"dummy_agent"` or `"simple_llm_agent"` (default for all players if `agent_types` not specified)
- `agent_types`: Optional dictionary mapping player numbers to agent types (e.g., `{1: "simple_llm_agent", 2: "simple_llm_agent"}`). Allows mixing agent types.

### Game Settings
- `total_players`: Number of players in the game (default: 10)
- `max_rounds`: Maximum number of day/night cycles before game ends (default: 10)
- `log_level`: Logging level (default: "INFO")

### LLM Settings
- `llm_model`: LLM model name (default: "gpt-4")
- `llm_temperature`: LLM temperature (default: 0.7)
- `reasoning_effort`: Optional reasoning effort for gpt-5 models (`"low"`, `"medium"`, `"high"`)
- `max_retries`: Maximum retries for LLM calls (default: 3)

### Judge Settings
- `use_judge_announcements`: Whether to use judge announcements (default: true)

## Creating Custom Configurations

You can create your own configuration files by copying one of the example files and modifying the values. Any missing values will use the defaults from `GameConfig`.

**Example:**
```bash
cp configs/dummy_agent.yaml configs/my_custom_config.yaml
# Edit my_custom_config.yaml with your preferred settings
python main.py --config configs/my_custom_config.yaml
```
