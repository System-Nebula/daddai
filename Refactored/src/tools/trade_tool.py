"""
Trade Tool - Manages trading system between users.
Creates trade offers with Discord embeds and handles trade execution.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
from src.utils.user_state_manager import UserStateManager
from Refactored.logger_config import logger


class TradeTool:
    """
    Tool for managing trades between users.
    Creates trade offers that require Discord embed Accept/Decline buttons.
    """
    
    def __init__(self):
        self.state_manager = UserStateManager()
        self._initialize_trade_schema()
    
    def _initialize_trade_schema(self):
        """Initialize trade storage schema."""
        # UserStateManager handles schema initialization
        pass
    
    def create_trade(
        self,
        from_user_id: str,
        to_user_id: str,
        from_items: Dict[str, int],
        to_items: Dict[str, int],
        channel_id: str,
        message_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a trade offer.
        
        Args:
            from_user_id: User initiating the trade
            to_user_id: User receiving the trade offer
            from_items: Items the initiator is offering (item_name: quantity)
            to_items: Items the initiator wants from the recipient (item_name: quantity)
            channel_id: Discord channel ID where trade was initiated
            message_id: Optional Discord message ID for the trade embed
            
        Returns:
            Trade data including trade_id for Discord embed buttons
        """
        try:
            # Validate trade
            if not from_items and not to_items:
                return {
                    "success": False,
                    "error": "Trade must include at least one item from either party"
                }
            
            if from_user_id == to_user_id:
                return {
                    "success": False,
                    "error": "Cannot trade with yourself"
                }
            
            # Check if initiator has the items they're offering
            inventory_tool = self._get_inventory_tool()
            for item_name, quantity in from_items.items():
                check_result = inventory_tool.check_item_quantity(from_user_id, item_name)
                if not check_result.get("success") or check_result.get("quantity", 0) < quantity:
                    return {
                        "success": False,
                        "error": f"You don't have enough {item_name}. You have {check_result.get('quantity', 0)}, but need {quantity}"
                    }
            
            # Check if recipient has the items being requested
            for item_name, quantity in to_items.items():
                check_result = inventory_tool.check_item_quantity(to_user_id, item_name)
                if not check_result.get("success") or check_result.get("quantity", 0) < quantity:
                    return {
                        "success": False,
                        "error": f"{to_user_id} doesn't have enough {item_name}. They have {check_result.get('quantity', 0)}, but you requested {quantity}"
                    }
            
            # Create trade record
            trade_id = f"trade_{from_user_id}_{to_user_id}_{datetime.now().timestamp()}"
            trade_data = {
                "trade_id": trade_id,
                "from_user_id": from_user_id,
                "to_user_id": to_user_id,
                "from_items": from_items,
                "to_items": to_items,
                "channel_id": channel_id,
                "message_id": message_id,
                "status": "pending",  # pending, accepted, declined, expired
                "created_at": datetime.now().isoformat(),
                "expires_at": None  # Could add expiration logic
            }
            
            # Store trade
            self.state_manager.set_user_state(
                f"trade_{trade_id}",
                "trade_data",
                trade_data,
                metadata={"action": "create_trade"}
            )
            
            # Format items for display
            from_items_str = ", ".join([f"{qty}x {item}" for item, qty in from_items.items()]) if from_items else "Nothing"
            to_items_str = ", ".join([f"{qty}x {item}" for item, qty in to_items.items()]) if to_items else "Nothing"
            
            return {
                "success": True,
                "trade_id": trade_id,
                "message": f"Trade offer created! {to_user_id} can accept or decline.",
                "trade_summary": {
                    "from_user": from_user_id,
                    "to_user": to_user_id,
                    "offering": from_items_str,
                    "requesting": to_items_str
                },
                "discord_data": {
                    "trade_id": trade_id,
                    "from_user_id": from_user_id,
                    "to_user_id": to_user_id,
                    "from_items": from_items,
                    "to_items": to_items,
                    "channel_id": channel_id
                }
            }
        except Exception as e:
            logger.error(f"Error creating trade: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error creating trade: {str(e)}"
            }
    
    def accept_trade(self, trade_id: str, accepting_user_id: str) -> Dict[str, Any]:
        """
        Accept a trade offer.
        
        Args:
            trade_id: Trade ID
            accepting_user_id: User accepting the trade
            
        Returns:
            Success status and trade execution result
        """
        try:
            # Get trade data
            trade_data = self.state_manager.get_user_state(f"trade_{trade_id}", "trade_data")
            if not trade_data:
                return {
                    "success": False,
                    "error": "Trade not found or has expired"
                }
            
            # Check if trade is still pending
            if trade_data.get("status") != "pending":
                return {
                    "success": False,
                    "error": f"Trade is already {trade_data.get('status')}"
                }
            
            # Verify the accepting user is the recipient
            if accepting_user_id != trade_data.get("to_user_id"):
                return {
                    "success": False,
                    "error": "Only the trade recipient can accept this trade"
                }
            
            # Execute trade
            inventory_tool = self._get_inventory_tool()
            
            # Transfer items from initiator to recipient
            for item_name, quantity in trade_data.get("from_items", {}).items():
                transfer_result = inventory_tool.transfer_item(
                    trade_data["from_user_id"],
                    trade_data["to_user_id"],
                    item_name,
                    quantity
                )
                if not transfer_result.get("success"):
                    return {
                        "success": False,
                        "error": f"Trade failed: {transfer_result.get('error')}"
                    }
            
            # Transfer items from recipient to initiator
            for item_name, quantity in trade_data.get("to_items", {}).items():
                transfer_result = inventory_tool.transfer_item(
                    trade_data["to_user_id"],
                    trade_data["from_user_id"],
                    item_name,
                    quantity
                )
                if not transfer_result.get("success"):
                    # Rollback: try to reverse the first transfer
                    # This is a simplified rollback - in production, use transactions
                    logger.warning(f"Trade rollback needed for trade {trade_id}")
                    return {
                        "success": False,
                        "error": f"Trade partially failed: {transfer_result.get('error')}. Some items may have been transferred."
                    }
            
            # Update trade status
            trade_data["status"] = "accepted"
            trade_data["accepted_at"] = datetime.now().isoformat()
            self.state_manager.set_user_state(
                f"trade_{trade_id}",
                "trade_data",
                trade_data,
                metadata={"action": "accept_trade", "accepted_by": accepting_user_id}
            )
            
            return {
                "success": True,
                "message": "Trade accepted and completed!",
                "trade_id": trade_id,
                "from_user": trade_data["from_user_id"],
                "to_user": trade_data["to_user_id"]
            }
        except Exception as e:
            logger.error(f"Error accepting trade: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error accepting trade: {str(e)}"
            }
    
    def decline_trade(self, trade_id: str, declining_user_id: str) -> Dict[str, Any]:
        """
        Decline a trade offer.
        
        Args:
            trade_id: Trade ID
            declining_user_id: User declining the trade
            
        Returns:
            Success status
        """
        try:
            # Get trade data
            trade_data = self.state_manager.get_user_state(f"trade_{trade_id}", "trade_data")
            if not trade_data:
                return {
                    "success": False,
                    "error": "Trade not found or has expired"
                }
            
            # Check if trade is still pending
            if trade_data.get("status") != "pending":
                return {
                    "success": False,
                    "error": f"Trade is already {trade_data.get('status')}"
                }
            
            # Verify the declining user is the recipient
            if declining_user_id != trade_data.get("to_user_id"):
                return {
                    "success": False,
                    "error": "Only the trade recipient can decline this trade"
                }
            
            # Update trade status
            trade_data["status"] = "declined"
            trade_data["declined_at"] = datetime.now().isoformat()
            self.state_manager.set_user_state(
                f"trade_{trade_id}",
                "trade_data",
                trade_data,
                metadata={"action": "decline_trade", "declined_by": declining_user_id}
            )
            
            return {
                "success": True,
                "message": "Trade declined",
                "trade_id": trade_id
            }
        except Exception as e:
            logger.error(f"Error declining trade: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error declining trade: {str(e)}"
            }
    
    def get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """
        Get trade data by trade_id.
        
        Args:
            trade_id: Trade ID
            
        Returns:
            Trade data or None
        """
        try:
            return self.state_manager.get_user_state(f"trade_{trade_id}", "trade_data")
        except Exception as e:
            logger.error(f"Error getting trade: {e}", exc_info=True)
            return None
    
    def _get_inventory_tool(self):
        """Lazy import to avoid circular dependencies."""
        from Refactored.src.tools.inventory_tool import InventoryTool
        return InventoryTool()

