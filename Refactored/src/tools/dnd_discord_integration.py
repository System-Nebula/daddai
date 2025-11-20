"""
D&D Discord Integration - Handles Discord thread creation and turn-based message filtering.
"""
from typing import Dict, Any, Optional
from Refactored.logger_config import logger


class DnDDiscordIntegration:
    """
    Handles Discord-specific D&D features:
    - Thread creation for campaigns
    - Turn-based message filtering
    - Campaign thread management
    """
    
    @staticmethod
    async def create_campaign_thread(
        message,
        campaign_name: str,
        campaign_id: str
    ) -> Optional[str]:
        """
        Create a Discord thread for a D&D campaign.
        
        Args:
            message: Discord message object to create thread from
            campaign_name: Campaign name
            campaign_id: Campaign ID
            
        Returns:
            Thread ID or None if creation failed
        """
        try:
            # Check if message is in a TextChannel (not DM)
            if hasattr(message.channel, 'create_thread'):
                thread = await message.channel.create_thread(
                    name=f"🎲 {campaign_name}",
                    auto_archive_duration=10080,  # 7 days
                    reason=f"D&D Campaign: {campaign_name}"
                )
                logger.info(f"Created Discord thread for campaign {campaign_name}: {thread.id}")
                return thread.id
            else:
                logger.warning("Cannot create thread - channel doesn't support threads")
                return None
        except Exception as e:
            logger.error(f"Error creating campaign thread: {e}", exc_info=True)
            return None
    
    @staticmethod
    def should_allow_message(
        message_user_id: str,
        campaign_data: Dict[str, Any],
        bot_user_id: str
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a message should be allowed based on turn order.
        Bot messages are always allowed.
        
        Args:
            message_user_id: User ID of message author
            campaign_data: Campaign data with turn order
            bot_user_id: Bot's user ID
            
        Returns:
            Tuple of (allowed: bool, reason: Optional[str])
        """
        # Bot messages are always allowed
        if message_user_id == bot_user_id:
            return True, None
        
        # If no turn order set, allow all messages
        turn_order = campaign_data.get("turn_order", [])
        current_turn = campaign_data.get("current_turn")
        
        if not turn_order or not current_turn:
            return True, None
        
        # Check if it's the current turn
        # Turn order can contain character names or user IDs
        # We need to check if the user's character is in the current turn
        
        # For now, allow if turn order is set but we'll enhance this
        # to check character ownership
        
        # TODO: Map user_id to character name and check if that character is current_turn
        # For now, allow all messages but log turn information
        return True, None  # Allow for now, will be enhanced with character mapping
    
    @staticmethod
    def get_turn_notification(campaign_data: Dict[str, Any]) -> Optional[str]:
        """
        Get a notification message for whose turn it is.
        
        Args:
            campaign_data: Campaign data
            
        Returns:
            Turn notification message or None
        """
        current_turn = campaign_data.get("current_turn")
        turn_order = campaign_data.get("turn_order", [])
        
        if current_turn and turn_order:
            return f"🎯 **It's {current_turn}'s turn!**"
        return None

