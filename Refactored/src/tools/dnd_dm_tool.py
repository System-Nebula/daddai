"""
D&D Dungeon Master Tool - Acts as intelligent DM, manages game flow, narrative, and rules.
All methods are async. Generates story and processes actions automatically.
"""
from typing import Dict, Any, Optional, List
import asyncio
from Refactored.src.tools.dnd_campaign_tool import DnDCampaignTool
from Refactored.src.tools.dnd_character_tool import DnDCharacterTool
from Refactored.src.tools.dnd_dice_tool import DnDDiceTool
from Refactored.logger_config import logger


class DnDDMTool:
    """
    Intelligent Dungeon Master assistant.
    Manages game flow, narrative, rules adjudication, and campaign state.
    """
    
    def __init__(self):
        self.campaign_tool = DnDCampaignTool()
        self.character_tool = DnDCharacterTool()
        self.dice_tool = DnDDiceTool()
    
    async def start_campaign(
        self,
        campaign_name: str,
        dm_user_id: str,
        description: Optional[str] = None,
        thread_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        theme: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Start a new D&D campaign. Creates a Discord thread for the campaign.
        LLM generates the opening story based on name, theme, and description.
        
        Args:
            campaign_name: Campaign name
            dm_user_id: DM's Discord ID
            description: Campaign description
            thread_id: Discord thread ID (if thread already created)
            channel_id: Discord channel ID
            theme: Campaign theme (e.g., "dark fantasy", "high magic", "horror", "steampunk")
            
        Returns:
            Campaign start result with thread information and generated story
        """
        result = await self.campaign_tool.create_campaign(
            campaign_name, dm_user_id, description, thread_id=thread_id, channel_id=channel_id, theme=theme
        )
        
        if result.get("success"):
            story_data = result.get("story", {})
            story_text = story_data.get("story", "")
            starting_location = story_data.get("starting_location", "Unknown")
            
            result["dm_message"] = f"""
🎲 **Campaign Started: {campaign_name}**

{story_text}

**Starting Location:** {starting_location}

**Campaign Setup:**
- Players can create characters using the character creator (characters are campaign-specific)
- Use commands to take actions, make rolls, and interact with the world
- I'll act as your Dungeon Master, narrating the story and adjudicating rules
- The story will evolve based on your actions

**Getting Started:**
- Create your character: "I want to create a character for {campaign_name}"
- Begin your adventure: "What do we see?" or "Let's explore"

Ready to begin your epic adventure!
"""
        
        return result
    
    async def resume_campaign(self, campaign_name: str) -> Dict[str, Any]:
        """
        Resume a campaign with full context.
        
        Args:
            campaign_name: Campaign name to resume
            
        Returns:
            Campaign context and resume message
        """
        result = await self.campaign_tool.load_campaign(campaign_name)
        
        if result.get("success"):
            campaign_data = result["campaign_data"]
            characters = result["characters"]
            context_summary = result["context_summary"]
            
            # Build resume message
            resume_message = f"""
🎲 **Resuming Campaign: {campaign_name}**

{context_summary}

**Active Characters:**
"""
            for char in characters:
                char_data = char if isinstance(char, dict) else {}
                resume_message += f"- {char_data.get('name', 'Unknown')} ({char_data.get('class', 'Unknown')} {char_data.get('race', 'Unknown')}) - Level {char_data.get('level', 1)}\n"
            
            current_turn = campaign_data.get("current_turn")
            if current_turn:
                resume_message += f"\n**Current Turn:** {current_turn}\n"
            
            resume_message += "\n**What would you like to do?**\n"
            resume_message += "- Take an action\n"
            resume_message += "- Make a roll\n"
            resume_message += "- Explore the area\n"
            resume_message += "- Check your character sheet\n"
            
            result["resume_message"] = resume_message
        
        return result
    
    async def process_action(
        self,
        campaign_id: str,
        user_id: str,
        action: str,
        character_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a player action in the campaign.
        
        Args:
            campaign_id: Campaign ID
            user_id: User ID taking action
            action: Action description
            character_name: Character name (if multiple characters)
            
        Returns:
            Action result with DM narration
        """
        try:
            # Load campaign and character
            campaign_result = await self.campaign_tool.load_campaign_by_id(campaign_id)
            if not campaign_result.get("success"):
                return campaign_result
            
            campaign_data = campaign_result["campaign_data"]
            characters = campaign_result["characters"]
            
            # Find character
            character = None
            for char in characters:
                char_data = char if isinstance(char, dict) else {}
                if char_data.get("discord_id") == user_id:
                    if not character_name or char_data.get("name") == character_name:
                        character = char_data
                        break
            
            if not character:
                return {
                    "success": False,
                    "error": "Character not found in campaign"
                }
            
            # Determine if action requires a roll
            action_lower = action.lower()
            requires_roll = any(keyword in action_lower for keyword in [
                "attack", "check", "save", "roll", "hit", "cast", "use"
            ])
            
            # Build context for smart rolling
            context = {
                "strength_modifier": character.get("ability_modifiers", {}).get("Strength", 0),
                "dexterity_modifier": character.get("ability_modifiers", {}).get("Dexterity", 0),
                "constitution_modifier": character.get("ability_modifiers", {}).get("Constitution", 0),
                "intelligence_modifier": character.get("ability_modifiers", {}).get("Intelligence", 0),
                "wisdom_modifier": character.get("ability_modifiers", {}).get("Wisdom", 0),
                "charisma_modifier": character.get("ability_modifiers", {}).get("Charisma", 0),
                "proficiency_bonus": character.get("proficiency_bonus", 2),
                "level": character.get("level", 1)
            }
            
            # Process action - auto-roll dice if action requires it
            roll_result = None
            if requires_roll:
                roll_result = self.dice_tool.smart_roll(action, context)
            
            # Generate DM narration with story elements
            narration = await self._generate_narration(action, character, roll_result, campaign_data)
            
            # Update campaign story using LLM
            story_context = {
                "characters": [char.get("name") for char in characters if isinstance(char, dict)],
                "location": campaign_data.get("game_state", {}).get("current_location", "Unknown"),
                "recent_events": f"{character.get('name')} attempted: {action}"
            }
            
            story_update_text = f"{character.get('name', 'Player')} attempted: {action}"
            if roll_result and roll_result.get("success"):
                story_update_text += f" (Roll: {roll_result.get('total', 'N/A')})"
            
            # Update story asynchronously (don't block on this)
            asyncio.create_task(
                self.campaign_tool.update_story(campaign_id, story_update_text, story_context)
            )
            
            # Update campaign state
            summary_update = story_update_text
            await self.campaign_tool.update_campaign_state(
                campaign_id,
                {},
                summary_update
            )
            
            return {
                "success": True,
                "action": action,
                "character": character.get("name"),
                "roll_result": roll_result,
                "narration": narration,
                "campaign_id": campaign_id
            }
        except Exception as e:
            logger.error(f"Error processing action: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to process action: {str(e)}"
            }
    
    async def _generate_narration(
        self,
        action: str,
        character: Dict[str, Any],
        roll_result: Optional[Dict[str, Any]] = None,
        campaign_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate DM narration for an action.
        
        Args:
            action: Action description
            character: Character data
            roll_result: Optional dice roll result
            
        Returns:
            DM narration text
        """
        char_name = character.get("name", "The adventurer")
        char_class = character.get("class", "adventurer")
        
        narration = f"**{char_name}** ({char_class}) "
        
        if roll_result and roll_result.get("success"):
            total = roll_result.get("total", 0)
            natural_20 = roll_result.get("natural_20", False)
            natural_1 = roll_result.get("natural_1", False)
            
            if natural_20:
                narration += f"🎯 **CRITICAL SUCCESS!** (Natural 20) "
            elif natural_1:
                narration += f"💥 **CRITICAL FAILURE!** (Natural 1) "
            else:
                narration += f"rolled **{total}** "
            
            # Add context-specific narration
            if "attack" in action.lower():
                if natural_20:
                    narration += f"Your attack strikes true with incredible precision! "
                elif total >= 15:
                    narration += f"Your attack looks promising! "
                elif total >= 10:
                    narration += f"Your attack might connect... "
                else:
                    narration += f"Your attack goes wide. "
            
            elif "check" in action.lower() or "skill" in action.lower():
                if natural_20:
                    narration += f"You perform this action with exceptional skill! "
                elif total >= 15:
                    narration += f"You succeed admirably! "
                elif total >= 10:
                    narration += f"You manage to accomplish this. "
                else:
                    narration += f"You struggle with this task. "
        else:
            narration += f"attempts to {action}. "
        
        narration += f"\n\n*What happens next?*"
        
        return narration
    
    async def describe_location(
        self,
        campaign_id: str,
        location_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Describe the current location or a specific location.
        
        Args:
            campaign_id: Campaign ID
            location_name: Optional specific location name
            
        Returns:
            Location description
        """
        try:
            campaign_result = self.campaign_tool.load_campaign_by_id(campaign_id)
            if not campaign_result.get("success"):
                return campaign_result
            
            campaign_data = campaign_result["campaign_data"]
            game_state = campaign_data.get("game_state", {})
            current_location = location_name or game_state.get("current_location", "Unknown")
            
            # Generate location description
            description = f"""
**Location: {current_location}**

You find yourself in {current_location}. The area around you is filled with mystery and adventure.

*What would you like to explore?*
"""
            
            return {
                "success": True,
                "location": current_location,
                "description": description
            }
        except Exception as e:
            logger.error(f"Error describing location: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to describe location: {str(e)}"
            }
    
    async def set_location(
        self,
        campaign_id: str,
        location_name: str,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Set or update the current location.
        
        Args:
            campaign_id: Campaign ID
            location_name: Location name
            description: Optional location description
            
        Returns:
            Update result
        """
        try:
            campaign_result = await self.campaign_tool.load_campaign_by_id(campaign_id)
            if not campaign_result.get("success"):
                return campaign_result
            
            game_state = campaign_result["campaign_data"].get("game_state", {})
            game_state["current_location"] = location_name
            
            if description:
                if "location_descriptions" not in game_state:
                    game_state["location_descriptions"] = {}
                game_state["location_descriptions"][location_name] = description
            
            return await self.campaign_tool.update_campaign_state(
                campaign_id,
                {"game_state": game_state},
                f"Location changed to: {location_name}"
            )
        except Exception as e:
            logger.error(f"Error setting location: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to set location: {str(e)}"
            }

