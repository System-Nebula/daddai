"""
LLM-based item tracking system.
The LLM understands what items are, where they go, and to whom they belong.
"""
from typing import Dict, Any, Optional, List
from neo4j import GraphDatabase
import json
from datetime import datetime
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from logger_config import logger
from lmstudio_client import LMStudioClient


class LLMItemTracker:
    """
    Uses LLM to understand and track items, their locations, and ownership.
    The LLM reasons about:
    - What items are being referenced
    - Where items should go
    - Who owns items
    - Item relationships and properties
    """
    
    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        """Initialize LLM item tracker."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.llm_client = LMStudioClient()
        self._initialize_schema()
    
    def _initialize_schema(self):
        """Initialize item tracking schema."""
        with self.driver.session() as session:
            try:
                session.run("CREATE CONSTRAINT item_id IF NOT EXISTS FOR (i:Item) REQUIRE i.id IS UNIQUE")
                session.run("CREATE INDEX item_name IF NOT EXISTS FOR (i:Item) ON (i.name)")
                session.run("CREATE INDEX item_owner IF NOT EXISTS FOR (i:Item) ON (i.owner_id)")
            except Exception as e:
                logger.debug(f"Schema initialization (may already exist): {e}")
    
    def parse_item_action(self, text: str, user_id: str, channel_id: str) -> Dict[str, Any]:
        """
        Use LLM to parse an item action from natural language.
        
        The LLM understands:
        - What item is being referenced
        - Action type (give, take, transfer, etc.)
        - Source and destination
        - Quantity and properties
        """
        prompt = f"""You are an item tracking system. Parse the following command and extract item information.

Command: "{text}"

Extract:
1. Action type (give, take, transfer, set, add, remove, query)
2. Item name (what item is being referenced - be specific and normalize it)
3. Quantity (if applicable, default to 1)
4. Source user/location (who/where is it coming from)
5. Destination user/location (who/where is it going to)
6. Item properties (if mentioned: type, rarity, value, etc.)

Respond ONLY with valid JSON in this format:
{{
    "action": "give|take|transfer|set|add|remove|query",
    "item_name": "normalized item name",
    "item_type": "currency|weapon|armor|consumable|misc",
    "quantity": 1,
    "source_user_id": "user id or null",
    "source_location": "location name or null",
    "dest_user_id": "user id or null",
    "dest_location": "location name or null",
    "properties": {{"key": "value"}},
    "confidence": 0.0-1.0
}}

Important:
- Normalize item names (e.g., "gold pieces" -> "gold", "sword" -> "sword")
- Extract user IDs from mentions like <@123456789>
- If quantity is not specified, use 1
- If action is unclear, set confidence low (< 0.5)
- Item type should be inferred from context
"""
        
        try:
            response = self.llm_client.generate_response(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,  # Lower temperature for more consistent parsing
                max_tokens=300
            )
            
            # Extract JSON from response
            import re
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                
                # Extract user IDs from text if not in JSON
                if not parsed.get("source_user_id") and not parsed.get("dest_user_id"):
                    user_mentions = re.findall(r'<@!?(\d+)>', text)
                    if user_mentions:
                        if parsed.get("action") in ["give", "add", "transfer"]:
                            parsed["dest_user_id"] = user_mentions[0]
                        elif parsed.get("action") in ["take", "remove"]:
                            parsed["source_user_id"] = user_mentions[0]
                
                return parsed
            else:
                logger.warn(f"Could not extract JSON from LLM response: {response}")
                return {"action": "unknown", "confidence": 0.0}
        except Exception as e:
            logger.error(f"Error parsing item action with LLM: {e}")
            return {"action": "unknown", "confidence": 0.0}
    
    def understand_item(self, item_name: str, context: str = "") -> Dict[str, Any]:
        """
        Use LLM to understand what an item is and its properties.
        
        Returns:
            Dict with item properties, type, and metadata
        """
        prompt = f"""You are an item tracking system. Understand what this item is.

Item name: "{item_name}"
Context: "{context}"

Determine:
1. Item type (currency, weapon, armor, consumable, misc)
2. Properties (value, rarity, weight, etc.)
3. Normalized name
4. Common aliases

Respond ONLY with valid JSON:
{{
    "normalized_name": "standardized item name",
    "item_type": "currency|weapon|armor|consumable|misc",
    "properties": {{
        "value": 0,
        "rarity": "common|uncommon|rare|epic|legendary",
        "weight": 0,
        "stackable": true/false
    }},
    "aliases": ["alternative names"]
}}
"""
        
        try:
            response = self.llm_client.generate_response(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )
            
            import re
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return {
                    "normalized_name": item_name.lower().strip(),
                    "item_type": "misc",
                    "properties": {},
                    "aliases": []
                }
        except Exception as e:
            logger.error(f"Error understanding item with LLM: {e}")
            return {
                "normalized_name": item_name.lower().strip(),
                "item_type": "misc",
                "properties": {},
                "aliases": []
            }
    
    def track_item(self,
                  item_name: str,
                  owner_id: Optional[str] = None,
                  location: Optional[str] = None,
                  quantity: int = 1,
                  properties: Dict[str, Any] = None) -> str:
        """
        Track an item in the knowledge graph.
        Creates or updates item node with ownership and location.
        """
        # Understand the item first
        item_info = self.understand_item(item_name)
        normalized_name = item_info.get("normalized_name", item_name.lower().strip())
        item_type = item_info.get("item_type", "misc")
        
        item_id = f"item_{normalized_name}_{owner_id or 'unowned'}"
        
        with self.driver.session() as session:
            # Create or update item
            session.run("""
                MERGE (i:Item {id: $item_id})
                SET i.name = $normalized_name,
                    i.item_type = $item_type,
                    i.quantity = COALESCE(i.quantity, 0) + $quantity,
                    i.updated_at = datetime(),
                    i.properties = $properties_json
                WITH i
                MERGE (u:User {id: $owner_id})
                MERGE (i)-[:OWNED_BY]->(u)
                WITH i, u
                WHERE $location IS NOT NULL
                MERGE (l:Location {name: $location})
                MERGE (i)-[:LOCATED_AT]->(l)
            """,
                item_id=item_id,
                normalized_name=normalized_name,
                item_type=item_type,
                quantity=quantity,
                owner_id=owner_id or "unowned",
                location=location,
                properties_json=json.dumps(properties or item_info.get("properties", {}))
            )
        
        logger.info(f"Tracked item: {normalized_name} (owner: {owner_id}, location: {location}, qty: {quantity})")
        return item_id
    
    def transfer_item(self,
                     item_name: str,
                     from_user_id: Optional[str],
                     to_user_id: Optional[str],
                     quantity: int = 1,
                     context: str = "") -> Dict[str, Any]:
        """
        Transfer an item using LLM understanding.
        The LLM determines the normalized item name and handles the transfer.
        """
        # Understand the item
        item_info = self.understand_item(item_name, context)
        normalized_name = item_info.get("normalized_name", item_name.lower().strip())
        
        # Track removal from source
        if from_user_id:
            self.track_item(normalized_name, owner_id=from_user_id, quantity=-quantity)
        
        # Track addition to destination
        if to_user_id:
            self.track_item(normalized_name, owner_id=to_user_id, quantity=quantity)
        
        # Create transfer relationship
        with self.driver.session() as session:
            session.run("""
                MATCH (from:User {id: $from_user_id})
                MATCH (to:User {id: $to_user_id})
                MATCH (i:Item {name: $normalized_name})
                MERGE (from)-[t:TRANSFERRED {quantity: $quantity, created_at: datetime()}]->(i)
                MERGE (i)-[t2:TRANSFERRED_TO {quantity: $quantity, created_at: datetime()}]->(to)
            """,
                from_user_id=from_user_id or "unowned",
                to_user_id=to_user_id or "unowned",
                normalized_name=normalized_name,
                quantity=quantity
            )
        
        return {
            "item": normalized_name,
            "from_user": from_user_id,
            "to_user": to_user_id,
            "quantity": quantity,
            "item_info": item_info
        }
    
    def query_item_location(self, item_name: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query where an item is located using LLM understanding.
        """
        item_info = self.understand_item(item_name)
        normalized_name = item_info.get("normalized_name", item_name.lower().strip())
        
        with self.driver.session() as session:
            if user_id:
                result = session.run("""
                    MATCH (i:Item {name: $normalized_name})-[:OWNED_BY]->(u:User {id: $user_id})
                    OPTIONAL MATCH (i)-[:LOCATED_AT]->(l:Location)
                    RETURN i.name AS name, i.quantity AS quantity, u.id AS owner, l.name AS location, i.properties AS properties
                """,
                    normalized_name=normalized_name,
                    user_id=user_id
                )
            else:
                result = session.run("""
                    MATCH (i:Item {name: $normalized_name})
                    OPTIONAL MATCH (i)-[:OWNED_BY]->(u:User)
                    OPTIONAL MATCH (i)-[:LOCATED_AT]->(l:Location)
                    RETURN i.name AS name, i.quantity AS quantity, u.id AS owner, l.name AS location, i.properties AS properties
                """,
                    normalized_name=normalized_name
                )
            
            locations = []
            for record in result:
                locations.append({
                    "item": record.get("name"),
                    "quantity": record.get("quantity", 0),
                    "owner": record.get("owner"),
                    "location": record.get("location"),
                    "properties": json.loads(record.get("properties", "{}"))
                })
            
            return locations
    
    def get_user_items(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all items owned by a user."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (i:Item)-[:OWNED_BY]->(u:User {id: $user_id})
                OPTIONAL MATCH (i)-[:LOCATED_AT]->(l:Location)
                RETURN i.name AS name, i.quantity AS quantity, i.item_type AS type, 
                       l.name AS location, i.properties AS properties
                ORDER BY i.item_type, i.name
            """,
                user_id=user_id
            )
            
            items = []
            for record in result:
                items.append({
                    "name": record.get("name"),
                    "quantity": record.get("quantity", 0),
                    "type": record.get("type"),
                    "location": record.get("location"),
                    "properties": json.loads(record.get("properties", "{}"))
                })
            
            return items
    
    def close(self):
        """Close connections."""
        self.driver.close()

