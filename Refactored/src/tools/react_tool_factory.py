"""
ReAct Tool Factory - Class-based tool registration for ReActAgent.
Dynamically discovers and registers tools instead of hardcoding them.
"""
from typing import List, Dict, Any, Optional, Callable
from langchain_core.tools import tool, BaseTool
from Refactored.logger_config import logger


class ReActToolFactory:
    """
    Factory class for creating and managing LangChain tools for ReActAgent.
    Dynamically discovers and registers available tools.
    """
    
    def __init__(self, execution_tracker: Optional[Dict[str, Any]] = None, context: Optional[Dict[str, Any]] = None):
        """
        Initialize the tool factory.
        
        Args:
            execution_tracker: Dictionary to track tool executions (for ReActAgent)
            context: Context dictionary with user_id, channel_id, etc.
        """
        self.execution_tracker = execution_tracker or {}
        self.context = context or {}
        self._tool_instances = {}
        self._availability_cache = {}
    
    def _check_availability(self, module_name: str, class_or_func_name: str) -> bool:
        """Check if a module/class is available."""
        if module_name in self._availability_cache:
            return self._availability_cache[module_name]
        
        try:
            if module_name == "image_generation":
                from src.tools.image_generation_tool import generate_image
                self._availability_cache[module_name] = True
                return True
            elif module_name == "vision":
                from src.tools.vision_tool import VisionTool
                self._availability_cache[module_name] = True
                return True
            elif module_name == "youtube":
                from src.tools.youtube_transcript_tool import summarize_youtube
                self._availability_cache[module_name] = True
                return True
            elif module_name == "website":
                from src.tools.website_summarizer_tool import summarize_website
                self._availability_cache[module_name] = True
                return True
            elif module_name == "inventory":
                from Refactored.src.tools.inventory_tool import InventoryTool
                from Refactored.src.tools.trade_tool import TradeTool
                self._availability_cache[module_name] = True
                return True
            elif module_name == "dnd":
                from Refactored.src.tools.dnd_campaign_tool import DnDCampaignTool
                from Refactored.src.tools.dnd_character_tool import DnDCharacterTool
                from Refactored.src.tools.dnd_dice_tool import DnDDiceTool
                from Refactored.src.tools.dnd_dm_tool import DnDDMTool
                self._availability_cache[module_name] = True
                return True
            else:
                self._availability_cache[module_name] = False
                return False
        except ImportError as e:
            logger.debug(f"Module {module_name} not available: {e}")
            self._availability_cache[module_name] = False
            return False
    
    def _track_tool_call(self, tool_name: str, success: bool, **kwargs):
        """Track a tool call in execution tracker."""
        if self.execution_tracker and "tool_calls" in self.execution_tracker:
            call_data = {
                "tool": tool_name,
                "success": success,
                **kwargs
            }
            self.execution_tracker["tool_calls"].append(call_data)
    
    def _run_async_in_sync(self, async_func: Callable, timeout: int = 300) -> Any:
        """Run an async function in a sync context using thread executor."""
        import asyncio
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, async_func())
            return future.result(timeout=timeout)
    
    def create_core_tools(self) -> List[BaseTool]:
        """Create core tools (code interpreter, memory)."""
        tools = []
        
        # Code Interpreter
        from src.tools.code_interpreter import CodeInterpreter
        code_interpreter = CodeInterpreter()
        
        @tool
        def run_python(code: str) -> str:
            """Execute Python code to solve math, logic, or data problems. Code must be safe (no file I/O, no network). Returns the result or error message."""
            try:
                result = code_interpreter.run_python(code)
                self._track_tool_call("run_python", True, code=code[:200])
                return result
            except Exception as e:
                self._track_tool_call("run_python", False, code=code[:200], error=str(e))
                return f"Error: {str(e)}"
        
        tools.append(run_python)
        
        # Memory Tools
        from src.tools.memory_tools import MemoryTools
        memory_tools = MemoryTools()
        
        @tool
        def save_core_memory(content: str, channel_id: str) -> str:
            """Save an important fact, user preference, or long-term memory to core memory."""
            try:
                result = memory_tools.save_core_memory(content, channel_id)
                self._track_tool_call("save_core_memory", True, content=content[:200])
                return result
            except Exception as e:
                self._track_tool_call("save_core_memory", False, error=str(e))
                return f"Error: {str(e)}"
        
        @tool
        def get_core_memory(channel_id: str, query: Optional[str] = None, top_k: int = 5) -> str:
            """Retrieve core memories for a channel/user. Use this to recall important facts or preferences."""
            try:
                async def _get():
                    return await memory_tools.get_core_memory(channel_id, query, top_k)
                
                result = self._run_async_in_sync(_get, timeout=30)
                self._track_tool_call("get_core_memory", True, channel_id=channel_id)
                
                if result:
                    memories_text = "\n".join([f"- {m}" for m in result[:top_k]])
                    return f"📝 Core memories for {channel_id}:\n{memories_text}"
                else:
                    return f"No core memories found for {channel_id}"
            except Exception as e:
                self._track_tool_call("get_core_memory", False, error=str(e))
                return f"Error: {str(e)}"
        
        tools.extend([save_core_memory, get_core_memory])
        
        return tools
    
    def create_media_tools(self) -> List[BaseTool]:
        """Create media tools (image generation, vision, YouTube, website)."""
        tools = []
        
        # Image Generation
        if self._check_availability("image_generation", "generate_image"):
            from src.tools.image_generation_tool import generate_image
            
            @tool
            def generate_image_tool(prompt: str) -> str:
                """Generate an image using AI image generation. Takes a text prompt describing the image and returns the image path or URL."""
                try:
                    async def _generate():
                        return await generate_image(
                            prompt=prompt,
                            negative_prompt="blurry, low quality, distorted",
                            width=1024,
                            height=1024
                        )
                    
                    result = self._run_async_in_sync(_generate, timeout=300)
                    
                    # Store full result for Discord bot
                    self._track_tool_call("generate_image", True, prompt=prompt[:200], result=result)
                    
                    if isinstance(result, dict) and result.get("success"):
                        summary = f"✅ Image generated successfully!\n"
                        summary += f"**Prompt:** {result.get('prompt', prompt)}\n"
                        if result.get("image_path"):
                            summary += f"**Image Path:** {result.get('image_path')}\n"
                        if result.get("filename"):
                            summary += f"**Filename:** {result.get('filename')}\n"
                        if result.get("image_url"):
                            summary += f"**Image URL:** {result.get('image_url')}\n"
                        if result.get("width") and result.get("height"):
                            summary += f"**Dimensions:** {result.get('width')}x{result.get('height')}\n"
                        if result.get("job_id"):
                            summary += f"**Job ID:** {result.get('job_id')}\n"
                        summary += f"\n🎨 The image has been generated. The base64 data is available in the tool result for Discord attachment."
                        return summary
                    elif isinstance(result, dict) and result.get("error"):
                        return f"❌ Image generation failed: {result.get('error')}"
                    else:
                        return f"✅ Image generation completed. Result: {str(result)[:500]}"
                except Exception as e:
                    self._track_tool_call("generate_image", False, error=str(e))
                    return f"Error: {str(e)}"
            
            tools.append(generate_image_tool)
        
        # Vision Tool
        if self._check_availability("vision", "VisionTool"):
            from src.tools.vision_tool import VisionTool
            vision_tool = VisionTool()
            
            @tool
            def analyze_image_tool(image_url: str) -> str:
                """Analyze an image using vision capabilities."""
                try:
                    result = vision_tool.process_image(image_url, None)
                    self._track_tool_call("analyze_image", True, image_url=image_url[:200])
                    if isinstance(result, dict):
                        return result.get("description", result.get("analysis", str(result)))
                    return str(result)
                except Exception as e:
                    self._track_tool_call("analyze_image", False, error=str(e))
                    return f"Error: {str(e)}"
            
            tools.append(analyze_image_tool)
        
        # YouTube Summarizer
        if self._check_availability("youtube", "summarize_youtube"):
            from src.tools.youtube_transcript_tool import summarize_youtube
            
            @tool
            def summarize_youtube_tool(url: str, language_codes: Optional[str] = None) -> str:
                """Summarize a YouTube video by extracting and processing its transcript. Takes a YouTube URL and optional language codes (comma-separated, e.g., "en,es"). Returns a summary of the video content."""
                try:
                    lang_list = None
                    if language_codes:
                        lang_list = [lang.strip() for lang in language_codes.split(",")]
                    
                    async def _summarize():
                        return await summarize_youtube(
                            url=url,
                            language_codes=lang_list,
                            save_to_documents=False
                        )
                    
                    result = self._run_async_in_sync(_summarize, timeout=300)
                    self._track_tool_call("summarize_youtube", result.get("success", False), url=url)
                    
                    if result.get("success"):
                        summary = result.get("summary", "")
                        transcript_length = result.get("transcript_length", 0)
                        return f"✅ YouTube video summarized!\n\n**Summary:**\n{summary}\n\n**Transcript Length:** {transcript_length} characters"
                    else:
                        return f"❌ {result.get('error', 'Unknown error')}"
                except Exception as e:
                    self._track_tool_call("summarize_youtube", False, error=str(e))
                    return f"Error: {str(e)}"
            
            tools.append(summarize_youtube_tool)
        
        # Website Summarizer
        if self._check_availability("website", "summarize_website"):
            from src.tools.website_summarizer_tool import summarize_website
            
            @tool
            def summarize_website_tool(url: str, max_length: int = 50000) -> str:
                """Summarize a website by extracting and processing its content. Takes a website URL and optional max_length (default 50000 characters). Returns a summary of the website content."""
                try:
                    async def _summarize():
                        return await summarize_website(
                            url=url,
                            max_length=max_length,
                            save_to_documents=False
                        )
                    
                    result = self._run_async_in_sync(_summarize, timeout=300)
                    self._track_tool_call("summarize_website", result.get("success", False), url=url)
                    
                    if result.get("success"):
                        summary = result.get("summary", "")
                        content_length = result.get("content_length", 0)
                        return f"✅ Website summarized!\n\n**Summary:**\n{summary}\n\n**Content Length:** {content_length} characters"
                    else:
                        return f"❌ {result.get('error', 'Unknown error')}"
                except Exception as e:
                    self._track_tool_call("summarize_website", False, error=str(e))
                    return f"Error: {str(e)}"
            
            tools.append(summarize_website_tool)
        
        return tools
    
    def create_inventory_tools(self) -> List[BaseTool]:
        """Create inventory and trade tools."""
        tools = []
        
        if not self._check_availability("inventory", "InventoryTool"):
            return tools
        
        from Refactored.src.tools.inventory_tool import InventoryTool
        from Refactored.src.tools.trade_tool import TradeTool
        
        inventory_tool = InventoryTool()
        trade_tool = TradeTool()
        
        @tool
        def check_inventory(user_id: str, requesting_user_id: Optional[str] = None, is_admin: Optional[bool] = None) -> str:
            """Check a user's inventory/backpack. Users can only check their own inventory unless they are admins."""
            try:
                req_user_id = requesting_user_id or self.context.get("user_id", "unknown")
                admin_status = is_admin if is_admin is not None else self.context.get("is_admin", False)
                result = inventory_tool.get_inventory(user_id, req_user_id, admin_status)
                self._track_tool_call("check_inventory", result.get("success", False), user_id=user_id)
                
                if result.get("success"):
                    items_display = result.get("items_display", [])
                    total = result.get("total_items", 0)
                    return f"📦 Inventory for {user_id}:\n" + "\n".join(items_display) + f"\n\nTotal items: {total}"
                else:
                    return f"❌ {result.get('error', 'Unknown error')}"
            except Exception as e:
                self._track_tool_call("check_inventory", False, error=str(e))
                return f"Error: {str(e)}"
        
        @tool
        def add_item_to_inventory(user_id: str, item_name: str, quantity: int = 1) -> str:
            """Add items to a user's inventory."""
            try:
                result = inventory_tool.add_item(user_id, item_name, quantity)
                self._track_tool_call("add_item_to_inventory", result.get("success", False), user_id=user_id, item_name=item_name, quantity=quantity)
                if result.get("success"):
                    return f"✅ {result.get('message')}"
                else:
                    return f"❌ {result.get('error', 'Unknown error')}"
            except Exception as e:
                self._track_tool_call("add_item_to_inventory", False, error=str(e))
                return f"Error: {str(e)}"
        
        @tool
        def remove_item_from_inventory(user_id: str, item_name: str, quantity: int = 1) -> str:
            """Remove items from a user's inventory."""
            try:
                result = inventory_tool.remove_item(user_id, item_name, quantity)
                self._track_tool_call("remove_item_from_inventory", result.get("success", False), user_id=user_id, item_name=item_name, quantity=quantity)
                if result.get("success"):
                    return f"✅ {result.get('message')}"
                else:
                    return f"❌ {result.get('error', 'Unknown error')}"
            except Exception as e:
                self._track_tool_call("remove_item_from_inventory", False, error=str(e))
                return f"Error: {str(e)}"
        
        @tool
        def create_trade(from_user_id: str, to_user_id: str, from_items_json: str, to_items_json: str, channel_id: str) -> str:
            """Create a trade offer between two users. from_items_json and to_items_json are JSON strings."""
            try:
                import json
                from_items = json.loads(from_items_json) if from_items_json else {}
                to_items = json.loads(to_items_json) if to_items_json else {}
                
                result = trade_tool.create_trade(from_user_id, to_user_id, from_items, to_items, channel_id)
                self._track_tool_call("create_trade", result.get("success", False), from_user_id=from_user_id, to_user_id=to_user_id, trade_id=result.get("trade_id"))
                
                if result.get("success"):
                    trade_summary = result.get("trade_summary", {})
                    return f"✅ Trade offer created!\n**From:** {trade_summary.get('from_user')}\n**To:** {trade_summary.get('to_user')}\n**Offering:** {trade_summary.get('offering')}\n**Requesting:** {trade_summary.get('requesting')}\n\nTrade ID: {result.get('trade_id')}\nThe recipient can accept or decline via Discord embed buttons."
                else:
                    return f"❌ {result.get('error', 'Unknown error')}"
            except json.JSONDecodeError as e:
                return f"❌ Invalid JSON format: {str(e)}"
            except Exception as e:
                self._track_tool_call("create_trade", False, error=str(e))
                return f"Error: {str(e)}"
        
        tools.extend([check_inventory, add_item_to_inventory, remove_item_from_inventory, create_trade])
        logger.info("✅ Inventory and trade tools added")
        
        return tools
    
    def create_dnd_tools(self) -> List[BaseTool]:
        """Create D&D campaign tools."""
        tools = []
        
        if not self._check_availability("dnd", "DnDCampaignTool"):
            return tools
        
        from Refactored.src.tools.dnd_campaign_tool import DnDCampaignTool
        from Refactored.src.tools.dnd_character_tool import DnDCharacterTool
        from Refactored.src.tools.dnd_dice_tool import DnDDiceTool
        from Refactored.src.tools.dnd_dm_tool import DnDDMTool
        
        campaign_tool = DnDCampaignTool()
        character_tool = DnDCharacterTool()
        dice_tool = DnDDiceTool()
        dm_tool = DnDDMTool()
        
        @tool
        def start_dnd_campaign(campaign_name: str, dm_user_id: str, description: Optional[str] = None, theme: Optional[str] = None) -> str:
            """Start a new D&D campaign. Theme examples: "dark fantasy", "high magic", "horror", "steampunk", "medieval", "sword and sorcery"."""
            try:
                import asyncio
                dm_id = dm_user_id or self.context.get("user_id", "unknown")
                channel_id = self.context.get("channel_id")
                
                loop = asyncio.get_event_loop()
                result = loop.run_until_complete(
                    dm_tool.start_campaign(campaign_name, dm_id, description, thread_id=None, channel_id=channel_id, theme=theme)
                )
                
                self._track_tool_call("start_dnd_campaign", result.get("success", False), campaign_name=campaign_name, campaign_id=result.get("campaign_id"))
                
                if result.get("success"):
                    # Store Discord data for thread creation
                    if self.execution_tracker and "tool_calls" in self.execution_tracker:
                        self.execution_tracker["tool_calls"][-1]["discord_data"] = {
                            "create_thread": True,
                            "campaign_name": campaign_name,
                            "campaign_id": result.get("campaign_id")
                        }
                    return result.get("dm_message", f"Campaign '{campaign_name}' started!")
                else:
                    return f"❌ {result.get('error', 'Unknown error')}"
            except Exception as e:
                self._track_tool_call("start_dnd_campaign", False, error=str(e))
                return f"Error: {str(e)}"
        
        @tool
        def resume_dnd_campaign(campaign_name: str) -> str:
            """Resume a D&D campaign by name. Loads full campaign context including characters, turn order, and game state."""
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                result = loop.run_until_complete(dm_tool.resume_campaign(campaign_name))
                self._track_tool_call("resume_dnd_campaign", result.get("success", False), campaign_name=campaign_name)
                if result.get("success"):
                    return result.get("resume_message", f"Campaign '{campaign_name}' loaded!")
                else:
                    return f"❌ {result.get('error', 'Unknown error')}"
            except Exception as e:
                self._track_tool_call("resume_dnd_campaign", False, error=str(e))
                return f"Error: {str(e)}"
        
        @tool
        def create_dnd_character(discord_id: str, campaign_name: str, character_name: str, character_class: str, race: str, level: int = 1, background: Optional[str] = None, alignment: Optional[str] = None, image_url: Optional[str] = None) -> str:
            """Create a D&D character for a specific campaign. Valid classes: Barbarian, Bard, Cleric, Druid, Fighter, Monk, Paladin, Ranger, Rogue, Sorcerer, Warlock, Wizard. Valid races: Human, Elf, Dwarf, Halfling, Dragonborn, Gnome, Half-Elf, Half-Orc, Tiefling."""
            try:
                user_id = discord_id or self.context.get("user_id", "unknown")
                if not image_url:
                    image_url = self.context.get("image_urls", [None])[0] if self.context.get("image_urls") else None
                
                import asyncio
                loop = asyncio.get_event_loop()
                campaign_result = loop.run_until_complete(campaign_tool.load_campaign(campaign_name))
                
                if not campaign_result.get("success"):
                    return f"❌ Campaign '{campaign_name}' not found. Please create the campaign first."
                
                campaign_id = campaign_result.get("campaign_id")
                result = loop.run_until_complete(
                    character_tool.create_character(user_id, campaign_id, character_name, character_class, race, level, background, None, alignment, image_url)
                )
                self._track_tool_call("create_dnd_character", result.get("success", False), character_name=character_name)
                
                if result.get("success"):
                    char_data = result.get("character_data", {})
                    image_info = f"\n🖼️ Character image: {char_data.get('image_url')}" if char_data.get("image_url") else ""
                    return f"✅ {result.get('message')}\n\n**Character Sheet:**\nName: {char_data.get('name')}\nClass: {char_data.get('class')} {char_data.get('race')}\nLevel: {char_data.get('level')}\nHP: {char_data.get('hit_points', {}).get('current')}/{char_data.get('hit_points', {}).get('max')}\nAbility Scores: {', '.join([f'{k}: {v}' for k, v in char_data.get('ability_scores', {}).items()])}{image_info}"
                else:
                    return f"❌ {result.get('error', 'Unknown error')}"
            except Exception as e:
                self._track_tool_call("create_dnd_character", False, error=str(e))
                return f"Error: {str(e)}"
        
        @tool
        def roll_dnd_dice(dice_notation: str, modifier: int = 0, advantage: bool = False, disadvantage: bool = False) -> str:
            """Roll D&D dice using standard notation (e.g., "2d6", "d20+5", "1d8+1d6"). Supports advantage/disadvantage for d20 rolls."""
            try:
                result = dice_tool.roll_dice(dice_notation, modifier, advantage, disadvantage)
                self._track_tool_call("roll_dnd_dice", result.get("success", False), dice_notation=dice_notation)
                if result.get("success"):
                    details = " + ".join(result.get("details", []))
                    return f"🎲 **Roll Result:** {result.get('total')}\nRolls: {details}\nModifier: {result.get('modifier', 0)}\n{'🎯 Natural 20!' if result.get('natural_20') else ''}{'💥 Natural 1!' if result.get('natural_1') else ''}"
                else:
                    return f"❌ {result.get('error', 'Unknown error')}"
            except Exception as e:
                self._track_tool_call("roll_dnd_dice", False, error=str(e))
                return f"Error: {str(e)}"
        
        @tool
        def dnd_action(campaign_name: str, action: str, character_name: Optional[str] = None) -> str:
            """Take an action in a D&D campaign. Examples: "attack the goblin", "make a strength check", "cast fireball", "investigate the room"."""
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                campaign_result = loop.run_until_complete(campaign_tool.load_campaign(campaign_name))
                if not campaign_result.get("success"):
                    return f"❌ {campaign_result.get('error', 'Campaign not found')}"
                
                campaign_id = campaign_result.get("campaign_id")
                user_id = self.context.get("user_id", "unknown")
                result = loop.run_until_complete(dm_tool.process_action(campaign_id, user_id, action, character_name))
                self._track_tool_call("dnd_action", result.get("success", False), campaign_name=campaign_name, action=action)
                
                if result.get("success"):
                    narration = result.get("narration", "")
                    roll_info = ""
                    if result.get("roll_result"):
                        roll = result["roll_result"]
                        roll_info = f"\n\n🎲 **Roll:** {roll.get('total', 'N/A')}"
                        if roll.get("details"):
                            roll_info += f" ({', '.join(roll.get('details', []))})"
                    return f"{narration}{roll_info}"
                else:
                    return f"❌ {result.get('error', 'Unknown error')}"
            except Exception as e:
                self._track_tool_call("dnd_action", False, error=str(e))
                return f"Error: {str(e)}"
        
        @tool
        def next_turn(campaign_name: str) -> str:
            """Advance to the next turn in combat/initiative order."""
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                campaign_result = loop.run_until_complete(campaign_tool.load_campaign(campaign_name))
                if not campaign_result.get("success"):
                    return f"❌ {campaign_result.get('error', 'Campaign not found')}"
                
                campaign_id = campaign_result.get("campaign_id")
                result = loop.run_until_complete(campaign_tool.next_turn(campaign_id))
                self._track_tool_call("next_turn", result.get("success", False), campaign_name=campaign_name)
                if result.get("success"):
                    return f"✅ Turn advanced to: {result.get('next_turn', 'Unknown')}"
                else:
                    return f"❌ {result.get('error', 'Unknown error')}"
            except Exception as e:
                self._track_tool_call("next_turn", False, error=str(e))
                return f"Error: {str(e)}"
        
        @tool
        def get_party_members(campaign_name: str) -> str:
            """Get all characters in the campaign party. Shows who's in the party."""
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                result = loop.run_until_complete(campaign_tool.get_party_members(campaign_name))
                
                if not result.get("success"):
                    return f"❌ {result.get('error', 'Unknown error')}"
                
                party_members = result.get("party_members", [])
                party_size = result.get("party_size", 0)
                
                if party_size == 0:
                    return f"📋 **Party Members for {campaign_name}**\n\nNo characters in the party yet. Players can create characters to join!"
                
                party_list = f"📋 **Party Members for {campaign_name}** ({party_size} members)\n\n"
                for i, member in enumerate(party_members, 1):
                    party_list += f"**{i}. {member['name']}**\n"
                    party_list += f"   • {member['class']} {member['race']} (Level {member['level']})\n"
                    party_list += f"   • HP: {member['hp']} | AC: {member['ac']}\n"
                    if member.get('image_url'):
                        party_list += f"   • 🖼️ Portrait available\n"
                    party_list += "\n"
                
                return party_list
            except Exception as e:
                return f"Error: {str(e)}"
        
        tools.extend([start_dnd_campaign, resume_dnd_campaign, create_dnd_character, roll_dnd_dice, dnd_action, next_turn, get_party_members])
        logger.info("✅ D&D tools added")
        
        return tools
    
    def create_all_tools(self) -> List[BaseTool]:
        """Create all available tools."""
        all_tools = []
        
        all_tools.extend(self.create_core_tools())
        all_tools.extend(self.create_media_tools())
        all_tools.extend(self.create_inventory_tools())
        all_tools.extend(self.create_dnd_tools())
        
        logger.info(f"✅ Created {len(all_tools)} tools via ReActToolFactory")
        return all_tools

