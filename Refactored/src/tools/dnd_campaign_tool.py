"""
D&D Campaign Tool - Full-featured Dungeons & Dragons campaign management.
Tracks campaigns, characters, game state, maps, and acts as Dungeon Master.
All methods are async for better performance.
"""
from typing import Dict, Any, Optional, List
from neo4j import GraphDatabase
import json
import asyncio
from datetime import datetime
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from Refactored.logger_config import logger

# Import LLM client for story generation
try:
    from src.clients.llm_client_factory import get_default_llm_client
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    logger.warning("LLM client not available for story generation")


class DnDCampaignTool:
    """
    Full-featured D&D campaign management system.
    Each campaign is stored as a separate instance with full context.
    """
    
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        self._initialize_schema()
    
    def _initialize_schema(self):
        """Initialize D&D campaign schema in Neo4j."""
        with self.driver.session() as session:
            try:
                # Campaign constraints and indexes
                session.run("CREATE CONSTRAINT campaign_id IF NOT EXISTS FOR (c:Campaign) REQUIRE c.id IS UNIQUE")
                session.run("CREATE INDEX campaign_name IF NOT EXISTS FOR (c:Campaign) ON (c.name)")
                session.run("CREATE INDEX campaign_status IF NOT EXISTS FOR (c:Campaign) ON (c.status)")
                
                # Character constraints
                session.run("CREATE CONSTRAINT character_id IF NOT EXISTS FOR (ch:Character) REQUIRE ch.id IS UNIQUE")
                session.run("CREATE INDEX character_user IF NOT EXISTS FOR (ch:Character) ON (ch.discord_id)")
                
                # Game state
                session.run("CREATE CONSTRAINT game_state_id IF NOT EXISTS FOR (gs:GameState) REQUIRE gs.id IS UNIQUE")
            except Exception as e:
                logger.debug(f"Schema initialization (may already exist): {e}")
    
    async def create_campaign(
        self,
        campaign_name: str,
        dm_user_id: str,
        description: Optional[str] = None,
        ruleset: str = "5e",
        thread_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        theme: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new D&D campaign with theme and story generation.
        
        Args:
            campaign_name: Name of the campaign (e.g., "Mists of Mangoria")
            dm_user_id: Discord ID of the Dungeon Master
            description: Optional campaign description
            ruleset: D&D ruleset version (default: "5e")
            thread_id: Discord thread ID
            channel_id: Discord channel ID
            theme: Campaign theme (e.g., "dark fantasy", "high magic", "steampunk", "horror")
            
        Returns:
            Campaign creation result with generated story
        """
        try:
            campaign_id = f"campaign_{campaign_name.lower().replace(' ', '_')}_{datetime.now().timestamp()}"
            
            # Generate initial story based on theme and name
            initial_story = await self._generate_campaign_story(campaign_name, theme, description)
            
            campaign_data = {
                "campaign_id": campaign_id,
                "name": campaign_name,
                "dm_user_id": dm_user_id,
                "description": description or f"A D&D {ruleset} campaign: {campaign_name}",
                "theme": theme or "fantasy",
                "ruleset": ruleset,
                "status": "active",  # active, paused, completed
                "created_at": datetime.now().isoformat(),
                "last_played": datetime.now().isoformat(),
                "current_turn": None,
                "turn_order": [],
                "summary": initial_story.get("summary", f"Campaign '{campaign_name}' just started!"),
                "story": initial_story.get("story", ""),  # Full story content
                "story_history": [initial_story],  # Track story progression
                "map_data": {},
                "thread_id": thread_id,  # Discord thread ID for campaign
                "channel_id": channel_id,  # Discord channel ID
                "game_state": {
                    "initiative_order": [],
                    "current_location": initial_story.get("starting_location", "Unknown"),
                    "encounters": [],
                    "notes": []
                }
            }
            
            # Run database operation in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._create_campaign_sync(
                    campaign_id, campaign_name, dm_user_id, campaign_data, ruleset
                )
            )
            
            logger.info(f"Created D&D campaign: {campaign_name} (ID: {campaign_id})")
            
            return {
                "success": True,
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "thread_id": thread_id,
                "story": initial_story,
                "message": f"Campaign '{campaign_name}' created successfully! Ready to start your adventure."
            }
        except Exception as e:
            logger.error(f"Error creating campaign: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to create campaign: {str(e)}"
            }
    
    async def _generate_campaign_story(
        self,
        campaign_name: str,
        theme: Optional[str],
        description: Optional[str]
    ) -> Dict[str, Any]:
        """
        Generate campaign story using LLM based on name, theme, and description.
        
        Args:
            campaign_name: Campaign name
            theme: Campaign theme
            description: Campaign description
            
        Returns:
            Generated story content
        """
        if not LLM_AVAILABLE:
            return {
                "summary": f"The adventure '{campaign_name}' begins!",
                "story": f"A new D&D campaign: {campaign_name}",
                "starting_location": "A mysterious starting point"
            }
        
        try:
            llm_client = get_default_llm_client()
            
            theme_desc = f"Theme: {theme}" if theme else "Standard fantasy theme"
            desc_text = f"\nDescription: {description}" if description else ""
            
            story_prompt = f"""You are a creative Dungeon Master creating the opening story for a D&D 5e campaign.

Campaign Name: {campaign_name}
{theme_desc}{desc_text}

Create an engaging opening story (2-3 paragraphs) that:
1. Sets the scene and atmosphere
2. Introduces a compelling starting location
3. Hints at adventure and mystery
4. Matches the theme and tone

Provide:
- A brief summary (1-2 sentences)
- The full opening story
- The starting location name

Format your response as JSON:
{{
    "summary": "Brief summary",
    "story": "Full opening story",
    "starting_location": "Location name"
}}"""
            
            messages = [
                {"role": "system", "content": "You are an expert Dungeon Master creating engaging D&D campaign stories. Always respond with valid JSON."},
                {"role": "user", "content": story_prompt}
            ]
            
            response = llm_client.generate_response(
                messages=messages,
                temperature=0.8,  # Creative but coherent
                max_tokens=800
            )
            
            # Parse response
            response_text = response if isinstance(response, str) else response.get("content", str(response))
            
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{[^{}]*"summary"[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    story_data = json.loads(json_match.group(0))
                    return story_data
                except json.JSONDecodeError:
                    pass
            
            # Fallback: create structured response from text
            return {
                "summary": f"The adventure '{campaign_name}' begins!",
                "story": response_text[:500] if len(response_text) > 500 else response_text,
                "starting_location": "The Starting Point"
            }
        except Exception as e:
            logger.error(f"Error generating campaign story: {e}", exc_info=True)
            return {
                "summary": f"The adventure '{campaign_name}' begins!",
                "story": f"A new D&D campaign: {campaign_name}",
                "starting_location": "A mysterious starting point"
            }
    
    async def update_story(
        self,
        campaign_id: str,
        story_update: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update campaign story using LLM based on player actions and events.
        
        Args:
            campaign_id: Campaign ID
            story_update: Description of what happened
            context: Optional context (characters, location, etc.)
            
        Returns:
            Updated story content
        """
        try:
            campaign_result = await self.load_campaign_by_id(campaign_id)
            if not campaign_result.get("success"):
                return campaign_result
            
            campaign_data = campaign_result["campaign_data"]
            current_story = campaign_data.get("story", "")
            story_history = campaign_data.get("story_history", [])
            
            # Generate story continuation using LLM
            if LLM_AVAILABLE:
                llm_client = get_default_llm_client()
                
                context_text = ""
                if context:
                    context_text = f"\n\nContext:\n- Characters: {', '.join(context.get('characters', []))}\n"
                    context_text += f"- Location: {context.get('location', 'Unknown')}\n"
                    context_text += f"- Recent events: {context.get('recent_events', 'None')}"
                
                story_prompt = f"""You are a Dungeon Master continuing a D&D campaign story.

Previous Story:
{current_story[-1000:] if len(current_story) > 1000 else current_story}

What Happened:
{story_update}{context_text}

Continue the story naturally, incorporating what happened. Write 1-2 paragraphs that:
1. Describe the consequences of the action
2. Advance the narrative
3. Maintain consistency with the campaign theme
4. Set up the next scene

Provide a brief summary and the story continuation as JSON:
{{
    "summary": "Brief summary of what happened",
    "story_continuation": "The story continuation text"
}}"""
                
                messages = [
                    {"role": "system", "content": "You are an expert Dungeon Master. Always respond with valid JSON."},
                    {"role": "user", "content": story_prompt}
                ]
                
                response = llm_client.generate_response(
                    messages=messages,
                    temperature=0.8,
                    max_tokens=600
                )
                
                response_text = response if isinstance(response, str) else response.get("content", str(response))
                
                # Parse JSON response
                import re
                json_match = re.search(r'\{[^{}]*"summary"[^{}]*\}', response_text, re.DOTALL)
                if json_match:
                    try:
                        update_data = json.loads(json_match.group(0))
                        new_story = current_story + "\n\n" + update_data.get("story_continuation", story_update)
                        
                        # Update campaign
                        story_history.append({
                            "timestamp": datetime.now().isoformat(),
                            "update": story_update,
                            "story_continuation": update_data.get("story_continuation", story_update),
                            "summary": update_data.get("summary", story_update)
                        })
                        
                        await self.update_campaign_state(
                            campaign_id,
                            {
                                "story": new_story,
                                "story_history": story_history,
                                "summary": update_data.get("summary", story_update)
                            },
                            update_data.get("summary", story_update)
                        )
                        
                        return {
                            "success": True,
                            "story_update": update_data.get("story_continuation", story_update),
                            "summary": update_data.get("summary", story_update)
                        }
                    except json.JSONDecodeError:
                        pass
            
            # Fallback: simple update
            new_story = current_story + "\n\n" + story_update
            story_history.append({
                "timestamp": datetime.now().isoformat(),
                "update": story_update
            })
            
            await self.update_campaign_state(
                campaign_id,
                {
                    "story": new_story,
                    "story_history": story_history,
                    "summary": story_update
                },
                story_update
            )
            
            return {
                "success": True,
                "story_update": story_update,
                "summary": story_update
            }
        except Exception as e:
            logger.error(f"Error updating story: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to update story: {str(e)}"
            }
    
    def _create_campaign_sync(
        self,
        campaign_id: str,
        campaign_name: str,
        dm_user_id: str,
        campaign_data: Dict[str, Any],
        ruleset: str
    ):
        """Synchronous helper for campaign creation."""
        with self.driver.session() as session:
            session.run("""
                MERGE (dm:User {id: $dm_user_id})
                MERGE (c:Campaign {id: $campaign_id})
                SET c.name = $name,
                    c.dm_user_id = $dm_user_id,
                    c.description = $description,
                    c.ruleset = $ruleset,
                    c.status = $status,
                    c.created_at = datetime(),
                    c.last_played = datetime(),
                    c.campaign_data = $campaign_data_json
                MERGE (dm)-[:DMS]->(c)
            """,
                campaign_id=campaign_id,
                name=campaign_name,
                dm_user_id=dm_user_id,
                description=campaign_data["description"],
                ruleset=ruleset,
                status="active",
                campaign_data_json=json.dumps(campaign_data)
            )
    
    async def load_campaign(self, campaign_name: str) -> Dict[str, Any]:
        """
        Load a campaign by name with full context.
        
        Args:
            campaign_name: Name of the campaign to load
            
        Returns:
            Campaign data with full context
        """
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._load_campaign_sync(campaign_name)
            )
            return result
        except Exception as e:
            logger.error(f"Error loading campaign: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to load campaign: {str(e)}"
            }
    
    def _load_campaign_sync(self, campaign_name: str) -> Dict[str, Any]:
        """Synchronous helper for loading campaign."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:Campaign {name: $name})
                OPTIONAL MATCH (c)<-[:PLAYS_IN]-(ch:Character)
                OPTIONAL MATCH (c)<-[:DMS]-(dm:User)
                RETURN c.campaign_data AS campaign_data,
                       collect(DISTINCT ch.character_data) AS characters,
                       dm.id AS dm_id
                ORDER BY c.last_played DESC
                LIMIT 1
            """,
                name=campaign_name
            )
            
            record = result.single()
            if not record:
                return {
                    "success": False,
                    "error": f"Campaign '{campaign_name}' not found"
                }
            
            campaign_data = json.loads(record["campaign_data"]) if isinstance(record["campaign_data"], str) else record["campaign_data"]
            characters = [json.loads(ch) if isinstance(ch, str) else ch for ch in record["characters"] if ch]
            
            # Update last accessed
            session.run("""
                MATCH (c:Campaign {name: $name})
                SET c.last_played = datetime()
            """,
                name=campaign_name
            )
            
            # Build context summary
            current_turn = campaign_data.get("current_turn")
            turn_order = campaign_data.get("turn_order", [])
            summary = campaign_data.get("summary", "No summary available")
            
            context_summary = f"""
**Campaign: {campaign_name}**
**Status:** {campaign_data.get('status', 'unknown')}
**Current Location:** {campaign_data.get('game_state', {}).get('current_location', 'Unknown')}
**Players:** {len(characters)}
**Summary:** {summary}
"""
            
            if current_turn and turn_order:
                context_summary += f"\n**Current Turn:** {current_turn}\n**Turn Order:** {', '.join(turn_order)}"
            
            return {
                "success": True,
                "campaign_data": campaign_data,
                "characters": characters,
                "dm_id": record["dm_id"],
                "context_summary": context_summary,
                "campaign_id": campaign_data.get("campaign_id")
            }
    
    async def update_campaign_state(
        self,
        campaign_id: str,
        updates: Dict[str, Any],
        update_summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update campaign game state.
        
        Args:
            campaign_id: Campaign ID
            updates: Dictionary of state updates
            update_summary: Optional summary of what changed
            
        Returns:
            Update result
        """
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: self._update_campaign_state_sync(campaign_id, updates, update_summary)
            )
        except Exception as e:
            logger.error(f"Error updating campaign state: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to update campaign state: {str(e)}"
            }
    
    def _update_campaign_state_sync(
        self,
        campaign_id: str,
        updates: Dict[str, Any],
        update_summary: Optional[str]
    ) -> Dict[str, Any]:
        """Synchronous helper for updating campaign state."""
        try:
            with self.driver.session() as session:
                # Get current campaign data
                result = session.run("""
                    MATCH (c:Campaign {id: $campaign_id})
                    RETURN c.campaign_data AS campaign_data
                """,
                    campaign_id=campaign_id
                )
                
                record = result.single()
                if not record:
                    return {
                        "success": False,
                        "error": "Campaign not found"
                    }
                
                campaign_data = json.loads(record["campaign_data"]) if isinstance(record["campaign_data"], str) else record["campaign_data"]
                
                # Update campaign data
                campaign_data.update(updates)
                campaign_data["last_played"] = datetime.now().isoformat()
                
                if update_summary:
                    # Append to summary history
                    if "summary_history" not in campaign_data:
                        campaign_data["summary_history"] = []
                    campaign_data["summary_history"].append({
                        "timestamp": datetime.now().isoformat(),
                        "summary": update_summary
                    })
                    campaign_data["summary"] = update_summary
                
                # Save updated data
                session.run("""
                    MATCH (c:Campaign {id: $campaign_id})
                    SET c.campaign_data = $campaign_data_json,
                        c.last_played = datetime()
                """,
                    campaign_id=campaign_id,
                    campaign_data_json=json.dumps(campaign_data)
                )
                
                return {
                    "success": True,
                    "message": "Campaign state updated",
                    "campaign_data": campaign_data
                }
        except Exception as e:
            logger.error(f"Error updating campaign state: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to update campaign state: {str(e)}"
            }
    
    async def set_turn_order(
        self,
        campaign_id: str,
        turn_order: List[str],
        current_turn: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Set the turn order for combat/initiative.
        
        Args:
            campaign_id: Campaign ID
            turn_order: List of character names or user IDs in turn order
            current_turn: Current turn (defaults to first in order)
            
        Returns:
            Update result
        """
        if not turn_order:
            return {
                "success": False,
                "error": "Turn order cannot be empty"
            }
        
        current = current_turn or turn_order[0]
        
        return await self.update_campaign_state(
            campaign_id,
            {
                "turn_order": turn_order,
                "current_turn": current,
                "game_state": {
                    "initiative_order": turn_order
                }
            },
            f"Turn order set. Current turn: {current}"
        )
    
    async def next_turn(self, campaign_id: str) -> Dict[str, Any]:
        """
        Advance to the next turn.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Next turn information
        """
        try:
            campaign_result = await self.load_campaign_by_id(campaign_id)
            if not campaign_result.get("success"):
                return campaign_result
            
            campaign_data = campaign_result["campaign_data"]
            turn_order = campaign_data.get("turn_order", [])
            current_turn = campaign_data.get("current_turn")
            
            if not turn_order:
                return {
                    "success": False,
                    "error": "No turn order set"
                }
            
            # Find next turn
            try:
                current_index = turn_order.index(current_turn) if current_turn else -1
                next_index = (current_index + 1) % len(turn_order)
                next_turn = turn_order[next_index]
            except ValueError:
                next_turn = turn_order[0]
            
            result = await self.update_campaign_state(
                campaign_id,
                {"current_turn": next_turn},
                f"Turn advanced to {next_turn}"
            )
            
            result["next_turn"] = next_turn
            return result
        except Exception as e:
            logger.error(f"Error advancing turn: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to advance turn: {str(e)}"
            }
    
    async def update_map(
        self,
        campaign_id: str,
        map_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update campaign map data.
        
        Args:
            campaign_id: Campaign ID
            map_data: Map data dictionary
            
        Returns:
            Update result
        """
        try:
            campaign_result = await self.load_campaign_by_id(campaign_id)
            if not campaign_result.get("success"):
                return campaign_result
            
            campaign_data = campaign_result["campaign_data"]
            current_map = campaign_data.get("map_data", {})
            current_map.update(map_data)
            
            return await self.update_campaign_state(
                campaign_id,
                {"map_data": current_map},
                "Map updated"
            )
        except Exception as e:
            logger.error(f"Error updating map: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to update map: {str(e)}"
            }
    
    async def add_character_to_campaign(
        self,
        campaign_id: str,
        character_id: str
    ) -> Dict[str, Any]:
        """
        Add a character to a campaign.
        
        Args:
            campaign_id: Campaign ID
            character_id: Character ID
            
        Returns:
            Add result
        """
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._add_character_to_campaign_sync(campaign_id, character_id)
            )
            return {
                "success": True,
                "message": "Character added to campaign"
            }
        except Exception as e:
            logger.error(f"Error adding character to campaign: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to add character: {str(e)}"
            }
    
    def _add_character_to_campaign_sync(self, campaign_id: str, character_id: str):
        """Synchronous helper for adding character to campaign."""
        with self.driver.session() as session:
            session.run("""
                MATCH (c:Campaign {id: $campaign_id})
                MATCH (ch:Character {id: $character_id})
                MERGE (ch)-[:PLAYS_IN]->(c)
            """,
                campaign_id=campaign_id,
                character_id=character_id
            )
    
    async def list_campaigns(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        List all campaigns, optionally filtered by user participation.
        
        Args:
            user_id: Optional user ID to filter campaigns
            
        Returns:
            List of campaigns
        """
        try:
            with self.driver.session() as session:
                if user_id:
                    result = session.run("""
                        MATCH (u:User {id: $user_id})
                        OPTIONAL MATCH (u)-[:DMS]->(c:Campaign)
                        OPTIONAL MATCH (u)-[:PLAYS_IN]->(ch:Character)-[:PLAYS_IN]->(c:Campaign)
                        RETURN DISTINCT c.id AS campaign_id,
                               c.name AS name,
                               c.status AS status,
                               c.last_played AS last_played
                        ORDER BY c.last_played DESC
                    """,
                        user_id=user_id
                    )
                else:
                    result = session.run("""
                        MATCH (c:Campaign)
                        RETURN c.id AS campaign_id,
                               c.name AS name,
                               c.status AS status,
                               c.last_played AS last_played
                        ORDER BY c.last_played DESC
                    """)
                
                campaigns = []
                for record in result:
                    campaigns.append({
                        "campaign_id": record["campaign_id"],
                        "name": record["name"],
                        "status": record["status"],
                        "last_played": record["last_played"]
                    })
                
                return {
                    "success": True,
                    "campaigns": campaigns
                }
        except Exception as e:
            logger.error(f"Error listing campaigns: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to list campaigns: {str(e)}"
            }
    
    async def load_campaign_by_id(self, campaign_id: str) -> Dict[str, Any]:
        """Load campaign by ID (internal helper)."""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: self._load_campaign_by_id_sync(campaign_id)
            )
        except Exception as e:
            logger.error(f"Error loading campaign by ID: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to load campaign: {str(e)}"
            }
    
    def _load_campaign_by_id_sync(self, campaign_id: str) -> Dict[str, Any]:
        """Synchronous helper for loading campaign by ID."""
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (c:Campaign {id: $campaign_id})
                    OPTIONAL MATCH (c)<-[:PLAYS_IN]-(ch:Character)
                    RETURN c.campaign_data AS campaign_data,
                           collect(DISTINCT ch.character_data) AS characters
                """,
                    campaign_id=campaign_id
                )
                
                record = result.single()
                if not record:
                    return {
                        "success": False,
                        "error": "Campaign not found"
                    }
                
                campaign_data = json.loads(record["campaign_data"]) if isinstance(record["campaign_data"], str) else record["campaign_data"]
                characters = [json.loads(ch) if isinstance(ch, str) else ch for ch in record["characters"] if ch]
                
                return {
                    "success": True,
                    "campaign_data": campaign_data,
                    "characters": characters
                }
        except Exception as e:
            logger.error(f"Error loading campaign by ID: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to load campaign: {str(e)}"
            }
    
    async def get_party_members(self, campaign_name: str) -> Dict[str, Any]:
        """
        Get all characters in a campaign party.
        
        Args:
            campaign_name: Campaign name
            
        Returns:
            List of all party members with their details
        """
        try:
            campaign_result = await self.load_campaign(campaign_name)
            if not campaign_result.get("success"):
                return campaign_result
            
            characters = campaign_result.get("characters", [])
            
            party_info = []
            for char in characters:
                char_data = char if isinstance(char, dict) else {}
                party_info.append({
                    "name": char_data.get("name", "Unknown"),
                    "class": char_data.get("class", "Unknown"),
                    "race": char_data.get("race", "Unknown"),
                    "level": char_data.get("level", 1),
                    "hp": f"{char_data.get('hit_points', {}).get('current', 0)}/{char_data.get('hit_points', {}).get('max', 0)}",
                    "ac": char_data.get("armor_class", 0),
                    "discord_id": char_data.get("discord_id", "Unknown"),
                    "image_url": char_data.get("image_url")
                })
            
            return {
                "success": True,
                "campaign_name": campaign_name,
                "party_members": party_info,
                "party_size": len(party_info)
            }
        except Exception as e:
            logger.error(f"Error getting party members: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to get party members: {str(e)}"
            }

