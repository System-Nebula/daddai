# D&D Campaign System Documentation

## Overview

A full-featured Dungeons & Dragons campaign management system integrated into the Discord bot. Each campaign is stored as a separate instance in Neo4j with full context, allowing campaigns to be resumed at any time.

## Features

### 🎲 Campaign Management
- **Create Campaigns**: Start new D&D campaigns with custom names and descriptions
- **Resume Campaigns**: Load campaigns with full context including:
  - Current turn order
  - Campaign summary and history
  - Active characters
  - Game state and location
  - Map data
- **Campaign State Tracking**: Automatically tracks game state, turn order, and campaign progress

### 👤 Character Management
- **Smart Character Creation**: 
  - Automatic ability score generation (4d6 drop lowest)
  - Intelligent score assignment based on class
  - Racial bonuses applied automatically
  - Hit points calculated based on class and Constitution
  - Proficiency bonus calculated by level
- **Character Classes**: All 12 D&D 5e classes supported
- **Character Races**: All 9 core races supported
- **Character Linking**: Characters linked to Discord user IDs
- **Campaign Integration**: Characters can be added to campaigns

### 🎯 Smart Dice Rolling
- **Context-Aware Rolling**: Automatically determines appropriate dice based on actions
- **Standard Notation**: Supports standard D&D dice notation (e.g., "2d6", "d20+5", "1d8+1d6")
- **Advantage/Disadvantage**: Full support for advantage and disadvantage rolls
- **Action-Based Rolling**: 
  - Attack rolls with weapon damage
  - Ability checks with proficiency
  - Saving throws
  - Initiative rolls
  - Skill checks
- **Critical Hits**: Automatic critical hit detection and damage doubling

### 🎭 Dungeon Master Assistant
- **Intelligent DM**: Acts as Dungeon Master, narrating actions and adjudicating rules
- **Action Processing**: Processes player actions with appropriate dice rolls
- **Narrative Generation**: Generates contextual narration based on roll results
- **Location Management**: Tracks and describes campaign locations
- **Turn Management**: Manages combat turn order and initiative

## Usage Examples

### Starting a Campaign
```
User: "Let's start a D&D campaign called 'Mists of Mangoria'"
Bot: [Creates campaign and provides DM welcome message]
```

### Resuming a Campaign
```
User: "Let's play dnd, we were on the adventure mists of mangoria"
Bot: [Loads campaign context, shows summary, current turn, active characters]
```

### Creating a Character
```
User: "I want to create a character named Thorne, he's a Fighter, Human, level 1"
Bot: [Creates character with smart defaults, shows character sheet]
```

### Taking Actions
```
User: "I attack the goblin with my sword"
Bot: [Rolls attack, rolls damage, provides DM narration]

User: "I make a strength check to break down the door"
Bot: [Rolls d20 + Strength modifier, provides result]

User: "I cast fireball at the group of enemies"
Bot: [Rolls spell attack/damage, provides narration]
```

### Rolling Dice
```
User: "Roll 2d6+3"
Bot: [Rolls dice, shows individual rolls and total]

User: "Roll initiative"
Bot: [Rolls d20 + Dexterity modifier]
```

### Turn Management
```
User: "Next turn"
Bot: [Advances to next character in turn order]
```

## Technical Architecture

### Database Structure (Neo4j)
- **Campaign Nodes**: Store campaign data, state, and metadata
- **Character Nodes**: Store character sheets and stats
- **User Nodes**: Link Discord users to characters
- **Relationships**:
  - `(User)-[:DMS]->(Campaign)`: DM relationship
  - `(Character)-[:PLAYS_IN]->(Campaign)`: Character participation
  - `(User)-[:OWNS]->(Character)`: Character ownership

### Tool Integration
All D&D functionality is exposed through ReActAgent tools:
- `start_dnd_campaign`: Create new campaigns
- `resume_dnd_campaign`: Load existing campaigns
- `create_dnd_character`: Create characters
- `roll_dnd_dice`: Roll dice with notation
- `dnd_action`: Process player actions
- `next_turn`: Advance turn order

### Smart Features
1. **Context Awareness**: Tools automatically use user context (user_id, channel_id) from execution
2. **Intelligent Defaults**: Character creation uses smart defaults based on class/race
3. **Rule Adjudication**: DM tool automatically applies D&D 5e rules
4. **State Persistence**: All game state is persisted in Neo4j for resumption

## Campaign Data Structure

```json
{
  "campaign_id": "campaign_mists_of_mangoria_1234567890",
  "name": "Mists of Mangoria",
  "dm_user_id": "123456789",
  "status": "active",
  "current_turn": "Thorne",
  "turn_order": ["Thorne", "Elara", "Grimm"],
  "summary": "The party is exploring the ancient ruins...",
  "game_state": {
    "initiative_order": ["Thorne", "Elara", "Grimm"],
    "current_location": "Ancient Ruins - Main Chamber",
    "encounters": [],
    "notes": []
  },
  "map_data": {}
}
```

## Character Data Structure

```json
{
  "character_id": "char_123456789_thorne_1234567890",
  "discord_id": "123456789",
  "name": "Thorne",
  "class": "Fighter",
  "race": "Human",
  "level": 1,
  "ability_scores": {
    "Strength": 16,
    "Dexterity": 14,
    "Constitution": 15,
    "Intelligence": 12,
    "Wisdom": 10,
    "Charisma": 8
  },
  "ability_modifiers": {
    "Strength": 3,
    "Dexterity": 2,
    "Constitution": 2,
    "Intelligence": 1,
    "Wisdom": 0,
    "Charisma": -1
  },
  "hit_points": {
    "current": 12,
    "max": 12,
    "temporary": 0
  },
  "proficiency_bonus": 2,
  "armor_class": 12
}
```

## Future Enhancements

- Spell management and tracking
- Inventory management integration
- Combat encounter management
- NPC tracking and management
- Quest and objective tracking
- Map visualization
- Custom homebrew rules support

