"""
Refactored ReActAgent with Smart A2A communication and agent delegation.
Implements Thought-Action-Observation loop with agent delegation capabilities.
"""
import operator
import time
import sys
import asyncio
from typing import Annotated, List, Union, Dict, Any, Optional
from pathlib import Path
from typing_extensions import TypedDict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
try:
    from langchain_core.messages import ToolCall
except ImportError:
    # ToolCall might not be available in all versions, create a simple class
    from typing import TypedDict
    class ToolCall(TypedDict):
        name: str
        args: dict
        id: str
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from config import (
    LLM_PROVIDER, LMSTUDIO_BASE_URL, LMSTUDIO_MODEL,
    OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL,
    CHUTES_API_KEY, CHUTES_BASE_URL, CHUTES_MODEL
)
from src.tools.code_interpreter import CodeInterpreter
from src.tools.memory_tools import MemoryTools
from Refactored.src.agents.base.base_agent import BaseAgent
from Refactored.src.agents.base.agent_message import AgentMessage, AgentResponse
from Refactored.src.agents.base.agent_capability import AgentCapability, CapabilityType
from Refactored.logger_config import logger

# Import RAG tools
try:
    from src.tools.image_generation_tool import generate_image
    IMAGE_GENERATION_AVAILABLE = True
except ImportError:
    IMAGE_GENERATION_AVAILABLE = False
    logger.warning("Image generation tool not available")

try:
    from src.tools.vision_tool import VisionTool
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False

# Import inventory and trade tools
try:
    from Refactored.src.tools.inventory_tool import InventoryTool
    from Refactored.src.tools.trade_tool import TradeTool
    INVENTORY_AVAILABLE = True
except ImportError as e:
    INVENTORY_AVAILABLE = False
    logger.warning(f"Inventory/trade tools not available: {e}")

# Import D&D tools
try:
    from Refactored.src.tools.dnd_campaign_tool import DnDCampaignTool
    from Refactored.src.tools.dnd_character_tool import DnDCharacterTool
    from Refactored.src.tools.dnd_dice_tool import DnDDiceTool
    from Refactored.src.tools.dnd_dm_tool import DnDDMTool
    DND_AVAILABLE = True
except ImportError as e:
    DND_AVAILABLE = False
    logger.warning(f"D&D tools not available: {e}")

# Import YouTube and Website summarizer tools
try:
    from src.tools.youtube_transcript_tool import summarize_youtube
    YOUTUBE_AVAILABLE = True
except ImportError as e:
    YOUTUBE_AVAILABLE = False
    logger.warning(f"YouTube summarizer tool not available: {e}")

try:
    from src.tools.website_summarizer_tool import summarize_website
    WEBSITE_AVAILABLE = True
except ImportError as e:
    WEBSITE_AVAILABLE = False
    logger.warning(f"Website summarizer tool not available: {e}")

# Define State
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]


class ReActAgent(BaseAgent):
    """
    Refactored ReActAgent with Smart A2A communication.
    Agent that uses ReAct pattern via LangGraph with agent delegation capabilities.
    Implements Thought -> Action -> Observation loop with step tracking.
    """
    
    # Class-level flag to track if tool binding has failed (to avoid repeated failures)
    _tool_binding_failed = False
    
    def __init__(self, agent_id: str = "react_agent"):
        """
        Initialize ReActAgent.
        
        Args:
            agent_id: Unique agent identifier
        """
        super().__init__(
            agent_id=agent_id,
            name="ReActAgent",
            description="ReAct pattern agent with tool calling and agent delegation"
        )
        
        # Initialize context and execution tracker before tools (tools need these)
        self.current_context = {}
        self.last_execution = {
            "steps": [],
            "tool_calls": [],
            "final_result": None
        }
        
        self.tools = self._setup_tools()
        self.llm = self._setup_llm()
        self.graph = self._build_graph()
        
        # Register capabilities
        self.register_capability(AgentCapability(
            capability_type=CapabilityType.REASONING,
            description="Execute complex multi-step tasks using ReAct pattern with tool calling",
            parameters={
                "message": "str - Task description",
                "context": "Dict - Context information"
            },
            returns="Dict with 'result', 'steps', 'tool_calls'"
        ))
        
        # Register message handlers
        self.register_message_handler("execute_task", self._handle_execute_task)
        self.register_message_handler("react", self._handle_execute_task)
        
        logger.info(f"🤖 ReActAgent {agent_id} initialized with A2A support")
    
    async def process_message(self, message: AgentMessage) -> AgentResponse:
        """
        Process incoming messages.
        
        Args:
            message: Incoming message
            
        Returns:
            AgentResponse
        """
        if message.action in ["execute_task", "react"]:
            return await self._handle_execute_task(message)
        else:
            return AgentResponse.error_response(
                f"Unknown action: {message.action}",
                error_code="UNKNOWN_ACTION"
            )
    
    async def _handle_execute_task(self, message: AgentMessage) -> AgentResponse:
        """
        Handle task execution request.
        
        Args:
            message: Task execution message
            
        Returns:
            AgentResponse with execution result
        """
        try:
            payload = message.payload
            task_message = payload.get("message", "")
            context = payload.get("context", {})
            
            if not task_message:
                return AgentResponse.error_response(
                    "Task message is required",
                    error_code="MISSING_MESSAGE"
                )
            
            logger.info(f"ReActAgent executing task: {task_message[:100]}...")
            
            # Execute ReAct task in executor to avoid blocking async event loop
            import concurrent.futures
            loop = asyncio.get_event_loop()
            
            # Run synchronous run() method in thread pool to avoid blocking
            with concurrent.futures.ThreadPoolExecutor() as executor:
                try:
                    # Wait for result with timeout (5 minutes max)
                    result = await asyncio.wait_for(
                        loop.run_in_executor(executor, self.run, task_message, context),
                        timeout=300.0
                    )
                except asyncio.TimeoutError:
                    logger.error("ReActAgent task execution timed out after 5 minutes")
                    return AgentResponse.error_response(
                        "Task execution timed out. The request may be too complex or the system is overloaded.",
                        error_code="TIMEOUT"
                    )
                except Exception as e:
                    logger.error(f"Error executing ReActAgent task: {e}", exc_info=True)
                    raise
            
            logger.info(f"ReActAgent task completed successfully. Result length: {len(str(result))}")
            
            return AgentResponse.success_response(
                data={
                    "result": result,
                    "steps": self.last_execution.get("steps", []),
                    "tool_calls": self.last_execution.get("tool_calls", [])
                },
                metadata={
                    "task": task_message[:100]
                }
            )
        except Exception as e:
            logger.error(f"Error in ReActAgent._handle_execute_task: {e}", exc_info=True)
            return AgentResponse.error_response(str(e))
    
    def _setup_tools(self):
        """Initialize tools using ReActToolFactory."""
        from Refactored.src.tools.react_tool_factory import ReActToolFactory
        
        # Create factory with execution tracker and context
        # Context will be updated in run() method, but initialize with empty dict for now
        factory = ReActToolFactory(
            execution_tracker=self.last_execution,
            context=getattr(self, 'current_context', {})
        )
        
        # Get all tools from factory
        tools = factory.create_all_tools()
        
        # Store factory reference so we can update context later if needed
        self._tool_factory = factory
        
        return tools
    
    def _setup_tools_old(self):
        """OLD: Initialize tools (hardcoded - kept for reference)."""
        code_interpreter = CodeInterpreter()
        memory_tools = MemoryTools()
        
        # Wrap tools for LangChain
        from langchain_core.tools import tool
        
        tools = []
        
        @tool
        def run_python(code: str) -> str:
            """Execute Python code to solve math, logic, or data problems. Code must be safe (no file I/O, no network). Returns the result or error message."""
            try:
                result = code_interpreter.run_python(code)
                self.last_execution["tool_calls"].append({
                    "tool": "run_python",
                    "code": code[:200],
                    "success": True
                })
                return result
            except Exception as e:
                self.last_execution["tool_calls"].append({
                    "tool": "run_python",
                    "code": code[:200],
                    "success": False,
                    "error": str(e)
                })
                return f"Error: {str(e)}"
        
        tools.append(run_python)
        
        @tool
        def save_core_memory(content: str, channel_id: str) -> str:
            """Save an important fact, user preference, or long-term memory to core memory."""
            try:
                result = memory_tools.save_core_memory(content, channel_id)
                self.last_execution["tool_calls"].append({
                    "tool": "save_core_memory",
                    "content": content[:200],
                    "success": True
                })
                return result
            except Exception as e:
                self.last_execution["tool_calls"].append({
                    "tool": "save_core_memory",
                    "success": False,
                    "error": str(e)
                })
                return f"Error: {str(e)}"
        
        tools.append(save_core_memory)
        
        @tool
        def get_core_memory(channel_id: str, query: Optional[str] = None, top_k: int = 5) -> str:
            """Retrieve core memories for a channel/user. Use this to recall important facts or preferences."""
            try:
                import asyncio
                import concurrent.futures
                
                async def _get_memory():
                    return await memory_tools.get_core_memory(channel_id, query, top_k)
                
                # Run async function in thread executor
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _get_memory())
                    result = future.result(timeout=30)
                
                self.last_execution["tool_calls"].append({
                    "tool": "get_core_memory",
                    "channel_id": channel_id,
                    "success": True
                })
                
                if result:
                    memories_text = "\n".join([f"- {m}" for m in result[:top_k]])
                    return f"📝 Core memories for {channel_id}:\n{memories_text}"
                else:
                    return f"No core memories found for {channel_id}"
            except Exception as e:
                self.last_execution["tool_calls"].append({
                    "tool": "get_core_memory",
                    "success": False,
                    "error": str(e)
                })
                return f"Error: {str(e)}"
        
        tools.append(get_core_memory)
        
        # Add image generation if available
        if IMAGE_GENERATION_AVAILABLE:
            @tool
            def generate_image_tool(prompt: str) -> str:
                """Generate an image using AI image generation. Takes a text prompt describing the image and returns the image path or URL."""
                try:
                    # Run async function in sync context (LangChain tools are sync)
                    # Run in thread executor to avoid blocking event loop
                    import asyncio
                    import concurrent.futures
                    
                    async def _generate():
                        return await generate_image(
                            prompt=prompt,
                            negative_prompt="blurry, low quality, distorted",
                            width=1024,
                            height=1024
                        )
                    
                    # Run async function in thread executor to avoid blocking
                    # This works whether or not there's an existing event loop
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, _generate())
                        result = future.result(timeout=300)  # 5 minute timeout for image generation
                    
                    # Store full result for Discord bot - use "generate_image" as tool name to match Discord bot expectations
                    tool_call_entry = {
                        "tool": "generate_image",  # Discord bot looks for this exact name
                        "prompt": prompt[:200],
                        "success": True,
                        "result": result  # Store full result dict with image_base64 for Discord bot
                    }
                    self.last_execution["tool_calls"].append(tool_call_entry)
                    logger.debug(f"Stored tool call: tool={tool_call_entry['tool']}, has_result={bool(result)}, result_keys={list(result.keys()) if isinstance(result, dict) else 'not_dict'}")
                    
                    # Format result for LLM consumption - exclude base64 to avoid context bloat
                    if isinstance(result, dict) and result.get("success"):
                        # Return a summary without the base64 data
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
                    self.last_execution["tool_calls"].append({
                        "tool": "generate_image",
                        "success": False,
                        "error": str(e)
                    })
                    return f"Error: {str(e)}"
            
            tools.append(generate_image_tool)
        
        # Add vision tool if available
        if VISION_AVAILABLE:
            vision_tool_instance = VisionTool()
            
            @tool
            def analyze_image_tool(image_url: str) -> str:
                """Analyze an image using vision capabilities."""
                try:
                    result = vision_tool_instance.process_image(image_url, None)
                    self.last_execution["tool_calls"].append({
                        "tool": "analyze_image",
                        "image_url": image_url[:200],
                        "success": True
                    })
                    if isinstance(result, dict):
                        return result.get("description", result.get("analysis", str(result)))
                    return str(result)
                except Exception as e:
                    self.last_execution["tool_calls"].append({
                        "tool": "analyze_image",
                        "success": False,
                        "error": str(e)
                    })
                    return f"Error: {str(e)}"
            
            tools.append(analyze_image_tool)
        
        # Add inventory and trade tools if available
        if INVENTORY_AVAILABLE:
            inventory_tool_instance = InventoryTool()
            trade_tool_instance = TradeTool()
            
            @tool
            def check_inventory(user_id: str, requesting_user_id: Optional[str] = None, is_admin: Optional[bool] = None) -> str:
                """
                Check a user's inventory/backpack. 
                Users can only check their own inventory unless they are admins.
                If requesting_user_id is not provided, uses the current user from context.
                If is_admin is not provided, uses the current admin status from context.
                """
                try:
                    # Use provided values or fall back to context
                    req_user_id = requesting_user_id or self.current_context.get("user_id", "unknown")
                    admin_status = is_admin if is_admin is not None else self.current_context.get("is_admin", False)
                    result = inventory_tool_instance.get_inventory(user_id, req_user_id, admin_status)
                    self.last_execution["tool_calls"].append({
                        "tool": "check_inventory",
                        "user_id": user_id,
                        "requesting_user_id": requesting_user_id,
                        "success": result.get("success", False)
                    })
                    if result.get("success"):
                        items_display = result.get("items_display", [])
                        total = result.get("total_items", 0)
                        return f"📦 Inventory for {user_id}:\n" + "\n".join(items_display) + f"\n\nTotal items: {total}"
                    else:
                        return f"❌ {result.get('error', 'Unknown error')}"
                except Exception as e:
                    self.last_execution["tool_calls"].append({
                        "tool": "check_inventory",
                        "success": False,
                        "error": str(e)
                    })
                    return f"Error: {str(e)}"
            
            @tool
            def add_item_to_inventory(user_id: str, item_name: str, quantity: int = 1) -> str:
                """Add items to a user's inventory."""
                try:
                    result = inventory_tool_instance.add_item(user_id, item_name, quantity)
                    self.last_execution["tool_calls"].append({
                        "tool": "add_item_to_inventory",
                        "user_id": user_id,
                        "item_name": item_name,
                        "quantity": quantity,
                        "success": result.get("success", False)
                    })
                    if result.get("success"):
                        return f"✅ {result.get('message')}"
                    else:
                        return f"❌ {result.get('error', 'Unknown error')}"
                except Exception as e:
                    self.last_execution["tool_calls"].append({
                        "tool": "add_item_to_inventory",
                        "success": False,
                        "error": str(e)
                    })
                    return f"Error: {str(e)}"
            
            @tool
            def remove_item_from_inventory(user_id: str, item_name: str, quantity: int = 1) -> str:
                """Remove items from a user's inventory."""
                try:
                    result = inventory_tool_instance.remove_item(user_id, item_name, quantity)
                    self.last_execution["tool_calls"].append({
                        "tool": "remove_item_from_inventory",
                        "user_id": user_id,
                        "item_name": item_name,
                        "quantity": quantity,
                        "success": result.get("success", False)
                    })
                    if result.get("success"):
                        return f"✅ {result.get('message')}"
                    else:
                        return f"❌ {result.get('error', 'Unknown error')}"
                except Exception as e:
                    self.last_execution["tool_calls"].append({
                        "tool": "remove_item_from_inventory",
                        "success": False,
                        "error": str(e)
                    })
                    return f"Error: {str(e)}"
            
            @tool
            def create_trade(
                from_user_id: str,
                to_user_id: str,
                from_items_json: str,
                to_items_json: str,
                channel_id: str
            ) -> str:
                """
                Create a trade offer between two users.
                from_items_json: JSON string of items being offered (e.g., '{"sword": 1, "potion": 2}')
                to_items_json: JSON string of items being requested (e.g., '{"gold": 100}')
                This will create a Discord embed with Accept/Decline buttons.
                """
                try:
                    import json
                    from_items = json.loads(from_items_json) if from_items_json else {}
                    to_items = json.loads(to_items_json) if to_items_json else {}
                    
                    result = trade_tool_instance.create_trade(
                        from_user_id, to_user_id, from_items, to_items, channel_id
                    )
                    self.last_execution["tool_calls"].append({
                        "tool": "create_trade",
                        "from_user_id": from_user_id,
                        "to_user_id": to_user_id,
                        "success": result.get("success", False),
                        "trade_id": result.get("trade_id"),
                        "discord_data": result.get("discord_data")
                    })
                    if result.get("success"):
                        trade_summary = result.get("trade_summary", {})
                        return f"✅ Trade offer created!\n" \
                               f"**From:** {trade_summary.get('from_user')}\n" \
                               f"**To:** {trade_summary.get('to_user')}\n" \
                               f"**Offering:** {trade_summary.get('offering')}\n" \
                               f"**Requesting:** {trade_summary.get('requesting')}\n" \
                               f"\nTrade ID: {result.get('trade_id')}\n" \
                               f"The recipient can accept or decline via Discord embed buttons."
                    else:
                        return f"❌ {result.get('error', 'Unknown error')}"
                except json.JSONDecodeError as e:
                    return f"❌ Invalid JSON format: {str(e)}"
                except Exception as e:
                    self.last_execution["tool_calls"].append({
                        "tool": "create_trade",
                        "success": False,
                        "error": str(e)
                    })
                    return f"Error: {str(e)}"
            
            tools.extend([check_inventory, add_item_to_inventory, remove_item_from_inventory, create_trade])
            logger.info("✅ Inventory and trade tools added to ReActAgent")
        
        # Add D&D tools if available
        if DND_AVAILABLE:
            campaign_tool_instance = DnDCampaignTool()
            character_tool_instance = DnDCharacterTool()
            dice_tool_instance = DnDDiceTool()
            dm_tool_instance = DnDDMTool()
            
            @tool
            def start_dnd_campaign(campaign_name: str, dm_user_id: str, description: Optional[str] = None, theme: Optional[str] = None) -> str:
                """
                Start a new D&D campaign. The dm_user_id should be the Discord ID of the Dungeon Master.
                Use the user_id from context if not provided. Creates a Discord thread for the campaign.
                The LLM will generate the opening story based on the campaign name, theme, and description.
                
                Theme examples: "dark fantasy", "high magic", "horror", "steampunk", "medieval", "sword and sorcery"
                """
                try:
                    import asyncio
                    # Use context user_id if dm_user_id not provided
                    dm_id = dm_user_id or self.current_context.get("user_id", "unknown")
                    channel_id = self.current_context.get("channel_id")
                    
                    # Run async campaign creation with theme
                    loop = asyncio.get_event_loop()
                    result = loop.run_until_complete(
                        dm_tool_instance.start_campaign(campaign_name, dm_id, description, thread_id=None, channel_id=channel_id, theme=theme)
                    )
                    
                    self.last_execution["tool_calls"].append({
                        "tool": "start_dnd_campaign",
                        "campaign_name": campaign_name,
                        "success": result.get("success", False),
                        "campaign_id": result.get("campaign_id"),
                        "thread_id": result.get("thread_id")
                    })
                    
                    if result.get("success"):
                        campaign_id = result.get("campaign_id")
                        # Store campaign_id and thread_id for Discord bot to create thread
                        self.last_execution["tool_calls"][-1]["discord_data"] = {
                            "create_thread": True,
                            "campaign_name": campaign_name,
                            "campaign_id": campaign_id
                        }
                        return result.get("dm_message", f"Campaign '{campaign_name}' started!")
                    else:
                        return f"❌ {result.get('error', 'Unknown error')}"
                except Exception as e:
                    self.last_execution["tool_calls"].append({
                        "tool": "start_dnd_campaign",
                        "success": False,
                        "error": str(e)
                    })
                    return f"Error: {str(e)}"
            
            @tool
            def resume_dnd_campaign(campaign_name: str) -> str:
                """
                Resume a D&D campaign by name. Loads full campaign context including characters, turn order, and game state.
                Example: "let's play dnd, we were on the adventure mists of mangoria"
                """
                try:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    result = loop.run_until_complete(
                        dm_tool_instance.resume_campaign(campaign_name)
                    )
                    self.last_execution["tool_calls"].append({
                        "tool": "resume_dnd_campaign",
                        "campaign_name": campaign_name,
                        "success": result.get("success", False),
                        "campaign_id": result.get("campaign_id"),
                        "thread_id": result.get("campaign_data", {}).get("thread_id")
                    })
                    if result.get("success"):
                        return result.get("resume_message", f"Campaign '{campaign_name}' loaded!")
                    else:
                        return f"❌ {result.get('error', 'Unknown error')}"
                except Exception as e:
                    self.last_execution["tool_calls"].append({
                        "tool": "resume_dnd_campaign",
                        "success": False,
                        "error": str(e)
                    })
                    return f"Error: {str(e)}"
            
            @tool
            def create_dnd_character(
                discord_id: str,
                campaign_name: str,
                character_name: str,
                character_class: str,
                race: str,
                level: int = 1,
                background: Optional[str] = None,
                alignment: Optional[str] = None,
                image_url: Optional[str] = None
            ) -> str:
                """
                Create a D&D character for a specific campaign. Characters are campaign-specific.
                Use discord_id from context if not provided. Campaign name is REQUIRED.
                Optionally include an image_url for the character portrait (Discord attachment URL).
                
                Valid classes: Barbarian, Bard, Cleric, Druid, Fighter, Monk, Paladin, Ranger, Rogue, Sorcerer, Warlock, Wizard
                Valid races: Human, Elf, Dwarf, Halfling, Dragonborn, Gnome, Half-Elf, Half-Orc, Tiefling
                Valid alignments: Lawful Good, Neutral Good, Chaotic Good, Lawful Neutral, True Neutral, Chaotic Neutral, Lawful Evil, Neutral Evil, Chaotic Evil
                
                Character creation follows D&D 5e rules with validation.
                """
                try:
                    # Use context user_id if discord_id not provided
                    user_id = discord_id or self.current_context.get("user_id", "unknown")
                    
                    # Get image URL from context if available (Discord attachment)
                    if not image_url:
                        image_url = self.current_context.get("image_urls", [None])[0] if self.current_context.get("image_urls") else None
                    
                    # Get campaign_id (REQUIRED - characters are campaign-specific)
                    import asyncio
                    loop = asyncio.get_event_loop()
                    campaign_result = loop.run_until_complete(
                        campaign_tool_instance.load_campaign(campaign_name)
                    )
                    
                    if not campaign_result.get("success"):
                        return f"❌ Campaign '{campaign_name}' not found. Please create the campaign first."
                    
                    campaign_id = campaign_result.get("campaign_id")
                    
                    # Create character (campaign-specific, with validation)
                    result = loop.run_until_complete(
                        character_tool_instance.create_character(
                            user_id, campaign_id, character_name, character_class, race, level, background, None, alignment, image_url
                        )
                    )
                    self.last_execution["tool_calls"].append({
                        "tool": "create_dnd_character",
                        "character_name": character_name,
                        "success": result.get("success", False)
                    })
                    if result.get("success"):
                        char_data = result.get("character_data", {})
                        image_info = ""
                        if char_data.get("image_url"):
                            image_info = f"\n🖼️ Character image: {char_data.get('image_url')}"
                        
                        return f"✅ {result.get('message')}\n\n**Character Sheet:**\n" \
                               f"Name: {char_data.get('name')}\n" \
                               f"Class: {char_data.get('class')} {char_data.get('race')}\n" \
                               f"Level: {char_data.get('level')}\n" \
                               f"HP: {char_data.get('hit_points', {}).get('current')}/{char_data.get('hit_points', {}).get('max')}\n" \
                               f"Ability Scores: {', '.join([f'{k}: {v}' for k, v in char_data.get('ability_scores', {}).items()])}" \
                               f"{image_info}"
                    else:
                        return f"❌ {result.get('error', 'Unknown error')}"
                except Exception as e:
                    self.last_execution["tool_calls"].append({
                        "tool": "create_dnd_character",
                        "success": False,
                        "error": str(e)
                    })
                    return f"Error: {str(e)}"
            
            @tool
            def roll_dnd_dice(dice_notation: str, modifier: int = 0, advantage: bool = False, disadvantage: bool = False) -> str:
                """
                Roll D&D dice using standard notation (e.g., "2d6", "d20+5", "1d8+1d6").
                Supports advantage/disadvantage for d20 rolls.
                """
                try:
                    result = dice_tool_instance.roll_dice(dice_notation, modifier, advantage, disadvantage)
                    self.last_execution["tool_calls"].append({
                        "tool": "roll_dnd_dice",
                        "dice_notation": dice_notation,
                        "success": result.get("success", False)
                    })
                    if result.get("success"):
                        details = " + ".join(result.get("details", []))
                        return f"🎲 **Roll Result:** {result.get('total')}\n" \
                               f"Rolls: {details}\n" \
                               f"Modifier: {result.get('modifier', 0)}\n" \
                               f"{'🎯 Natural 20!' if result.get('natural_20') else ''}" \
                               f"{'💥 Natural 1!' if result.get('natural_1') else ''}"
                    else:
                        return f"❌ {result.get('error', 'Unknown error')}"
                except Exception as e:
                    self.last_execution["tool_calls"].append({
                        "tool": "roll_dnd_dice",
                        "success": False,
                        "error": str(e)
                    })
                    return f"Error: {str(e)}"
            
            @tool
            def dnd_action(campaign_name: str, action: str, character_name: Optional[str] = None) -> str:
                """
                Take an action in a D&D campaign. The action will be processed by the DM with appropriate dice rolls.
                Examples: "attack the goblin", "make a strength check", "cast fireball", "investigate the room"
                """
                try:
                    import asyncio
                    # Load campaign to get campaign_id
                    loop = asyncio.get_event_loop()
                    campaign_result = loop.run_until_complete(
                        campaign_tool_instance.load_campaign(campaign_name)
                    )
                    if not campaign_result.get("success"):
                        return f"❌ {campaign_result.get('error', 'Campaign not found')}"
                    
                    campaign_id = campaign_result.get("campaign_id")
                    user_id = self.current_context.get("user_id", "unknown")
                    
                    # Process action (auto-rolls dice if needed)
                    result = loop.run_until_complete(
                        dm_tool_instance.process_action(campaign_id, user_id, action, character_name)
                    )
                    self.last_execution["tool_calls"].append({
                        "tool": "dnd_action",
                        "campaign_name": campaign_name,
                        "action": action,
                        "success": result.get("success", False)
                    })
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
                    self.last_execution["tool_calls"].append({
                        "tool": "dnd_action",
                        "success": False,
                        "error": str(e)
                    })
                    return f"Error: {str(e)}"
            
            @tool
            def next_turn(campaign_name: str) -> str:
                """Advance to the next turn in combat/initiative order."""
                try:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    campaign_result = loop.run_until_complete(
                        campaign_tool_instance.load_campaign(campaign_name)
                    )
                    if not campaign_result.get("success"):
                        return f"❌ {campaign_result.get('error', 'Campaign not found')}"
                    
                    campaign_id = campaign_result.get("campaign_id")
                    result = loop.run_until_complete(
                        campaign_tool_instance.next_turn(campaign_id)
                    )
                    self.last_execution["tool_calls"].append({
                        "tool": "next_turn",
                        "campaign_name": campaign_name,
                        "success": result.get("success", False)
                    })
                    if result.get("success"):
                        return f"✅ Turn advanced to: {result.get('next_turn', 'Unknown')}"
                    else:
                        return f"❌ {result.get('error', 'Unknown error')}"
                except Exception as e:
                    self.last_execution["tool_calls"].append({
                        "tool": "next_turn",
                        "success": False,
                        "error": str(e)
                    })
                    return f"Error: {str(e)}"
            
            @tool
            def get_party_members(campaign_name: str) -> str:
                """Get all characters in the campaign party. Shows who's in the party."""
                try:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    result = loop.run_until_complete(
                        campaign_tool_instance.get_party_members(campaign_name)
                    )
                    
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
            
            tools.extend([
                start_dnd_campaign,
                resume_dnd_campaign,
                create_dnd_character,
                roll_dnd_dice,
                dnd_action,
                next_turn,
                get_party_members
            ])
            logger.info("✅ D&D tools added to ReActAgent (with party member listing)")
        
        # Add YouTube summarizer if available
        if YOUTUBE_AVAILABLE:
            @tool
            def summarize_youtube_tool(url: str, language_codes: Optional[str] = None) -> str:
                """
                Summarize a YouTube video by extracting and processing its transcript.
                Takes a YouTube URL and optional language codes (comma-separated, e.g., "en,es").
                Returns a summary of the video content.
                """
                try:
                    import asyncio
                    import concurrent.futures
                    
                    # Parse language codes if provided
                    lang_list = None
                    if language_codes:
                        lang_list = [lang.strip() for lang in language_codes.split(",")]
                    
                    async def _summarize():
                        return await summarize_youtube(
                            url=url,
                            language_codes=lang_list,
                            save_to_documents=False
                        )
                    
                    # Run async function in thread executor
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, _summarize())
                        result = future.result(timeout=300)  # 5 minute timeout
                    
                    self.last_execution["tool_calls"].append({
                        "tool": "summarize_youtube",
                        "url": url,
                        "success": result.get("success", False)
                    })
                    
                    if result.get("success"):
                        summary = result.get("summary", "")
                        transcript_length = result.get("transcript_length", 0)
                        return f"✅ YouTube video summarized!\n\n**Summary:**\n{summary}\n\n**Transcript Length:** {transcript_length} characters"
                    else:
                        return f"❌ {result.get('error', 'Unknown error')}"
                except Exception as e:
                    self.last_execution["tool_calls"].append({
                        "tool": "summarize_youtube",
                        "success": False,
                        "error": str(e)
                    })
                    return f"Error: {str(e)}"
            
            tools.append(summarize_youtube_tool)
            logger.info("✅ YouTube summarizer tool added to ReActAgent")
        
        # Add Website summarizer if available
        if WEBSITE_AVAILABLE:
            @tool
            def summarize_website_tool(url: str, max_length: int = 50000) -> str:
                """
                Summarize a website by extracting and processing its content.
                Takes a website URL and optional max_length (default 50000 characters).
                Returns a summary of the website content.
                """
                try:
                    import asyncio
                    import concurrent.futures
                    
                    async def _summarize():
                        return await summarize_website(
                            url=url,
                            max_length=max_length,
                            save_to_documents=False
                        )
                    
                    # Run async function in thread executor
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, _summarize())
                        result = future.result(timeout=300)  # 5 minute timeout
                    
                    self.last_execution["tool_calls"].append({
                        "tool": "summarize_website",
                        "url": url,
                        "success": result.get("success", False)
                    })
                    
                    if result.get("success"):
                        summary = result.get("summary", "")
                        content_length = result.get("content_length", 0)
                        return f"✅ Website summarized!\n\n**Summary:**\n{summary}\n\n**Content Length:** {content_length} characters"
                    else:
                        return f"❌ {result.get('error', 'Unknown error')}"
                except Exception as e:
                    self.last_execution["tool_calls"].append({
                        "tool": "summarize_website",
                        "success": False,
                        "error": str(e)
                    })
                    return f"Error: {str(e)}"
            
            tools.append(summarize_website_tool)
            logger.info("✅ Website summarizer tool added to ReActAgent")
        
        return tools
    
    def _setup_llm(self):
        """Configure LLM based on config."""
        if LLM_PROVIDER == "lmstudio":
            return ChatOpenAI(
                base_url=LMSTUDIO_BASE_URL,
                api_key="lm-studio",
                model=LMSTUDIO_MODEL,
                temperature=0
            )
        elif LLM_PROVIDER == "chutes":
            # Configure ChatOpenAI for Chutes API
            # Chutes supports OpenAI-compatible tool calling
            return ChatOpenAI(
                base_url=CHUTES_BASE_URL,
                api_key=CHUTES_API_KEY,
                model=CHUTES_MODEL,
                temperature=0,
                # Ensure proper tool serialization
                model_kwargs={}
            )
        else:
            return ChatOpenAI(
                base_url=OPENAI_BASE_URL,
                api_key=OPENAI_API_KEY,
                model=OPENAI_MODEL,
                temperature=0
            )
    
    def _truncate_message_content(self, content: str, max_chars: int = 50000) -> str:
        """
        Truncate individual message content if it's too long.
        
        Args:
            content: Message content to truncate
            max_chars: Maximum characters to keep
            
        Returns:
            Truncated content with indicator if truncated
        """
        if len(content) <= max_chars:
            return content
        
        # Keep the beginning and end, with truncation indicator
        half_max = max_chars // 2
        truncated = content[:half_max] + f"\n\n[... {len(content) - max_chars} characters truncated ...]\n\n" + content[-half_max:]
        return truncated
    
    def _truncate_messages(self, messages: List[BaseMessage], max_tokens: int = 100000) -> List[BaseMessage]:
        """
        Truncate messages to fit within token limit.
        Keeps system message and most recent messages.
        Also truncates individual message content if too large.
        
        Args:
            messages: List of messages to truncate
            max_tokens: Maximum tokens to keep (default 100k to leave room for response)
            
        Returns:
            Truncated list of messages
        """
        if not messages:
            return messages
        
        # Estimate tokens (rough: 1 token ≈ 4 characters, but be conservative)
        def estimate_tokens(text: str) -> int:
            # Use a more conservative estimate for safety
            return len(text) // 3
        
        # Separate system messages from others
        system_messages = [msg for msg in messages if isinstance(msg, SystemMessage)]
        other_messages = [msg for msg in messages if not isinstance(msg, SystemMessage)]
        
        # Find the first user message (original request) - this must be preserved
        first_user_message = None
        remaining_messages = []
        for msg in other_messages:
            if isinstance(msg, HumanMessage) and first_user_message is None:
                first_user_message = msg
            else:
                remaining_messages.append(msg)
        
        # Truncate individual message contents if they're extremely large
        # This handles cases where a single message has huge content (like image data or large outputs)
        max_message_chars = max_tokens * 3  # Rough conversion: tokens * 3 = chars
        processed_remaining = []
        for msg in remaining_messages:
            if hasattr(msg, 'content') and msg.content:
                content = msg.content
                # For tool messages, be more aggressive with truncation since they're often huge
                is_tool_message = isinstance(msg, ToolMessage)
                max_chars_for_msg = max_message_chars // 2 if is_tool_message else max_message_chars
                
                if len(content) > max_chars_for_msg:
                    logger.warning(f"Truncating large message content from {len(content)} to {max_chars_for_msg} characters")
                    content = self._truncate_message_content(content, max_chars_for_msg)
                    # Create new message with truncated content
                    if isinstance(msg, AIMessage):
                        processed_remaining.append(AIMessage(content=content))
                    elif isinstance(msg, HumanMessage):
                        processed_remaining.append(HumanMessage(content=content))
                    elif isinstance(msg, ToolMessage):
                        processed_remaining.append(ToolMessage(content=content, tool_call_id=getattr(msg, 'tool_call_id', '')))
                    else:
                        processed_remaining.append(type(msg)(content=content))
                else:
                    processed_remaining.append(msg)
            else:
                processed_remaining.append(msg)
        
        # Calculate system message tokens
        system_tokens = sum(estimate_tokens(msg.content if hasattr(msg, 'content') else str(msg)) 
                           for msg in system_messages)
        
        # Calculate first user message tokens (must keep this)
        user_tokens = 0
        if first_user_message:
            user_content = first_user_message.content if hasattr(first_user_message, 'content') else str(first_user_message)
            user_tokens = estimate_tokens(user_content)
        
        # Start with user message (must keep)
        truncated_others = []
        if first_user_message:
            truncated_others.append(first_user_message)
        current_tokens = system_tokens + user_tokens
        
        # Add remaining messages from the end (most recent first) until we hit token limit
        # Skip tool messages if they're too large - they're less critical than user requests
        messages_to_add = []
        for msg in reversed(processed_remaining):
            msg_content = msg.content if hasattr(msg, 'content') else str(msg)
            msg_tokens = estimate_tokens(msg_content)
            
            # Skip very large tool messages if we're running low on tokens
            if isinstance(msg, ToolMessage) and msg_tokens > max_tokens // 4:
                logger.debug(f"Skipping large tool message ({msg_tokens} tokens) to preserve user request")
                continue
            
            if current_tokens + msg_tokens > max_tokens:
                # Can't fit this message, stop
                break
            
            messages_to_add.insert(0, msg)  # Insert at beginning to maintain chronological order
            current_tokens += msg_tokens
        
        # Combine: user message first, then other messages in chronological order
        truncated_others.extend(messages_to_add)
        
        # Combine: system messages first, then truncated other messages
        truncated = system_messages + truncated_others
        
        # Ensure we always have at least system + user message
        min_expected = len(system_messages) + (1 if first_user_message else 0)
        if len(truncated) < min_expected:
            logger.error(f"Truncation too aggressive! Lost user message. Original: {len(messages)} messages, Result: {len(truncated)} messages")
            # Force keep at least system + user message
            if first_user_message:
                truncated = system_messages + [first_user_message]
                logger.warning("Forced to keep only system message and user request due to extreme truncation")
        
        if len(truncated) < len(messages):
            logger.warning(f"Truncated messages from {len(messages)} to {len(truncated)} to fit token limit ({current_tokens} estimated tokens)")
        
        return truncated
    
    def _build_graph(self):
        """Build the LangGraph with step tracking."""
        from langchain_core.tools import BaseTool
        
        # Validate and filter tools to ensure they're proper BaseTool instances
        valid_tools = []
        for t in self.tools:
            if isinstance(t, BaseTool):
                # Ensure tool has required attributes and is properly formatted
                try:
                    # Check if tool has name attribute and it's not empty
                    if hasattr(t, 'name') and t.name:
                        # Verify tool can be serialized (some APIs require this)
                        # Try to access name as attribute (not dict key)
                        tool_name = t.name if hasattr(t, 'name') else None
                        if tool_name:
                            valid_tools.append(t)
                        else:
                            logger.warning(f"Tool has empty name: {type(t)}")
                    else:
                        logger.warning(f"Skipping tool without name attribute: {type(t)}")
                except Exception as e:
                    logger.warning(f"Error validating tool {type(t)}: {e}, skipping")
            else:
                logger.warning(f"Skipping non-BaseTool: {type(t)}")
        
        if not valid_tools:
            logger.warning("No valid tools available")
            llm_with_tools = self.llm
        elif ReActAgent._tool_binding_failed:
            # Skip tool binding if we've seen it fail before (avoids repeated errors)
            logger.info("Skipping tool binding - previous attempts failed with serialization errors")
            llm_with_tools = self.llm
        else:
            try:
                # Use LangChain's built-in tool conversion to ensure proper format
                # This should handle Chutes API compatibility better
                tool_names = [t.name for t in valid_tools if hasattr(t, 'name')]
                logger.info(f"Binding {len(valid_tools)} tools to LLM: {tool_names}")
                
                # Ensure all tools have proper schemas before binding
                # LangChain's bind_tools should handle serialization, but we ensure tools are valid
                for tool in valid_tools:
                    if not hasattr(tool, 'name') or not tool.name:
                        logger.warning(f"Tool missing name attribute: {type(tool)}")
                    if not hasattr(tool, 'description'):
                        logger.warning(f"Tool {tool.name if hasattr(tool, 'name') else 'unknown'} missing description")
                    # Ensure tool has args_schema or args for proper serialization
                    if not hasattr(tool, 'args_schema') and not hasattr(tool, 'args'):
                        logger.debug(f"Tool {tool.name if hasattr(tool, 'name') else 'unknown'} has no args_schema - this is OK for @tool decorator")
                
                # Use bind_tools - LangChain should handle serialization correctly
                # If this fails, it's likely a Chutes API compatibility issue
                try:
                    llm_with_tools = self.llm.bind_tools(valid_tools)
                    logger.debug(f"Successfully bound {len(valid_tools)} tools to LLM")
                except Exception as bind_error:
                    # Log the error details for debugging
                    error_msg = str(bind_error)
                    logger.error(f"Tool binding error: {bind_error}", exc_info=True)
                    
                    # Check if it's a serialization issue
                    if "'dict object' has no attribute 'name'" in error_msg or "name" in error_msg.lower():
                        logger.warning("Tool serialization error detected - Chutes API may have compatibility issues with LangChain tool format")
                        logger.warning("This is a known issue with some OpenAI-compatible APIs")
                        ReActAgent._tool_binding_failed = True
                        llm_with_tools = self.llm
                    else:
                        # Re-raise if it's a different error
                        raise
                    
            except Exception as e:
                logger.error(f"Error binding tools: {e}", exc_info=True)
                logger.warn("Continuing without tool binding - some features may not work")
                llm_with_tools = self.llm
        
        def call_model(state):
            messages = state['messages']
            
            step = {
                "type": "thought",
                "timestamp": time.time(),
                "content": messages[-1].content if messages else "Initial message"
            }
            self.last_execution["steps"].append(step)
            
            # Clean messages to ensure tool_calls are in proper format
            # LangChain expects tool_calls to be objects, not dicts
            cleaned_messages = []
            for msg in messages:
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    # Check if tool_calls contain dicts that need conversion
                    needs_cleaning = False
                    for tc in msg.tool_calls:
                        if isinstance(tc, dict):
                            needs_cleaning = True
                            break
                    
                    if needs_cleaning:
                        # Convert dict tool_calls to proper format
                        # LangChain's AIMessage expects tool_calls to be dictionaries with "name", "args", and "id" keys
                        cleaned_tool_calls = []
                        for tc in msg.tool_calls:
                            if isinstance(tc, dict):
                                # Extract name and args from dict format
                                name = tc.get("name", "")
                                if not name and "function" in tc:
                                    name = tc["function"].get("name", "") if isinstance(tc["function"], dict) else ""
                                
                                args = tc.get("args", tc.get("arguments", {}))
                                if not args and "function" in tc:
                                    func_args = tc["function"].get("arguments", {}) if isinstance(tc["function"], dict) else {}
                                    if isinstance(func_args, str):
                                        import json
                                        try:
                                            args = json.loads(func_args)
                                        except:
                                            args = {}
                                    else:
                                        args = func_args
                                
                                # Create a proper ToolCall object that LangChain can serialize
                                # Try to use LangChain's ToolCall class if available, otherwise create dict-like object
                                try:
                                    # Check if ToolCall is a class we can instantiate
                                    if isinstance(ToolCall, type) and hasattr(ToolCall, '__call__'):
                                        # It's a class, try to instantiate it
                                        cleaned_tool_calls.append(ToolCall(
                                            name=name or "unknown",
                                            args=args or {},
                                            id=tc.get("id", "")
                                        ))
                                    else:
                                        # ToolCall is a TypedDict, create a dict subclass with attributes
                                        class ToolCallDict(dict):
                                            """Dict subclass that also supports attribute access"""
                                            def __init__(self, name: str, args: dict, id: str):
                                                super().__init__(name=name, args=args, id=id)
                                                self.name = name
                                                self.args = args
                                                self.id = id
                                        
                                        cleaned_tool_calls.append(ToolCallDict(
                                            name=name or "unknown",
                                            args=args or {},
                                            id=tc.get("id", "")
                                        ))
                                except (TypeError, AttributeError) as e:
                                    # Fallback: create a dict subclass with attributes
                                    class ToolCallDict(dict):
                                        """Dict subclass that also supports attribute access"""
                                        def __init__(self, name: str, args: dict, id: str):
                                            super().__init__(name=name, args=args, id=id)
                                            self.name = name
                                            self.args = args
                                            self.id = id
                                    
                                    cleaned_tool_calls.append(ToolCallDict(
                                        name=name or "unknown",
                                        args=args or {},
                                        id=tc.get("id", "")
                                    ))
                            else:
                                cleaned_tool_calls.append(tc)
                        
                        # Create new message with cleaned tool_calls
                        if isinstance(msg, AIMessage):
                            # Create new AIMessage with cleaned tool_calls
                            cleaned_messages.append(AIMessage(content=msg.content, tool_calls=cleaned_tool_calls))
                        else:
                            # For other message types, remove tool_calls to avoid issues
                            cleaned_messages.append(type(msg)(content=msg.content if hasattr(msg, 'content') else ""))
                    else:
                        cleaned_messages.append(msg)
                else:
                    cleaned_messages.append(msg)
            
            try:
                response = llm_with_tools.invoke(cleaned_messages)
            except Exception as e:
                error_msg = str(e)
                error_type = type(e).__name__
                logger.error(f"Error in call_model: {error_type} - {error_msg}", exc_info=True)
                
                # Check if error is related to context length
                is_context_error = (
                    "context length" in error_msg.lower() or
                    "longer than" in error_msg.lower() and "token" in error_msg.lower() or
                    "max_tokens" in error_msg.lower() or
                    "too long" in error_msg.lower()
                )
                
                # Check if error is related to tool binding/serialization
                is_tool_error = (
                    ("name" in error_msg.lower() and "attribute" in error_msg.lower()) or 
                    ("tool" in error_msg.lower() and "dict" in error_msg.lower()) or
                    ("dict object" in error_msg.lower() and "name" in error_msg.lower())
                )
                
                # If this is a tool binding error, mark it so we skip binding in future
                if is_tool_error:
                    ReActAgent._tool_binding_failed = True
                    logger.warning("Tool binding marked as failed - will skip binding in future graph builds")
                
                if is_context_error or is_tool_error:
                    logger.warning(f"{'Context length' if is_context_error else 'Tool binding/serialization'} error detected, retrying with truncated messages and without tools...")
                    try:
                        # Remove tool_calls from messages if present to avoid format issues
                        cleaned_messages_no_tools = []
                        system_msg_updated = False
                        for msg in messages:
                            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                                # Create new message without tool_calls to avoid format issues
                                if hasattr(msg, 'content'):
                                    if isinstance(msg, AIMessage):
                                        cleaned_messages_no_tools.append(AIMessage(content=msg.content))
                                    elif isinstance(msg, HumanMessage):
                                        cleaned_messages_no_tools.append(HumanMessage(content=msg.content))
                                    elif isinstance(msg, SystemMessage):
                                        # Update system message to include tool info even when tool binding failed
                                        if not system_msg_updated and is_tool_error:
                                            from langchain_core.tools import BaseTool
                                            available_tools = [t for t in self.tools if isinstance(t, BaseTool)]
                                            tool_list = ", ".join([t.name for t in available_tools if hasattr(t, 'name')])
                                            updated_content = msg.content
                                            if tool_list and "Available Tools:" not in updated_content:
                                                updated_content += f"\n\nNote: Tool calling is temporarily unavailable, but you have access to these tools: {tool_list}. Please inform the user about available capabilities."
                                            cleaned_messages_no_tools.append(SystemMessage(content=updated_content))
                                            system_msg_updated = True
                                        else:
                                            cleaned_messages_no_tools.append(SystemMessage(content=msg.content))
                                    else:
                                        # Create a copy without tool_calls
                                        msg_copy = type(msg)(content=msg.content)
                                        cleaned_messages_no_tools.append(msg_copy)
                                else:
                                    cleaned_messages_no_tools.append(msg)
                            else:
                                # Update system message if it's the first one and we have tool errors
                                if isinstance(msg, SystemMessage) and not system_msg_updated and is_tool_error:
                                    from langchain_core.tools import BaseTool
                                    available_tools = [t for t in self.tools if isinstance(t, BaseTool)]
                                    tool_list = ", ".join([t.name for t in available_tools if hasattr(t, 'name')])
                                    updated_content = msg.content
                                    if tool_list and "Available Tools:" not in updated_content and "temporarily unavailable" not in updated_content:
                                        updated_content += f"\n\nNote: Tool calling is temporarily unavailable, but you have access to these tools: {tool_list}. Please inform the user about available capabilities."
                                    cleaned_messages_no_tools.append(SystemMessage(content=updated_content))
                                    system_msg_updated = True
                                else:
                                    cleaned_messages_no_tools.append(msg)
                        
                        # Always truncate when retrying without tools (messages might be huge even if few in number)
                        # Use more aggressive truncation for tool error retries
                        truncation_limit = 80000 if is_tool_error else 100000
                        cleaned_messages_no_tools = self._truncate_messages(cleaned_messages_no_tools, max_tokens=truncation_limit)
                        
                        response = self.llm.invoke(cleaned_messages_no_tools)
                        logger.info("Successfully retried with truncated messages and without tools")
                    except Exception as e2:
                        logger.error(f"Error in fallback LLM call: {e2}", exc_info=True)
                        # Try with even more aggressive truncation
                        try:
                            very_short_messages = self._truncate_messages(cleaned_messages_no_tools, max_tokens=50000)
                            response = self.llm.invoke(very_short_messages)
                            logger.info("Successfully retried with heavily truncated messages")
                        except Exception as e3:
                            logger.error(f"Error in second fallback LLM call: {e3}", exc_info=True)
                            # Last resort: keep only system message and most recent user message
                            try:
                                system_msgs = [msg for msg in messages if isinstance(msg, SystemMessage)]
                                user_msgs = [msg for msg in messages if isinstance(msg, HumanMessage)]
                                if user_msgs:
                                    last_user_msg = user_msgs[-1]
                                    # Truncate content if needed
                                    if hasattr(last_user_msg, 'content') and len(last_user_msg.content) > 10000:
                                        truncated_content = self._truncate_message_content(last_user_msg.content, 10000)
                                        last_user_msg = HumanMessage(content=truncated_content)
                                    minimal_messages = system_msgs + [last_user_msg]
                                    response = self.llm.invoke(minimal_messages)
                                    logger.info("Successfully retried with minimal messages (system + last user message)")
                                else:
                                    raise e3
                            except Exception as e4:
                                logger.error(f"Error in minimal fallback LLM call: {e4}", exc_info=True)
                                # Return error message
                                response = AIMessage(content=f"I encountered an error processing your request. The conversation history is too long. Please try starting a new conversation or rephrasing your request.")
                else:
                    # Other error, try fallback
                    try:
                        # Truncate if messages are very long
                        fallback_messages = messages
                        if len(messages) > 50:
                            fallback_messages = self._truncate_messages(messages, max_tokens=100000)
                        response = self.llm.invoke(fallback_messages)
                    except Exception as e2:
                        logger.error(f"Error in fallback LLM call: {e2}", exc_info=True)
                        response = AIMessage(content=f"I encountered an error: {error_msg}. Please try again.")
            
            if hasattr(response, 'tool_calls') and response.tool_calls:
                action_step = {
                    "type": "action",
                    "timestamp": time.time(),
                    "tool_calls": [
                        {
                            "name": tc.get("name", "") if isinstance(tc, dict) else (getattr(tc, "name", "") if hasattr(tc, "name") else ""),
                            "arguments": tc.get("args", tc.get("arguments", {})) if isinstance(tc, dict) else (getattr(tc, "args", getattr(tc, "arguments", {})) if hasattr(tc, "args") or hasattr(tc, "arguments") else {})
                        }
                        for tc in response.tool_calls
                    ]
                }
                self.last_execution["steps"].append(action_step)
            
            return {"messages": [response]}
        
        def execute_tools(state):
            """Execute tools and track observations."""
            from langchain_core.tools import BaseTool
            valid_tools = [t for t in self.tools if isinstance(t, BaseTool)]
            tool_node = ToolNode(valid_tools)
            tool_results = tool_node.invoke(state)
            
            # Also check the previous AI message to get tool call names
            messages = state.get("messages", [])
            tool_call_map = {}
            for msg in messages:
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tc_id = tc.get("id", "") if isinstance(tc, dict) else (getattr(tc, "id", "") if hasattr(tc, "id") else "")
                        tc_name = tc.get("name", "") if isinstance(tc, dict) else (getattr(tc, "name", "") if hasattr(tc, "name") else "")
                        if tc_id:
                            tool_call_map[tc_id] = tc_name
            
            for tool_message in tool_results.get("messages", []):
                if isinstance(tool_message, ToolMessage):
                    # Extract tool name safely - ToolMessage may have name as attribute or in tool_call_id
                    tool_name = "unknown"
                    tool_call_id = None
                    
                    if hasattr(tool_message, 'tool_call_id'):
                        tool_call_id = tool_message.tool_call_id
                        tool_name = tool_call_map.get(str(tool_call_id), "unknown")
                    elif hasattr(tool_message, 'name') and tool_message.name:
                        tool_name = tool_message.name
                    elif isinstance(tool_message, dict):
                        tool_call_id = tool_message.get('tool_call_id')
                        tool_name = tool_message.get('name', tool_call_map.get(str(tool_call_id) if tool_call_id else "", 'unknown'))
                    
                    # For generate_image tool, try to extract the full result from tool_calls if available
                    if tool_name == "generate_image_tool" or tool_name == "generate_image":
                        # Check if we already have the result stored in last_execution["tool_calls"]
                        for tc_entry in self.last_execution.get("tool_calls", []):
                            if tc_entry.get("tool") == "generate_image" and tc_entry.get("result"):
                                logger.debug(f"Found generate_image result in tool_calls, result keys: {list(tc_entry['result'].keys()) if isinstance(tc_entry['result'], dict) else 'not_dict'}")
                                break
                    
                    observation_step = {
                        "type": "observation",
                        "timestamp": time.time(),
                        "tool": tool_name,
                        "result": str(tool_message.content if hasattr(tool_message, 'content') else tool_message.get('content', ''))[:500]
                    }
                    self.last_execution["steps"].append(observation_step)
            
            return tool_results
        
        workflow = StateGraph(AgentState)
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", execute_tools)
        workflow.set_entry_point("agent")
        
        def should_continue(state):
            messages = state['messages']
            last_message = messages[-1]
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                return "tools"
            return END
        
        workflow.add_conditional_edges("agent", should_continue)
        workflow.add_edge("tools", "agent")
        
        return workflow.compile()
    
    def run(self, message: str, context: Dict[str, Any] = None) -> str:
        """
        Run the agent on a message with ReAct pattern.
        Implements Thought -> Action -> Observation loop.
        """
        # Reset execution tracking
        self.last_execution = {
            "steps": [],
            "tool_calls": [],
            "final_result": None
        }
        
        channel_id = context.get("channel_id") or context.get("channelId", "unknown") if context else "unknown"
        user_id = context.get("userId") or context.get("user_id", "unknown") if context else "unknown"
        is_admin = context.get("isAdmin") or context.get("is_admin", False) if context else False
        image_urls = context.get("imageUrls") or context.get("image_urls", []) if context else []
        
        # Store context for tools to access
        self.current_context = {
            "user_id": user_id,
            "channel_id": channel_id,
            "is_admin": is_admin,
            "image_urls": image_urls,
            "imageUrls": image_urls  # Also store as imageUrls for compatibility
        }
        
        # Update tool factory context if it exists
        if hasattr(self, '_tool_factory'):
            self._tool_factory.context = self.current_context
        
        # Get available tool names and descriptions
        from langchain_core.tools import BaseTool
        available_tools = [t for t in self.tools if isinstance(t, BaseTool)]
        tool_descriptions = []
        for tool in available_tools:
            if hasattr(tool, 'name') and hasattr(tool, 'description'):
                tool_descriptions.append(f"- {tool.name}: {tool.description}")
        
        tools_info = ""
        if tool_descriptions:
            tools_info = f"\n\nAvailable Tools:\n" + "\n".join(tool_descriptions) + "\n\nYou can use these tools by calling them when needed."
        
        # Build system prompt with explicit tool selection guidance
        system_prompt = f"""You are a helpful AI assistant with access to tools. Use the ReAct pattern:
1. **Thought**: Analyze the user's request and determine what tools (if any) are needed
2. **Action**: Use the appropriate tools based on your analysis
3. **Observation**: Analyze the tool results
4. Repeat until you have the final answer

**Tool Selection Guidelines:**
- If the user provides a YouTube URL or asks about a YouTube video → use `summarize_youtube`
- If the user provides a website URL or asks to summarize a website → use `summarize_website`
- If the user asks to generate/create/draw an image → use `generate_image`
- If the user provides an image attachment or asks about an image → use `analyze_image`
- If the user asks a calculation, math problem, or data analysis question → use `run_python`
- If the user wants to save important information → use `save_core_memory`
- If the user asks about past conversations or preferences → use `get_core_memory`
- If the user mentions inventory, items, or trading → use inventory tools
- If the user mentions D&D, campaigns, characters, or dice → use D&D tools
- For general questions without specific tool needs, answer directly without tools

**Important:** Always analyze the user's request first. Don't use tools unless they're actually needed. If the user is just chatting or asking a simple question, answer directly.

Context:
- Channel ID: {channel_id}
- User ID: {user_id}
- Image URLs: {image_urls if image_urls else 'None'}
{tools_info}

Think step by step, analyze what tools are needed (if any), use them appropriately, and provide a clear final answer."""
        
        inputs = {
            "messages": [
                SystemMessage(content=system_prompt),
                HumanMessage(content=message)
            ]
        }
        
        try:
            logger.debug(f"Invoking ReAct graph with {len(inputs['messages'])} messages")
            final_state = self.graph.invoke(inputs)
            logger.debug(f"Graph execution completed. Final state has {len(final_state.get('messages', []))} messages")
            
            final_message = final_state['messages'][-1]
            result_content = final_message.content if hasattr(final_message, 'content') else str(final_message)
            
            self.last_execution["final_result"] = result_content
            logger.info(f"ReAct agent completed successfully. Result: {result_content[:200]}...")
            
            return self.last_execution["final_result"]
        except Exception as e:
            logger.error(f"ReAct agent error: {e}", exc_info=True)
            self.last_execution["final_result"] = f"Error: {str(e)}"
            return f"I encountered an error while processing your request: {str(e)}"

