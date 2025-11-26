# Mafia Game Rules Analysis

## Executive Summary

This document provides a comprehensive analysis of the Official 2025 Mafia Rules for creating an LLM-based simulation. The game is a 10-player social deduction game with two teams competing through alternating day and night phases.


## 1. Core Game Structure

### 1.1 Player Composition
- **Total Players**: 10
- **Red Team (Civilians)**: 7 players
  - 6 Regular Civilians
  - 1 Sheriff (special role with investigation ability)
- **Black Team (Mafia)**: 3 players
  - 2 Regular Mafia
  - 1 Don (special role with Sheriff detection ability)

### 1.2 Win Conditions
- **Red Team Wins**: When all black team players are eliminated
- **Black Team Wins**: When the number of players remaining is equal for both teams OR when there are more black than red players remaining

### 1.3 Game Phases
The game alternates between:
1. **Night Phase**: Secret actions (mafia kills, role abilities)
2. **Day Phase**: Public discussion, nominations, and voting

---

## 2. Game Flow Breakdown

### 2.1 Game Start (Section 4.1)
- Players randomly assigned numbers (1-10)
- Judge assigns roles randomly
- Players receive their role information
- **Game Engine provides mafia players with knowledge of all mafia identities**
- Judge announces: **"Night falls."**

### 2.3 Day Phase (Section 4.3)
**Structure:**
- Judge announces: **"Morning has come (in the city)"**
- **Discussion Phase**: Each player gets a speech turn
  - Must speak in turn order (by player number)
  - First day: Player 1 starts
  - Subsequent days: Next player after previous day's starter
  - Must refer to others by player number only
  - Must end speech with **"PASS"** or **"THANK YOU"**
  - **Speech length limit**: Maximum tokens/words per speech (configurable, e.g., 200 words or 300 tokens)
  
**Nominations:**
- Each player may nominate **only one** candidate per day
- Use phrases: "I nominate player number X" / "I nominate number X" / "Nominating number X"
- Nominations **cannot be withdrawn**
- If multiple nominations in one speech, only first un-nominated candidate accepted

### 2.4 Voting Phase (Section 4.4)
**Process:**
- Only nominated players can be voted on
- Judge announces nominated players **twice** before voting
- Voting occurs in nomination order
- Judge calls: **"Five, who votes against player number five?"**
- **Voting window: 1.5 seconds**
- Players submit their vote choice
- **One vote per round**
- **Default vote**: If player doesn't vote, vote automatically assigned to **last nominated player**

**Elimination Rules:**
- Player with **most votes** is eliminated
- **Role is NOT revealed** upon elimination
- Eliminated player gets a **final speech** (same token/word limit as regular speeches)
- **Tie-breaking**: 
  - Tied players get **additional speeches** (shorter limit, e.g., 100 words or 150 tokens), then revote
  - If same tie persists: Vote to eliminate all tied players or keep all
  - If vote splits evenly: All tied players remain

**Special Cases:**
- **First day**: If only one nomination, no vote occurs
- **Subsequent days**: If only one nomination, that player automatically eliminated (unanimous)

### 2.5 Night Phase (Section 4.5)
**Sequence (applies to ALL nights, including first night):**

1. **Sheriff Check** (every night, including first night):
   - Judge: **"The Sheriff wakes up, you have ten seconds."**
   - Sheriff selects number of player to check
   - Judge responds with:
     - **"Red"** = Civilian
     - **"Black"** = Mafia
   - Judge: **"The Sheriff goes to sleep."**
   - *Note: Sheriff checks first so they can check even if they are killed this night*

2. **Mafia Kill**:
   - Judge: **"The mafia goes hunting."**
   - All mafia players "wake up" and each actor makes a claim about who they think should be killed
   - Don decides who to kill and returns one number to the judge
   - If Don provides a valid target: Player eliminated (role not revealed, gets final speech)

3. **Don Check** (every night, including first night):
   - Judge: **"The Don wakes up, you have ten seconds."**
   - Don selects number of suspected Sheriff
   - Judge responds with:
     - **"Sheriff"** if correct
     - **"Not the Sheriff"** if incorrect
   - Judge: **"The Don goes to sleep."**

**Night Conduct Rules:**
- **Complete silence**: No communication during night phase
- **Forbidden**: Any form of communication, coordination, or information sharing
- **Violations**: Can result in disqualification or team loss

---

## 3. Role Abilities

### 3.1 Sheriff (Red Team)
- **Ability**: Check one player per night to learn if they are red (civilian) or black (mafia)
- **Timing**: First, before mafia kill, every night (including first night)
- **Information**: Receives "Red" (civilian) or "Black" (mafia)
- **Note**: Sheriff checks first so they can check even if they are killed this night

### 3.2 Don (Black Team)
- **Ability**: Check one player per night to learn if they are the Sheriff
- **Timing**: After mafia kill, every night (including first night)
- **Information**: Receives "Sheriff" or "Not the Sheriff"
- **Mafia Knowledge**: Knows all mafia identities (provided by game engine from start)

### 3.3 Regular Mafia (Black Team)
- **Ability**: Participate in mafia kills by making claims about who should be killed
- **Mafia Knowledge**: Knows all mafia identities (provided by game engine from start)
- **Night Action**: Wakes up every night to make a claim about kill target (Don makes final decision)

### 3.4 Regular Civilians (Red Team)
- **No special abilities**
- Must deduce mafia through discussion and voting

---

## 4. Key Game Mechanics for Simulation

### 4.1 Information Asymmetry
- **Mafia knows**: All mafia identities (provided by game engine from game start)
- **Sheriff knows**: Results of their checks (red/black)
- **Don knows**: Results of their checks (Sheriff/not Sheriff), all mafia identities
- **Civilians know**: Only public information from day discussions

### 4.2 Communication Rules
- **Day Phase**: Open discussion, token/word limit per player speech
- **Night Phase**: Complete silence, no communication
- **Voting**: Submit vote choice through game interface
- **Language**: English (or Russian for certain tournaments)

### 4.3 Strategic Elements
- **Mafia coordination**: All mafia make claims, Don makes final kill decision (every night, including first)
- **Sheriff strategy**: Must balance revealing information vs. staying hidden
- **Don strategy**: Find Sheriff while avoiding detection, make strategic kill decisions
- **Voting strategy**: Build coalitions, analyze voting patterns
- **Discussion strategy**: Read behavior, build trust, identify contradictions

---

## 5. Implementation Considerations for LLM Simulation

### 5.1 State Management
**Game State Must Track:**
- Player roles (hidden from most players)
- Player status (alive/eliminated)
- Day/night phase
- Vote history
- Nomination history
- Sheriff check results (per Sheriff)
- Don check results (per Don)
- Mafia kill attempts and results
- Player speeches/statements

### 5.2 LLM Agent Requirements
**Each LLM Agent Needs:**
- **Role information** (only what their role allows them to know)
- **Game history** (all public information)
- **Private information** (Sheriff checks, Don checks, mafia coordination)
- **Current phase context** (what actions are available)
- **Strategy guidelines** (role-specific objectives)

### 5.3 Judge/Moderator System
**Judge Must:**
- Enforce turn order
- Enforce speech length limits (token/word limits for speeches)
- Manage response time limits for night actions (Don/Sheriff checks, mafia coordination)
- Process nominations
- Collect and count votes accurately
- Execute night actions in correct order
- Announce game state changes
- Detect win conditions
- Enforce rules and issue fouls

### 5.4 Communication Protocol
**Day Phase:**
- Structured turn-based speech
- Enforce speech length limits (token/word count)
- Parse nominations from speech
- Validate speech endings ("PASS"/"THANK YOU")

**Night Phase:**
- Silent except for role actions
- Process Sheriff checks first (every night, including first) - so sheriff can check even if killed
- Process mafia kill: All mafia make claims, Don makes final decision (every night, including first)
- Mafia players coordinate through game engine (know each other's identities)
- Process Don checks after mafia kill (every night, including first)

**Voting Phase:**
- Collect votes simultaneously (1.5-second window)
- Players submit vote choices through interface
- Handle default votes
- Process tie-breaking

### 5.5 Special Cases to Handle
1. **First day single nomination**: No vote
2. **Subsequent day single nomination**: Automatic elimination
3. **Tie votes**: Shorter speeches (reduced token/word limit), revote, potential elimination of all tied
4. **Win condition checks**: After each elimination and night kill
5. **Mafia coordination**: All mafia know each other from start (via game engine), Don makes final kill decision

---

## 6. Scoring System (Tournament Context)

### 6.1 Main Points
- **Win**: +0.75 points
- **Loss/Draw**: 0 points
- **Disqualification**: -0.5 points
- **Rules-based team loss**: -0.75 points

### 6.2 Bonus Points
- **Judge bonuses**: +0.1 to +0.9 for winners, up to +0.5 for losers

### 6.3 Penalty Points
- **Destructive play**: -0.2 to -0.4 points

---

## 7. Critical Rules for Simulation

### 7.1 Must-Implement Rules
1. **Mafia kill decision**: All mafia make claims, Don makes final decision (applies every night including first)
2. **Mafia knowledge**: Game engine provides all mafia identities to mafia players from start
3. **Role secrecy** (roles not revealed on elimination)
4. **Turn order** (rotating starting player)
5. **Speech length limits** (token/word count enforcement)
6. **Voting mechanics** (default to last nominated)
7. **Tie-breaking procedure** (shorter speeches, revote, potential all-elimination)

### 7.2 Communication Constraints
- No role claims based on night information
- No oaths, threats, or non-game arguments
- No foreign languages
- No spectator hints
- Must use player numbers only

### 7.3 Information Flow
- **Public**: All day speeches, nominations, votes, eliminations
- **Private (Sheriff)**: Check results
- **Private (Don)**: Check results, all mafia identities (from game engine)
- **Private (Mafia)**: All mafia identities (from game engine), kill coordination
- **Hidden**: Actual roles until game end

---

## 8. Recommended Simulation Architecture

### 8.1 Core Components
1. **Game Engine**: Manages state, phases, win conditions
2. **Judge Module**: Enforces rules, manages timing, processes actions
3. **LLM Agent System**: Individual player agents with role-specific knowledge
4. **Communication Layer**: Handles day/night communication protocols
5. **Voting System**: Processes nominations and votes
6. **Role Action System**: Handles Sheriff/Don checks, mafia kills

### 8.2 Data Structures
- **Player**: {id, role, status, number, speeches, votes, checks, mafia_identities (if mafia)}
- **Game State**: {phase, day_number, night_number, players, nominations, votes, history}
- **Role Information**: {type, abilities, private_info, known_mafia (for mafia players)}
- **Action Log**: {timestamp, phase, player, action, result}
- **Mafia Coordination**: {night_number, target_votes, result}

### 8.3 LLM Prompting Strategy
- **Context Window**: Full game history + role info
- **Role-Specific Prompts**: Different instructions for Sheriff, Don, Mafia, Civilian
- **Phase-Specific Prompts**: Day discussion vs. night actions
- **Strategy Guidance**: Role objectives, common strategies, meta-game awareness

---

## 9. Challenges for LLM Simulation

### 9.1 Technical Challenges
- **Mafia Kill Decision**: All mafia make claims, Don makes final kill decision every night (including first) - game engine facilitates this
- **Mafia Knowledge**: Game engine must provide mafia identities to mafia players at game start
- **Speech Length**: Enforcing token/word limits for speeches
- **Vote Synchronization**: Voting window for collecting votes
- **State Consistency**: Maintaining accurate game state across all agents

### 9.2 Strategic Challenges
- **Bluffing**: LLMs may struggle with deception
- **Reading Behavior**: Analyzing speech patterns and voting
- **Coalition Building**: Forming voting alliances
- **Information Management**: Deciding when to reveal vs. hide information

### 9.3 Validation Challenges
- **Rule Enforcement**: Ensuring all rules are followed
- **Fair Play**: Preventing meta-gaming or rule exploitation
- **Realistic Behavior**: Making LLM agents play like humans

---

## 10. Next Steps for Implementation

1. **Design Game Engine**: Core state management and phase transitions
2. **Implement Judge System**: Rule enforcement and action processing
3. **Create LLM Agent Framework**: Role-based agent system
4. **Build Communication Protocol**: Day/night message handling
5. **Implement Voting System**: Nomination and voting mechanics
6. **Add Role Actions**: Sheriff/Don checks, mafia kills
7. **Testing**: Validate rule compliance and game flow
8. **Strategy Tuning**: Optimize LLM prompts for realistic play

---

## Appendix: Key Phrases and Commands

### Judge Announcements
- **"Night falls."** - Start of game/night
- **"Morning has come (in the city)."** - Start of day
- **"The Sheriff wakes up, you have ten seconds."** - Sheriff check (first, every night including first)
- **"The mafia goes hunting."** - Mafia kill phase (second, every night including first)
- **"The Don wakes up, you have ten seconds."** - Don check (third, every night including first)
- **"Game over, red/black victory."** - Game end
- **"Accepted."** - Nomination accepted
- **"Thank you" / "Stop"** - End voting window

### Player Requirements
- **"PASS"** or **"THANK YOU"** - End speech
- **"I nominate player number X"** - Nomination phrase
- **Submit vote choice** - Voting action

---

*This analysis is based on the Official 2025 Mafia Rules translated on 15 July 2025 from mafgame.org/pages/rules*

