"""
D&D Character Tool - Character creation and management for D&D campaigns.
All characters are campaign-specific. Supports async operations and concurrent character creation.
"""
from typing import Dict, Any, Optional, List
from neo4j import GraphDatabase
import json
import random
import asyncio
from datetime import datetime
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from Refactored.logger_config import logger


class DnDCharacterTool:
    """
    Character creation and management for D&D.
    Supports smart character creation with D&D 5e rules.
    """
    
    # D&D 5e Ability Scores
    ABILITY_SCORES = ["Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"]
    
    # D&D 5e Classes
    CLASSES = {
        "Barbarian": {"hit_die": 12, "primary_abilities": ["Strength", "Constitution"]},
        "Bard": {"hit_die": 8, "primary_abilities": ["Charisma"]},
        "Cleric": {"hit_die": 8, "primary_abilities": ["Wisdom"]},
        "Druid": {"hit_die": 8, "primary_abilities": ["Wisdom"]},
        "Fighter": {"hit_die": 10, "primary_abilities": ["Strength", "Dexterity"]},
        "Monk": {"hit_die": 8, "primary_abilities": ["Dexterity", "Wisdom"]},
        "Paladin": {"hit_die": 10, "primary_abilities": ["Strength", "Charisma"]},
        "Ranger": {"hit_die": 10, "primary_abilities": ["Dexterity", "Wisdom"]},
        "Rogue": {"hit_die": 8, "primary_abilities": ["Dexterity"]},
        "Sorcerer": {"hit_die": 6, "primary_abilities": ["Charisma"]},
        "Warlock": {"hit_die": 8, "primary_abilities": ["Charisma"]},
        "Wizard": {"hit_die": 6, "primary_abilities": ["Intelligence"]}
    }
    
    # D&D 5e Races
    RACES = {
        "Human": {"ability_bonuses": {"all": 1}},
        "Elf": {"ability_bonuses": {"Dexterity": 2}},
        "Dwarf": {"ability_bonuses": {"Constitution": 2}},
        "Halfling": {"ability_bonuses": {"Dexterity": 2}},
        "Dragonborn": {"ability_bonuses": {"Strength": 2, "Charisma": 1}},
        "Gnome": {"ability_bonuses": {"Intelligence": 2}},
        "Half-Elf": {"ability_bonuses": {"Charisma": 2, "other": 1}},
        "Half-Orc": {"ability_bonuses": {"Strength": 2, "Constitution": 1}},
        "Tiefling": {"ability_bonuses": {"Intelligence": 1, "Charisma": 2}}
    }
    
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        self._initialize_schema()
    
    def _initialize_schema(self):
        """Initialize character schema."""
        # Schema is initialized in campaign tool, but ensure character nodes exist
        pass
    
    def roll_ability_scores(self, method: str = "standard") -> List[int]:
        """
        Roll ability scores using specified method.
        
        Args:
            method: "standard" (4d6 drop lowest), "point_buy", or "array"
            
        Returns:
            List of 6 ability scores
        """
        if method == "standard":
            # 4d6 drop lowest
            scores = []
            for _ in range(6):
                rolls = [random.randint(1, 6) for _ in range(4)]
                rolls.sort()
                scores.append(sum(rolls[1:]))  # Drop lowest
            return scores
        elif method == "array":
            # Standard array: 15, 14, 13, 12, 10, 8
            return [15, 14, 13, 12, 10, 8]
        else:  # point_buy equivalent
            return [15, 14, 13, 12, 10, 8]
    
    async def create_character(
        self,
        discord_id: str,
        campaign_id: str,
        character_name: str,
        character_class: str,
        race: str,
        level: int = 1,
        background: Optional[str] = None,
        ability_scores: Optional[Dict[str, int]] = None,
        alignment: Optional[str] = None,
        image_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new D&D character for a specific campaign with smart defaults.
        Handles concurrent creation requests gracefully.
        
        Args:
            discord_id: Discord user ID
            campaign_id: Campaign ID (REQUIRED - characters are campaign-specific)
            character_name: Character name
            character_class: D&D class
            race: D&D race
            level: Starting level (default: 1)
            background: Character background
            ability_scores: Optional custom ability scores
            alignment: Character alignment
            image_url: Optional image URL for character portrait
            
        Returns:
            Character creation result
        """
        try:
            # Check if user already has a character in this campaign
            existing_chars = await self.get_user_characters(discord_id, campaign_id)
            if existing_chars.get("success") and existing_chars.get("characters"):
                return {
                    "success": False,
                    "error": f"You already have a character in this campaign. Characters are campaign-specific."
                }
            
            # Run character creation in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._create_character_sync(
                    discord_id, campaign_id, character_name, character_class, race,
                    level, background, ability_scores, alignment, image_url
                )
            )
            return result
        except Exception as e:
            logger.error(f"Error creating character: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to create character: {str(e)}"
            }
    
    def _validate_character(self, character_class: str, race: str, level: int, ability_scores: Dict[str, int], alignment: Optional[str]) -> tuple[bool, Optional[str]]:
        """
        Validate character creation according to D&D 5e rules.
        
        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])
        """
        # Validate class
        if character_class not in self.CLASSES:
            return False, f"Invalid class '{character_class}'. Valid classes: {', '.join(self.CLASSES.keys())}"
        
        # Validate race
        if race not in self.RACES:
            return False, f"Invalid race '{race}'. Valid races: {', '.join(self.RACES.keys())}"
        
        # Validate level
        if level < 1 or level > 20:
            return False, f"Invalid level {level}. Level must be between 1 and 20."
        
        # Validate ability scores
        if ability_scores:
            # Check all abilities are present
            for ability in self.ABILITY_SCORES:
                if ability not in ability_scores:
                    return False, f"Missing ability score: {ability}"
            
            # Validate ability score ranges (before racial bonuses)
            # Standard array/point buy: 8-15, rolled: 3-18
            for ability, score in ability_scores.items():
                if score < 3 or score > 18:
                    return False, f"Invalid {ability} score: {score}. Ability scores must be between 3 and 18 (before racial bonuses)."
        
        # Validate alignment (if provided)
        valid_alignments = [
            "Lawful Good", "Neutral Good", "Chaotic Good",
            "Lawful Neutral", "True Neutral", "Chaotic Neutral",
            "Lawful Evil", "Neutral Evil", "Chaotic Evil"
        ]
        if alignment and alignment not in valid_alignments:
            return False, f"Invalid alignment '{alignment}'. Valid alignments: {', '.join(valid_alignments)}"
        
        # Class-specific validations
        class_info = self.CLASSES[character_class]
        
        # Check ability score requirements for multiclassing (if level > 1)
        # For now, we'll just validate that primary abilities are reasonable
        if ability_scores:
            primary_abilities = class_info["primary_abilities"]
            for ability in primary_abilities:
                score = ability_scores.get(ability, 10)
                if score < 8:
                    return False, f"{character_class} requires {ability} to be at least 8. Current: {score}"
        
        return True, None
    
    def _create_character_sync(
        self,
        discord_id: str,
        campaign_id: str,
        character_name: str,
        character_class: str,
        race: str,
        level: int,
        background: Optional[str],
        ability_scores: Optional[Dict[str, int]],
        alignment: Optional[str],
        image_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Synchronous helper for character creation."""
        try:
            # Validate class and race
            if character_class not in self.CLASSES:
                return {
                    "success": False,
                    "error": f"Invalid class. Valid classes: {', '.join(self.CLASSES.keys())}"
                }
            
            if race not in self.RACES:
                return {
                    "success": False,
                    "error": f"Invalid race. Valid races: {', '.join(self.RACES.keys())}"
                }
            
            # Validate level
            if level < 1 or level > 20:
                return {
                    "success": False,
                    "error": f"Invalid level {level}. Level must be between 1 and 20."
                }
            
            # Roll or use provided ability scores
            if not ability_scores:
                rolled_scores = self.roll_ability_scores()
                # Assign scores intelligently based on class
                class_info = self.CLASSES[character_class]
                primary_abilities = class_info["primary_abilities"]
                
                # Sort scores descending
                rolled_scores.sort(reverse=True)
                
                ability_scores = {}
                used_scores = []
                
                # Assign highest scores to primary abilities
                for i, ability in enumerate(primary_abilities):
                    if i < len(rolled_scores):
                        ability_scores[ability] = rolled_scores[i]
                        used_scores.append(rolled_scores[i])
                
                # Assign remaining scores to other abilities
                remaining_scores = [s for s in rolled_scores if s not in used_scores]
                remaining_abilities = [a for a in self.ABILITY_SCORES if a not in ability_scores]
                
                for i, ability in enumerate(remaining_abilities):
                    if i < len(remaining_scores):
                        ability_scores[ability] = remaining_scores[i]
            else:
                # Ensure all abilities are present
                for ability in self.ABILITY_SCORES:
                    if ability not in ability_scores:
                        ability_scores[ability] = 10
            
            # Validate character before proceeding
            is_valid, validation_error = self._validate_character(
                character_class, race, level, ability_scores, alignment
            )
            if not is_valid:
                return {
                    "success": False,
                    "error": validation_error
                }
            
            # Apply racial bonuses
            race_info = self.RACES[race]
            racial_bonuses = race_info.get("ability_bonuses", {})
            
            for ability, bonus in racial_bonuses.items():
                if ability == "all":
                    for ab in self.ABILITY_SCORES:
                        ability_scores[ab] = ability_scores.get(ab, 10) + bonus
                elif ability == "other":
                    # Half-Elf: +2 Cha, +1 to two other abilities
                    # For simplicity, add to two highest non-Cha abilities
                    pass  # Handle manually if needed
                else:
                    ability_scores[ability] = ability_scores.get(ability, 10) + bonus
            
            # Calculate modifiers
            ability_modifiers = {}
            for ability, score in ability_scores.items():
                ability_modifiers[ability] = (score - 10) // 2
            
            # Calculate hit points
            class_info = self.CLASSES[character_class]
            hit_die = class_info["hit_die"]
            con_modifier = ability_modifiers.get("Constitution", 0)
            max_hp = hit_die + con_modifier + (level - 1) * ((hit_die // 2) + 1 + con_modifier)
            
            # Calculate proficiency bonus
            proficiency_bonus = 2 + ((level - 1) // 4)
            
            character_id = f"char_{discord_id}_{character_name.lower().replace(' ', '_')}_{datetime.now().timestamp()}"
            
            character_data = {
                "character_id": character_id,
                "discord_id": discord_id,
                "name": character_name,
                "class": character_class,
                "race": race,
                "level": level,
                "background": background or "Adventurer",
                "alignment": alignment or "Neutral",
                "ability_scores": ability_scores,
                "ability_modifiers": ability_modifiers,
                "hit_points": {
                    "current": max_hp,
                    "max": max_hp,
                    "temporary": 0
                },
                "proficiency_bonus": proficiency_bonus,
                "hit_die": hit_die,
                "armor_class": 10 + ability_modifiers.get("Dexterity", 0),
                "skills": [],
                "equipment": [],
                "spells": [],
                "features": [],
                "inventory": {},  # Campaign-specific inventory
                "gold": 0,  # Starting gold
                "image_url": image_url,  # Character portrait image URL
                "created_at": datetime.now().isoformat()
            }
            
            # Store character
            with self.driver.session() as session:
                session.run("MERGE (u:User {id: $discord_id})", discord_id=discord_id)
                
                session.run("""
                    MERGE (ch:Character {id: $character_id})
                    SET ch.discord_id = $discord_id,
                        ch.name = $character_name,
                        ch.character_data = $character_data_json,
                        ch.created_at = datetime()
                    WITH ch
                    MATCH (u:User {id: $discord_id})
                    MERGE (u)-[:OWNS]->(ch)
                """,
                    character_id=character_id,
                    discord_id=discord_id,
                    character_name=character_name,
                    character_data_json=json.dumps(character_data)
                )
                
                # Add to campaign if specified
                if campaign_id:
                    session.run("""
                        MATCH (c:Campaign {id: $campaign_id})
                        MATCH (ch:Character {id: $character_id})
                        MERGE (ch)-[:PLAYS_IN]->(c)
                    """,
                        campaign_id=campaign_id,
                        character_id=character_id
                    )
            
            logger.info(f"Created D&D character: {character_name} ({character_class} {race}) for user {discord_id}")
            
            return {
                "success": True,
                "character_id": character_id,
                "character_data": character_data,
                "message": f"Character '{character_name}' created successfully!"
            }
        except Exception as e:
            logger.error(f"Error creating character: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to create character: {str(e)}"
            }
    
    async def get_character(self, character_id: str) -> Dict[str, Any]:
        """Get character data by ID."""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: self._get_character_sync(character_id)
            )
        except Exception as e:
            logger.error(f"Error getting character: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to get character: {str(e)}"
            }
    
    def _get_character_sync(self, character_id: str) -> Dict[str, Any]:
        """Synchronous helper for getting character."""
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (ch:Character {id: $character_id})
                    RETURN ch.character_data AS character_data
                """,
                    character_id=character_id
                )
                
                record = result.single()
                if not record:
                    return {
                        "success": False,
                        "error": "Character not found"
                    }
                
                character_data = json.loads(record["character_data"]) if isinstance(record["character_data"], str) else record["character_data"]
                
                return {
                    "success": True,
                    "character_data": character_data
                }
        except Exception as e:
            logger.error(f"Error getting character: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to get character: {str(e)}"
            }
    
    async def get_user_characters(self, discord_id: str, campaign_id: Optional[str] = None) -> Dict[str, Any]:
        """Get all characters for a user, optionally filtered by campaign."""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: self._get_user_characters_sync(discord_id, campaign_id)
            )
        except Exception as e:
            logger.error(f"Error getting user characters: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to get characters: {str(e)}"
            }
    
    def _get_user_characters_sync(self, discord_id: str, campaign_id: Optional[str] = None) -> Dict[str, Any]:
        """Synchronous helper for getting user characters."""
        try:
            with self.driver.session() as session:
                if campaign_id:
                    result = session.run("""
                        MATCH (u:User {id: $discord_id})-[:OWNS]->(ch:Character)-[:PLAYS_IN]->(c:Campaign {id: $campaign_id})
                        RETURN ch.character_data AS character_data
                    """,
                        discord_id=discord_id,
                        campaign_id=campaign_id
                    )
                else:
                    result = session.run("""
                        MATCH (u:User {id: $discord_id})-[:OWNS]->(ch:Character)
                        RETURN ch.character_data AS character_data
                    """,
                        discord_id=discord_id
                    )
                
                characters = []
                for record in result:
                    char_data = json.loads(record["character_data"]) if isinstance(record["character_data"], str) else record["character_data"]
                    characters.append(char_data)
                
                return {
                    "success": True,
                    "characters": characters
                }
        except Exception as e:
            logger.error(f"Error getting user characters: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to get characters: {str(e)}"
            }
    
    async def update_character(
        self,
        character_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update character data."""
        try:
            char_result = await self.get_character(character_id)
            if not char_result.get("success"):
                return char_result
            
            character_data = char_result["character_data"]
            character_data.update(updates)
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._update_character_sync(character_id, character_data)
            )
            
            return {
                "success": True,
                "character_data": character_data,
                "message": "Character updated"
            }
        except Exception as e:
            logger.error(f"Error updating character: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to update character: {str(e)}"
            }
    
    def _get_starting_equipment(self, character_class: str, background: Optional[str]) -> List[str]:
        """Get starting equipment based on class."""
        equipment_map = {
            "Fighter": ["longsword", "shield", "leather armor", "explorer's pack"],
            "Rogue": ["rapier", "shortbow", "leather armor", "thieves' tools", "burglar's pack"],
            "Wizard": ["quarterstaff", "component pouch", "scholar's pack", "spellbook"],
            "Cleric": ["mace", "shield", "scale mail", "priest's pack", "holy symbol"],
            "Ranger": ["longsword", "longbow", "leather armor", "explorer's pack"],
            "Paladin": ["longsword", "shield", "chain mail", "priest's pack", "holy symbol"],
            "Barbarian": ["greataxe", "handaxe", "explorer's pack"],
            "Bard": ["rapier", "leather armor", "diplomat's pack", "lute"],
            "Druid": ["scimitar", "shield", "leather armor", "explorer's pack", "druidic focus"],
            "Monk": ["shortsword", "dart", "explorer's pack"],
            "Sorcerer": ["quarterstaff", "component pouch", "scholar's pack"],
            "Warlock": ["light crossbow", "component pouch", "scholar's pack", "pact weapon"]
        }
        return equipment_map.get(character_class, ["simple weapon", "explorer's pack"])
    
    def _get_starting_gold(self, character_class: str) -> int:
        """Get starting gold based on class (D&D 5e rules)."""
        gold_map = {
            "Fighter": 200,
            "Rogue": 200,
            "Wizard": 200,
            "Cleric": 200,
            "Ranger": 200,
            "Paladin": 200,
            "Barbarian": 200,
            "Bard": 200,
            "Druid": 200,
            "Monk": 200,
            "Sorcerer": 200,
            "Warlock": 200
        }
        return gold_map.get(character_class, 200)
    
    def _update_character_sync(self, character_id: str, character_data: Dict[str, Any]):
        """Synchronous helper for updating character."""
        with self.driver.session() as session:
            session.run("""
                MATCH (ch:Character {id: $character_id})
                SET ch.character_data = $character_data_json
            """,
                character_id=character_id,
                character_data_json=json.dumps(character_data)
            )
    
    async def get_character_inventory(self, character_id: str) -> Dict[str, Any]:
        """Get character's campaign-specific inventory."""
        char_result = await self.get_character(character_id)
        if not char_result.get("success"):
            return char_result
        
        char_data = char_result["character_data"]
        return {
            "success": True,
            "character_id": character_id,
            "character_name": char_data.get("name"),
            "inventory": char_data.get("inventory", {}),
            "gold": char_data.get("gold", 0),
            "equipment": char_data.get("equipment", [])
        }
    
    async def add_item_to_character(
        self,
        character_id: str,
        item_name: str,
        quantity: int = 1
    ) -> Dict[str, Any]:
        """Add item to character's campaign-specific inventory."""
        char_result = await self.get_character(character_id)
        if not char_result.get("success"):
            return char_result
        
        char_data = char_result["character_data"]
        inventory = char_data.get("inventory", {})
        
        item_name = item_name.lower().strip()
        current_qty = inventory.get(item_name, 0)
        inventory[item_name] = current_qty + quantity
        
        char_data["inventory"] = inventory
        
        await self.update_character(character_id, char_data)
        
        return {
            "success": True,
            "message": f"Added {quantity} {item_name}(s) to inventory",
            "item": item_name,
            "quantity": inventory[item_name]
        }
    
    async def remove_item_from_character(
        self,
        character_id: str,
        item_name: str,
        quantity: int = 1
    ) -> Dict[str, Any]:
        """Remove item from character's campaign-specific inventory."""
        char_result = await self.get_character(character_id)
        if not char_result.get("success"):
            return char_result
        
        char_data = char_result["character_data"]
        inventory = char_data.get("inventory", {})
        
        item_name = item_name.lower().strip()
        current_qty = inventory.get(item_name, 0)
        
        if current_qty < quantity:
            return {
                "success": False,
                "error": f"Insufficient items. You have {current_qty} {item_name}(s), but tried to remove {quantity}"
            }
        
        inventory[item_name] = current_qty - quantity
        if inventory[item_name] == 0:
            del inventory[item_name]
        
        char_data["inventory"] = inventory
        await self.update_character(character_id, char_data)
        
        return {
            "success": True,
            "message": f"Removed {quantity} {item_name}(s) from inventory",
            "remaining": inventory.get(item_name, 0)
        }
    
    async def update_character_image(
        self,
        character_id: str,
        image_url: str
    ) -> Dict[str, Any]:
        """
        Update character's portrait image.
        
        Args:
            character_id: Character ID
            image_url: Image URL (Discord attachment URL or other URL)
            
        Returns:
            Update result
        """
        char_result = await self.get_character(character_id)
        if not char_result.get("success"):
            return char_result
        
        char_data = char_result["character_data"]
        char_data["image_url"] = image_url
        
        await self.update_character(character_id, char_data)
        
        return {
            "success": True,
            "message": f"Character image updated",
            "image_url": image_url,
            "character_name": char_data.get("name")
        }
    
    async def get_character_sheet(
        self,
        discord_id: str,
        campaign_id: str,
        character_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get full character sheet with image.
        
        Args:
            discord_id: User Discord ID
            campaign_id: Campaign ID
            character_name: Optional character name (if user has multiple characters)
            
        Returns:
            Character sheet data
        """
        chars_result = await self.get_user_characters(discord_id, campaign_id)
        if not chars_result.get("success") or not chars_result.get("characters"):
            return {
                "success": False,
                "error": "Character not found in this campaign"
            }
        
        # Find character
        character = None
        for char in chars_result["characters"]:
            char_data = char if isinstance(char, dict) else {}
            if not character_name or char_data.get("name") == character_name:
                character = char_data
                break
        
        if not character:
            return {
                "success": False,
                "error": f"Character '{character_name}' not found"
            }
        
        return {
            "success": True,
            "character_data": character,
            "image_url": character.get("image_url")
        }

