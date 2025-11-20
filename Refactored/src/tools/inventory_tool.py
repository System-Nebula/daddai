"""
Inventory Tool - Manages user backpack/inventory system.
Tracks items for each user with permission checks.
"""
from typing import Dict, Any, Optional, List
from src.utils.user_state_manager import UserStateManager
from Refactored.logger_config import logger


class InventoryTool:
    """
    Tool for managing user inventories/backpacks.
    Users can only view their own inventory unless they're admins.
    """
    
    def __init__(self):
        self.state_manager = UserStateManager()
        self._initialize_inventory_schema()
    
    def _initialize_inventory_schema(self):
        """Initialize inventory storage schema."""
        # UserStateManager handles schema initialization
        pass
    
    def get_inventory(self, user_id: str, requesting_user_id: str, is_admin: bool = False) -> Dict[str, Any]:
        """
        Get a user's inventory.
        
        Args:
            user_id: The user whose inventory to retrieve
            requesting_user_id: The user making the request
            is_admin: Whether the requesting user is an admin
            
        Returns:
            Dictionary with inventory data or error message
        """
        # Permission check: users can only view their own inventory unless admin
        if user_id != requesting_user_id and not is_admin:
            return {
                "success": False,
                "error": "You can only view your own inventory. Admins can view any user's inventory."
            }
        
        try:
            inventory = self.state_manager.get_user_state(user_id, "inventory", default={"items": {}})
            
            # Ensure inventory has proper structure
            if not isinstance(inventory, dict):
                inventory = {"items": {}}
            if "items" not in inventory:
                inventory["items"] = {}
            
            # Format items for display
            items_list = []
            for item_name, quantity in inventory["items"].items():
                if quantity > 0:
                    items_list.append(f"{item_name}: {quantity}")
            
            return {
                "success": True,
                "user_id": user_id,
                "inventory": inventory,
                "items_display": items_list if items_list else ["Empty"],
                "total_items": sum(inventory["items"].values()) if inventory.get("items") else 0
            }
        except Exception as e:
            logger.error(f"Error getting inventory for user {user_id}: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error retrieving inventory: {str(e)}"
            }
    
    def add_item(self, user_id: str, item_name: str, quantity: int = 1) -> Dict[str, Any]:
        """
        Add items to a user's inventory.
        
        Args:
            user_id: User ID
            item_name: Name of the item
            quantity: Quantity to add (default: 1)
            
        Returns:
            Success status and updated inventory
        """
        try:
            if quantity <= 0:
                return {
                    "success": False,
                    "error": "Quantity must be greater than 0"
                }
            
            # Get current inventory
            inventory = self.state_manager.get_user_state(user_id, "inventory", default={"items": {}})
            if not isinstance(inventory, dict):
                inventory = {"items": {}}
            if "items" not in inventory:
                inventory["items"] = {}
            
            # Normalize item name (lowercase, strip)
            item_name = item_name.lower().strip()
            
            # Add items
            current_qty = inventory["items"].get(item_name, 0)
            inventory["items"][item_name] = current_qty + quantity
            
            # Save updated inventory
            self.state_manager.set_user_state(
                user_id,
                "inventory",
                inventory,
                metadata={"action": "add_item", "item": item_name, "quantity": quantity}
            )
            
            return {
                "success": True,
                "message": f"Added {quantity} {item_name}(s) to inventory",
                "item": item_name,
                "quantity_added": quantity,
                "new_total": inventory["items"][item_name]
            }
        except Exception as e:
            logger.error(f"Error adding item to inventory: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error adding item: {str(e)}"
            }
    
    def remove_item(self, user_id: str, item_name: str, quantity: int = 1) -> Dict[str, Any]:
        """
        Remove items from a user's inventory.
        
        Args:
            user_id: User ID
            item_name: Name of the item
            quantity: Quantity to remove (default: 1)
            
        Returns:
            Success status and updated inventory
        """
        try:
            if quantity <= 0:
                return {
                    "success": False,
                    "error": "Quantity must be greater than 0"
                }
            
            # Get current inventory
            inventory = self.state_manager.get_user_state(user_id, "inventory", default={"items": {}})
            if not isinstance(inventory, dict):
                inventory = {"items": {}}
            if "items" not in inventory:
                inventory["items"] = {}
            
            # Normalize item name
            item_name = item_name.lower().strip()
            
            # Check if user has enough items
            current_qty = inventory["items"].get(item_name, 0)
            if current_qty < quantity:
                return {
                    "success": False,
                    "error": f"Insufficient items. You have {current_qty} {item_name}(s), but tried to remove {quantity}"
                }
            
            # Remove items
            inventory["items"][item_name] = current_qty - quantity
            
            # Remove item entry if quantity reaches 0
            if inventory["items"][item_name] == 0:
                del inventory["items"][item_name]
            
            # Save updated inventory
            self.state_manager.set_user_state(
                user_id,
                "inventory",
                inventory,
                metadata={"action": "remove_item", "item": item_name, "quantity": quantity}
            )
            
            return {
                "success": True,
                "message": f"Removed {quantity} {item_name}(s) from inventory",
                "item": item_name,
                "quantity_removed": quantity,
                "remaining": inventory["items"].get(item_name, 0)
            }
        except Exception as e:
            logger.error(f"Error removing item from inventory: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error removing item: {str(e)}"
            }
    
    def transfer_item(self, from_user_id: str, to_user_id: str, item_name: str, quantity: int) -> Dict[str, Any]:
        """
        Transfer items between users (used by trade system).
        
        Args:
            from_user_id: User giving items
            to_user_id: User receiving items
            item_name: Name of the item
            quantity: Quantity to transfer
            
        Returns:
            Success status
        """
        try:
            if quantity <= 0:
                return {
                    "success": False,
                    "error": "Quantity must be greater than 0"
                }
            
            # Remove from source user
            remove_result = self.remove_item(from_user_id, item_name, quantity)
            if not remove_result.get("success"):
                return remove_result
            
            # Add to destination user
            add_result = self.add_item(to_user_id, item_name, quantity)
            if not add_result.get("success"):
                # Rollback: add items back to source user
                self.add_item(from_user_id, item_name, quantity)
                return {
                    "success": False,
                    "error": f"Transfer failed: {add_result.get('error')}. Items restored to source."
                }
            
            return {
                "success": True,
                "message": f"Transferred {quantity} {item_name}(s) from {from_user_id} to {to_user_id}",
                "from_user": from_user_id,
                "to_user": to_user_id,
                "item": item_name,
                "quantity": quantity
            }
        except Exception as e:
            logger.error(f"Error transferring item: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error transferring item: {str(e)}"
            }
    
    def check_item_quantity(self, user_id: str, item_name: str) -> Dict[str, Any]:
        """
        Check how many of a specific item a user has.
        
        Args:
            user_id: User ID
            item_name: Name of the item
            
        Returns:
            Quantity of the item
        """
        try:
            inventory = self.state_manager.get_user_state(user_id, "inventory", default={"items": {}})
            if not isinstance(inventory, dict) or "items" not in inventory:
                return {
                    "success": True,
                    "item": item_name,
                    "quantity": 0
                }
            
            item_name = item_name.lower().strip()
            quantity = inventory["items"].get(item_name, 0)
            
            return {
                "success": True,
                "item": item_name,
                "quantity": quantity
            }
        except Exception as e:
            logger.error(f"Error checking item quantity: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error checking item quantity: {str(e)}"
            }

