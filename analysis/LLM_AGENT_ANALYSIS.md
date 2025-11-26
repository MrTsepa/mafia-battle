# LLM Agent Behavior Analysis

## Overview

The `SimpleLLMAgent` is a strategic agent implementation that uses OpenAI's API to make intelligent decisions in the Mafia game. Unlike random agents, it analyzes game patterns, voting behavior, and strategic information to make informed choices.

## Architecture

### Core Components

1. **Base Agent Interface** (`BaseAgent`)
   - Defines the interface: `get_day_speech()`, `get_night_action()`, `get_vote_choice()`
   - Provides context building with `build_context()` method
   - Extracts public history and private information

2. **LLM Integration** (`SimpleLLMAgent`)
   - Uses OpenAI API for decision-making
   - Builds strategic prompts based on game state
   - Tracks game patterns and suspicious behavior
   - Has fallback mechanisms when LLM calls fail

## Key Features

### 1. Strategic State Tracking

The agent maintains several data structures to track game patterns:

```python
self.checked_players: set[int]  # Players checked by sheriff/don
self.suspicious_players: set[int]  # Players flagged as suspicious
self.trusted_players: set[int]  # Players we trust
self.voting_patterns: Dict[int, List[int]]  # Voting history per player
self.speech_analysis: Dict[int, List[str]]  # Speech history per player
```

### 2. Pattern Analysis

The agent analyzes voting patterns to identify:
- **Suspicious voters**: Players who voted for eliminated civilians
- **Coordinated votes**: Players who consistently vote together (possible mafia)
- **Hidden players**: Players rarely nominated (possible mafia hiding)

### 3. Role-Specific Strategies

#### Sheriff Strategy
- Checks suspicious players (those who voted for eliminated civilians)
- Checks players who avoid nominations
- Uses check results to build trust/distrust lists
- Avoids revealing role in speeches

#### Mafia Strategy
- Targets active players (potential sheriff or leaders)
- Coordinates with known mafia team members
- Avoids drawing attention
- Uses kill claims to coordinate

#### Don Strategy
- Checks players to find the Sheriff
- Prioritizes checking active/leading players
- Makes final kill decisions based on team claims
- Uses check results to identify threats

## Decision-Making Process

### Day Phase: Speech Generation

1. **Build Strategic Prompt** (`build_strategic_prompt()`)
   - Includes role, team, and game rules
   - Adds role-specific strategic information
   - Includes current game state (alive players, phase, day/night numbers)
   - Adds voting pattern analysis
   - Includes recent game history (last 15 events)
   - Provides instructions for speech generation

2. **Call LLM** (`_call_llm()`)
   - Sends prompt to OpenAI API
   - Uses configured model (default: `gpt-5-mini`)
   - Handles different API parameter formats for different models

3. **Process Response**
   - Ensures speech ends with "PASS" or "THANK YOU"
   - Token limits enforced by LLM call (`max_speech_tokens`, default: 400)
   - Falls back to basic speech if LLM fails

### Night Phase: Actions

#### Sheriff Check
1. Builds prompt with:
   - Check results from previous nights
   - List of suspicious players
   - Players already checked
   - Strategic guidance

2. Extracts player number from LLM response
3. Validates target is alive and not self
4. Falls back to checking suspicious players if LLM fails

#### Mafia Kill Claim
1. Builds prompt with:
   - Known mafia team members
   - Active players to target
   - Strategic guidance

2. Extracts target from response
3. Falls back to targeting active civilians if LLM fails

#### Don Check & Kill Decision
1. **Check**: Similar to sheriff, but checks for Sheriff identity
2. **Kill Decision**: 
   - Receives kill claims from team
   - Chooses final target based on claims and strategy
   - Falls back to first claim or random civilian

### Voting Phase: Vote Choice

1. Builds prompt with:
   - Nominated players
   - Voting pattern analysis
   - Suspicious players
   - Strategic guidance

2. Extracts player number from response
3. Validates target is in nominations
4. Falls back to voting for suspicious nominated players

## Prompt Engineering

The agent uses sophisticated prompt engineering to guide the LLM:

### Prompt Structure

```
1. Role & Team Information
2. Game Rules
3. Role-Specific Strategy
4. Current Game State
5. Alive Players (with suspicious/trusted markers)
6. Voting Pattern Analysis
7. Recent Game History
8. Phase-Specific Instructions
```

### Example Prompt Components

**For Sheriff Check:**
```
SHERIFF ABILITIES:
- Check one player per night to see if they are Red (civilian) or Black (mafia)
- Your check results:
  Night 1: Player 3 is Red
  Night 2: Player 5 is Black

SHERIFF STRATEGY:
- Check suspicious players (those who voted for eliminated civilians)
- Check players who avoid nominations or seem to be hiding
- Don't check randomly - use information from voting patterns
```

**For Mafia Kill:**
```
MAFIA TEAM: You know these players are mafia: [2, 7, 9]
STRATEGY:
- Target active players who might be sheriff or leading civilians
- Coordinate with your team (you know who they are)
- Avoid drawing attention to yourself
```

## Fallback Mechanisms

The agent has multiple fallback layers:

1. **LLM Call Failure**: Falls back to rule-based strategy
2. **Invalid Response**: Extracts numbers from text, validates against game state
3. **No Valid Target**: Uses pattern-based heuristics (suspicious players, active players)
4. **Final Fallback**: Random selection from valid options

## API Integration

### Model Support
- **gpt-5-mini**: Uses `max_completion_tokens`, default temperature
- **gpt-4o**: Uses `max_completion_tokens`
- **Older models**: Uses `max_tokens`

### Error Handling
- Catches API exceptions
- Prints warnings but continues with fallback
- Allows initialization without API key in test environments

## Strategic Improvements Over Random Agents

1. **Pattern Recognition**: Analyzes voting patterns to identify mafia
2. **Information Tracking**: Remembers check results and suspicious behavior
3. **Role Awareness**: Uses role-specific abilities strategically
4. **Early Game Focus**: Recognizes games end in 2-4 rounds
5. **Coordination**: Mafia team coordinates kills
6. **Threat Assessment**: Targets active players and potential threats

## Testing

The `test_llm_agent.py` file provides comprehensive testing:
- Initialization with API key validation
- Speech generation
- Night actions (sheriff, mafia, don)
- Vote choices
- Full game simulation

## Configuration

Key configuration options in `simple_llm_agent.yaml`:
- `llm_model`: OpenAI model to use (default: `gpt-5-mini`)
- `llm_temperature`: Response randomness (default: 0.7)
- `max_speech_tokens`: Maximum tokens for LLM (default: 400)

## Usage Example

```python
from src.agents import SimpleLLMAgent
from src.config.config_loader import load_config

# Load configuration
config = load_config("configs/simple_llm_agent.yaml")

# Create agent for a player
agent = SimpleLLMAgent(player, config)

# Build context
context = agent.build_context(game_state)

# Get actions
speech = agent.get_day_speech(context)
action = agent.get_night_action(context)
vote = agent.get_vote_choice(context)
```

## Limitations & Considerations

1. **API Costs**: Each decision requires an API call
2. **Latency**: LLM calls add delay to game execution
3. **Token Limits**: Prompts are truncated to fit token limits
4. **Response Parsing**: Must extract structured data from free-form text
5. **Fallback Dependency**: Relies on fallback mechanisms for reliability

## Execution Flow

### Day Phase Flow

```
Game Engine → DayPhaseHandler.run_day_phase()
    ↓
For each player in speaking order:
    ↓
    agent.build_context(game_state)
        ↓
        Creates AgentContext with:
        - Current player
        - Game state
        - Public history (speeches, votes, eliminations)
        - Private info (role-specific)
        - Current phase
        - Available actions
    ↓
    agent.get_day_speech(context)
        ↓
        build_strategic_prompt(context, "speech")
            ↓
            - Adds role/team info
            - Adds game rules
            - Adds role-specific strategy
            - Adds current game state
            - Adds voting pattern analysis
            - Adds recent history
            - Adds speech instructions
        ↓
        _call_llm(prompt, max_tokens=300)
            ↓
            OpenAI API call
            ↓
            Response text
        ↓
        Process response:
        - Ensure ends with "PASS" or "THANK YOU"
        - Token limits enforced by LLM call
        - Extract nominations if any
    ↓
    Return speech to game engine
```

### Night Phase Flow

```
Game Engine → NightPhaseHandler.run_night_phase()
    ↓
1. Sheriff Check Phase (first, so sheriff can check even if killed):
    ↓
    agent.get_night_action(context)
        ↓
        build_strategic_prompt(context, "sheriff_check")
        ↓
        _call_llm(prompt, max_tokens=50)
        ↓
        _extract_player_number(response)
        ↓
        Return action: {"type": "sheriff_check", "target": X}
    ↓
    
2. Mafia Kill Phase:
    ↓
    For each mafia player:
        ↓
        agent.build_context(game_state)
        ↓
        agent.get_night_action(context)
            ↓
            Check if kill_decision_call:
                - Don eliminated?
                - kill_claims structure?
            ↓
            If normal mafia:
                build_strategic_prompt(context, "kill_claim")
                ↓
                _call_llm(prompt, max_tokens=50)
                ↓
                _extract_player_number(response)
                ↓
                Fallback if invalid
            ↓
            Return action: {"type": "kill_claim", "target": X}
        ↓
    Collect all kill_claims
    ↓
    Don (or mafia if Don eliminated) makes decision:
        ↓
        agent.get_night_action(context) [kill_decision_call]
            ↓
            build_strategic_prompt(context, "kill_decision")
                - Shows all kill_claims from team
                - Strategic guidance
            ↓
            _call_llm(prompt, max_tokens=50)
            ↓
            _extract_player_number(response)
            ↓
            Return action: {"type": "kill_decision", "kill_decision": X}
    ↓
    Execute kill
    
3. Don Check Phase:
    ↓
    agent.get_night_action(context)
        ↓
        build_strategic_prompt(context, "don_check")
        ↓
        _call_llm(prompt, max_tokens=50)
        ↓
        _extract_player_number(response)
        ↓
        Return action: {"type": "don_check", "target": X}
```

### Voting Phase Flow

```
Game Engine → VotingHandler.run_voting_phase()
    ↓
For each alive player:
    ↓
    agent.build_context(game_state)
    ↓
    agent.get_vote_choice(context)
        ↓
        build_strategic_prompt(context, "vote")
            - Shows nominations
            - Voting pattern analysis
            - Suspicious players
        ↓
        _call_llm(prompt, max_tokens=50)
        ↓
        _extract_player_number(response)
        ↓
        Validate target is in nominations
        ↓
        Fallback to suspicious nominated players
    ↓
    Return vote choice
```

## Example Prompts

### Example 1: Sheriff Check Prompt (Night 2)

```
You are Player 1, a sheriff on the Red team.

GAME RULES:
- Red Team (Civilians) wins when all Mafia are eliminated
- Black Team (Mafia) wins when numbers are equal or Mafia outnumber Civilians
- Roles are NOT revealed when players are eliminated
- Games typically end in 2-4 rounds, so early decisions are critical
- Night kills account for ~50% of eliminations - they are very powerful

SHERIFF ABILITIES:
- Check one player per night to see if they are Red (civilian) or Black (mafia)
- Your check results:
  Night 1: Player 3 is Red

SHERIFF STRATEGY:
- Check suspicious players (those who voted for eliminated civilians)
- Check players who avoid nominations or seem to be hiding
- Don't check randomly - use information from voting patterns

CURRENT PHASE: night
DAY: 1, NIGHT: 2
ALIVE: 9 players (3 mafia, 6 civilians)

ALIVE PLAYERS:
  Player 1
  Player 2 [SUSPICIOUS]
  Player 3 [TRUSTED]
  Player 4
  Player 5
  Player 6
  Player 7 [SUSPICIOUS]
  Player 8
  Player 9

RECENT GAME HISTORY:
  Day 1: Player 2 said: I think we should vote out Player 5, they seem suspicious...
  Day 1: Player 5 was nominated
  Player 5 was eliminated (voting)
  Day 1: 8 votes cast

SHERIFF CHECK:
- Check one player to see if they are Red (civilian) or Black (mafia)
- Players already checked: [3]
- Prioritize checking suspicious players
- Return ONLY the player number (e.g., '5' or 'Player 5')
```

### Example 2: Mafia Kill Claim Prompt (Night 1)

```
You are Player 2, a mafia on the Black team.

GAME RULES:
- Red Team (Civilians) wins when all Mafia are eliminated
- Black Team (Mafia) wins when numbers are equal or Mafia outnumber Civilians
- Roles are NOT revealed when players are eliminated
- Games typically end in 2-4 rounds, so early decisions are critical
- Night kills account for ~50% of eliminations - they are very powerful

MAFIA TEAM: You know these players are mafia: [2, 7, 9]
STRATEGY:
- Target active players who might be sheriff or leading civilians
- Coordinate with your team (you know who they are)
- Avoid drawing attention to yourself

CURRENT PHASE: night
DAY: 1, NIGHT: 1
ALIVE: 10 players (3 mafia, 7 civilians)

ALIVE PLAYERS:
  Player 1
  Player 2
  Player 3
  Player 4
  Player 5
  Player 6
  Player 7
  Player 8
  Player 9
  Player 10

RECENT GAME HISTORY:
  Day 1: Player 1 said: Let's analyze the situation carefully...
  Day 1: Player 3 said: I nominate player number 5...
  Day 1: Player 5 was nominated

MAFIA KILL CLAIM:
- Suggest who should be killed tonight
- Target active players, potential sheriff, or threats
- Return ONLY the player number (e.g., '5' or 'Player 5')
```

### Example 3: Day Speech Prompt (Day 2)

```
You are Player 1, a sheriff on the Red team.

GAME RULES:
- Red Team (Civilians) wins when all Mafia are eliminated
- Black Team (Mafia) wins when numbers are equal or Mafia outnumber Civilians
- Roles are NOT revealed when players are eliminated
- Games typically end in 2-4 rounds, so early decisions are critical
- Night kills account for ~50% of eliminations - they are very powerful

SHERIFF ABILITIES:
- Check one player per night to see if they are Red (civilian) or Black (mafia)
- Your check results:
  Night 1: Player 3 is Red
  Night 2: Player 7 is Black

SHERIFF STRATEGY:
- Check suspicious players (those who voted for eliminated civilians)
- Check players who avoid nominations or seem to be hiding
- Don't check randomly - use information from voting patterns

CURRENT PHASE: day
DAY: 2, NIGHT: 2
ALIVE: 8 players (3 mafia, 5 civilians)

ALIVE PLAYERS:
  Player 1
  Player 2 [SUSPICIOUS]
  Player 3 [TRUSTED]
  Player 4
  Player 6
  Player 7 [SUSPICIOUS]
  Player 8
  Player 9

SUSPICIOUS PLAYERS (based on voting patterns):
  Player 2
  Player 7

COORDINATED VOTING PATTERNS (possible mafia):
  Players 2 and 7 voted together multiple times

RECENT GAME HISTORY:
  Day 1: Player 2 said: I think we should vote out Player 5...
  Day 1: Player 5 was nominated
  Player 5 was eliminated (voting)
  Day 1: 8 votes cast
  Player 4 was eliminated (night kill)

YOUR TURN TO SPEAK:
- You have up to 200 words
- You can nominate a player by saying 'I nominate player number X'
- End your speech with 'PASS' or 'THANK YOU'
- Analyze voting patterns and suspicious behavior
- If you're sheriff, be careful not to reveal your role
- Coordinate with your team if possible
- Current nominations: []

Generate your strategic speech:
```

## Code Examples

### Example: Sheriff Check Decision

```python
# In get_night_action() method
if self.player.role.role_type == RoleType.SHERIFF:
    prompt = self.build_strategic_prompt(context, "sheriff_check")
    # Prompt includes:
    # - "You are Player X, a Sheriff on the Red team"
    # - "SHERIFF ABILITIES: Check one player per night..."
    # - "Your check results: Night 1: Player 3 is Red"
    # - "SUSPICIOUS PLAYERS: Player 5, Player 7"
    # - "Players already checked: [3]"
    
    response = self._call_llm(prompt, max_tokens=50)
    # Response might be: "I should check Player 5" or just "5"
    
    target = self._extract_player_number(response, context)
    # Extracts: 5
    
    if target and target != self.player.player_number:
        action["type"] = "sheriff_check"
        action["target"] = target
        self.checked_players.add(target)
```

### Example: Pattern Analysis

```python
# In _identify_suspicious_players()
# Finds players who voted for eliminated civilians
for action in context.game_state.action_log:
    if action.get("type") == "player_eliminated":
        eliminated = action.get("data", {}).get("player")
        day = action.get("data", {}).get("day_number")
        if day and eliminated:
            votes = context.game_state.votes.get(day, {})
            for voter, target in votes.items():
                if target == eliminated:
                    eliminated_player = context.game_state.get_player(eliminated)
                    if eliminated_player and eliminated_player.is_civilian:
                        suspicious.add(voter)  # Voter is suspicious!
```

## Future Improvements

Potential enhancements:
- Caching LLM responses for similar game states
- Fine-tuning prompts based on game outcomes
- Multi-turn reasoning for complex decisions
- Better response parsing with structured outputs
- Local LLM support to reduce API costs

