"""
User state management system for tracking:
- User inventory (gold, items, etc.)
- User attributes and properties
- State changes and transactions
- Historical state tracking
"""
from typing import Dict, Any, Optional, List
from neo4j import GraphDatabase
import json
from datetime import datetime
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from logger_config import logger


class UserStateManager:
    """
    Manages user state including inventory, attributes, and transactions.
    Tracks state changes so queries can return current state.
    """
    
    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        """Initialize user state manager."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._initialize_schema()
    
    def _initialize_schema(self):
        """Initialize user state schema."""
        with self.driver.session() as session:
            try:
                session.run("CREATE CONSTRAINT user_state_id IF NOT EXISTS FOR (s:UserState) REQUIRE s.id IS UNIQUE")
                session.run("CREATE INDEX state_user IF NOT EXISTS FOR (s:UserState) ON (s.user_id)")
                session.run("CREATE INDEX state_key IF NOT EXISTS FOR (s:UserState) ON (s.key)")
            except Exception as e:
                logger.debug(f"Schema initialization (may already exist): {e}")
    
    def set_user_state(self,
                      user_id: str,
                      key: str,
                      value: Any,
                      metadata: Dict[str, Any] = None) -> str:
        """
        Set a user state value.
        
        Args:
            user_id: User ID
            key: State key (e.g., "gold", "inventory.sword", "level")
            value: State value (can be number, string, dict, list)
            metadata: Optional metadata (source, reason, etc.)
            
        Returns:
            State ID
        """
        state_id = f"state_{user_id}_{key}_{datetime.now().timestamp()}"
        
        with self.driver.session() as session:
            session.run("MERGE (u:User {id: $user_id})", user_id=user_id)
            
            # Serialize value
            if isinstance(value, (dict, list)):
                value_json = json.dumps(value)
            else:
                value_json = json.dumps({"value": value})
            
            metadata_json = json.dumps(metadata) if metadata else "{}"
            
            # Create or update state
            session.run("""
                MERGE (s:UserState {
                    user_id: $user_id,
                    key: $key
                })
                SET s.value = $value_json,
                    s.metadata = $metadata_json,
                    s.updated_at = datetime(),
                    s.id = COALESCE(s.id, $state_id)
                WITH s
                MATCH (u:User {id: $user_id})
                MERGE (u)-[:HAS_STATE]->(s)
            """,
                user_id=user_id,
                key=key,
                value_json=value_json,
                metadata_json=metadata_json,
                state_id=state_id
            )
            
            # Create transaction record
            self._create_transaction(user_id, key, value, "SET", metadata)
            
            return state_id
    
    def get_user_state(self,
                      user_id: str,
                      key: str,
                      default: Any = None) -> Any:
        """
        Get a user state value.
        
        Args:
            user_id: User ID
            key: State key
            default: Default value if not found
            
        Returns:
            State value or default
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (s:UserState {user_id: $user_id, key: $key})
                RETURN s.value AS value
                ORDER BY s.updated_at DESC
                LIMIT 1
            """,
                user_id=user_id,
                key=key
            )
            
            record = result.single()
            if not record:
                return default
            
            value_json = record.get("value")
            if not value_json:
                return default
            
            try:
                value_data = json.loads(value_json)
                # Handle both direct values and wrapped values
                if isinstance(value_data, dict) and "value" in value_data:
                    return value_data["value"]
                return value_data
            except:
                return default
    
    def increment_user_state(self,
                            user_id: str,
                            key: str,
                            amount: float,
                            metadata: Dict[str, Any] = None) -> float:
        """
        Increment a numeric user state value.
        
        Args:
            user_id: User ID
            key: State key
            amount: Amount to add (can be negative)
            metadata: Optional metadata
            
        Returns:
            New value
        """
        current_value = self.get_user_state(user_id, key, 0)
        
        # Ensure it's numeric
        try:
            current_value = float(current_value)
        except (ValueError, TypeError):
            current_value = 0.0
        
        new_value = current_value + amount
        
        self.set_user_state(user_id, key, new_value, metadata)
        
        # Create transaction
        self._create_transaction(user_id, key, amount, "INCREMENT", metadata)
        
        return new_value
    
    def add_to_inventory(self,
                        user_id: str,
                        item: str,
                        quantity: int = 1,
                        metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Add item to user inventory.
        
        Args:
            user_id: User ID
            item: Item name
            quantity: Quantity to add
            metadata: Optional metadata (source, etc.)
            
        Returns:
            Updated inventory
        """
        inventory = self.get_user_state(user_id, "inventory", {})
        
        if not isinstance(inventory, dict):
            inventory = {}
        
        current_qty = inventory.get(item, 0)
        inventory[item] = current_qty + quantity
        
        self.set_user_state(user_id, "inventory", inventory, metadata)
        
        # Create transaction
        self._create_transaction(
            user_id,
            f"inventory.{item}",
            quantity,
            "ADD",
            metadata
        )
        
        return inventory
    
    def remove_from_inventory(self,
                             user_id: str,
                             item: str,
                             quantity: int = 1,
                             metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Remove item from user inventory."""
        inventory = self.get_user_state(user_id, "inventory", {})
        
        if not isinstance(inventory, dict):
            inventory = {}
        
        current_qty = inventory.get(item, 0)
        new_qty = max(0, current_qty - quantity)
        
        if new_qty == 0:
            inventory.pop(item, None)
        else:
            inventory[item] = new_qty
        
        self.set_user_state(user_id, "inventory", inventory, metadata)
        
        # Create transaction
        self._create_transaction(
            user_id,
            f"inventory.{item}",
            -quantity,
            "REMOVE",
            metadata
        )
        
        return inventory
    
    def transfer_state(self,
                      from_user_id: str,
                      to_user_id: str,
                      key: str,
                      amount: float,
                      metadata: Dict[str, Any] = None) -> Dict[str, float]:
        """
        Transfer state value from one user to another.
        Example: Transfer gold from user A to user B.
        
        Returns:
            Dict with 'from_value' and 'to_value'
        """
        # Decrement from source
        from_value = self.increment_user_state(
            from_user_id,
            key,
            -amount,
            {**(metadata or {}), "transfer": "out", "to_user": to_user_id}
        )
        
        # Increment to destination
        to_value = self.increment_user_state(
            to_user_id,
            key,
            amount,
            {**(metadata or {}), "transfer": "in", "from_user": from_user_id}
        )
        
        return {
            "from_value": from_value,
            "to_value": to_value
        }
    
    def transfer_item(self,
                     from_user_id: str,
                     to_user_id: str,
                     item: str,
                     quantity: int = 1,
                     metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Transfer item from one user to another.
        
        Returns:
            Dict with 'from_inventory' and 'to_inventory'
        """
        # Remove from source
        from_inventory = self.remove_from_inventory(
            from_user_id,
            item,
            quantity,
            {**(metadata or {}), "transfer": "out", "to_user": to_user_id}
        )
        
        # Add to destination
        to_inventory = self.add_to_inventory(
            to_user_id,
            item,
            quantity,
            {**(metadata or {}), "transfer": "in", "from_user": from_user_id}
        )
        
        return {
            "from_inventory": from_inventory,
            "to_inventory": to_inventory
        }
    
    def _create_transaction(self,
                           user_id: str,
                           key: str,
                           value: Any,
                           operation: str,
                           metadata: Dict[str, Any] = None):
        """Create a transaction record for state changes."""
        transaction_id = f"txn_{user_id}_{datetime.now().timestamp()}"
        
        with self.driver.session() as session:
            value_json = json.dumps(value) if isinstance(value, (dict, list)) else json.dumps({"value": value})
            metadata_json = json.dumps(metadata) if metadata else "{}"
            
            session.run("""
                CREATE (t:Transaction {
                    id: $transaction_id,
                    user_id: $user_id,
                    key: $key,
                    value: $value_json,
                    operation: $operation,
                    metadata: $metadata_json,
                    created_at: datetime()
                })
                WITH t
                MATCH (u:User {id: $user_id})
                MERGE (u)-[:HAS_TRANSACTION]->(t)
            """,
                transaction_id=transaction_id,
                user_id=user_id,
                key=key,
                value_json=value_json,
                operation=operation,
                metadata_json=metadata_json
            )
    
    def get_user_all_states(self, user_id: str) -> Dict[str, Any]:
        """Get all state values for a user."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (s:UserState {user_id: $user_id})
                RETURN s.key AS key, s.value AS value
                ORDER BY s.updated_at DESC
            """,
                user_id=user_id
            )
            
            states = {}
            seen_keys = set()
            
            for record in result:
                key = record.get("key")
                if key in seen_keys:
                    continue  # Skip older versions
                
                seen_keys.add(key)
                value_json = record.get("value")
                
                try:
                    value_data = json.loads(value_json)
                    if isinstance(value_data, dict) and "value" in value_data:
                        states[key] = value_data["value"]
                    else:
                        states[key] = value_data
                except:
                    states[key] = value_json
            
            return states
    
    def get_transaction_history(self,
                               user_id: str,
                               key: str = None,
                               limit: int = 50) -> List[Dict[str, Any]]:
        """Get transaction history for a user."""
        with self.driver.session() as session:
            cypher = """
                MATCH (t:Transaction {user_id: $user_id})
            """
            params = {"user_id": user_id}
            
            if key:
                cypher += " WHERE t.key = $key"
                params["key"] = key
            
            cypher += """
                RETURN t.id AS id,
                       t.key AS key,
                       t.value AS value,
                       t.operation AS operation,
                       t.metadata AS metadata,
                       toString(t.created_at) AS created_at
                ORDER BY t.created_at DESC
                LIMIT $limit
            """
            params["limit"] = limit
            
            result = session.run(cypher, **params)
            
            transactions = []
            for record in result:
                value_json = record.get("value", "{}")
                metadata_json = record.get("metadata", "{}")
                
                try:
                    value = json.loads(value_json)
                except:
                    value = value_json
                
                try:
                    metadata = json.loads(metadata_json)
                except:
                    metadata = {}
                
                transactions.append({
                    "id": record.get("id"),
                    "key": record.get("key"),
                    "value": value,
                    "operation": record.get("operation"),
                    "metadata": metadata,
                    "created_at": record.get("created_at")
                })
            
            return transactions
    
    def close(self):
        """Close connection."""
        self.driver.close()

