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
from src.clients.lmstudio_client import LMStudioClient


class LLMItemTracker:
    """
    Uses LLM to understand and track items, their locations, and ownership.
    The LLM reasons about:
    - What items are being referenced
    - Where items should go
    - Who owns items
    - Item relationships and properties
    """
    
    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD, llm_client: Optional[LMStudioClient] = None):
        """Initialize LLM item tracker."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.llm_client = llm_client if llm_client is not None else LMStudioClient()
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
        prompt = f"""You are an intelligent item tracking system. Your job is to understand ACTION COMMANDS and extract the user's intent.

Command: "{text}"

CRITICAL: This parser is ONLY for ACTION COMMANDS (give, take, transfer, etc.). 
DO NOT parse queries (questions starting with "how many", "how much", "what", etc.) as actions.
DO NOT parse casual conversation, greetings, or small talk as actions.
If this is a query/question OR casual conversation, set action="query" and confidence=0.0

Examples of ACTION COMMANDS you should understand:
- "I'm giving @alexei 40 gold coins" → give, gold, 40, to @alexei
- "Give 40 gold to @alexei" → give, gold, 40, to @alexei  
- "Transfer 40 coins to @alexei" → transfer, gold, 40, to @alexei
- "Send @alexei 40 gold" → send, gold, 40, to @alexei
- "I want to give @alexei some gold coins, 40 of them" → give, gold, 40, to @alexei
- "Can you give @alexei 40 gold coins?" → give, gold, 40, to @alexei (question form but still an action)
- "Let's give @alexei 40 gold coins" → give, gold, 40, to @alexei
- "I'll give @alexei 40 gold coins" → give, gold, 40, to @alexei

Examples of QUERIES (NOT actions - set action="query", confidence=0.0):
- "how many gold coins does @alexei have?" → query, confidence=0.0
- "how much gold does @alexei have?" → query, confidence=0.0
- "what does @alexei have?" → query, confidence=0.0
- "how many coins do I have?" → query, confidence=0.0

Examples of CASUAL CONVERSATION (NOT actions - set action="query", confidence=0.0):
- "Heyya Gopher! How's it going?" → query, confidence=0.0
- "Hi, how are you?" → query, confidence=0.0
- "What's up?" → query, confidence=0.0
- "that's wild I didnt ask that. I was asking how you're doing" → query, confidence=0.0
- "ping" → query, confidence=0.0
- "lets go to the store and help me pick out some things to buy" → query, confidence=0.0 (casual conversation, not an action command)
- "let's go shopping" → query, confidence=0.0 (casual conversation)
- "help me pick out some things" → query, confidence=0.0 (casual conversation, asking for help/companionship)
- "can you help me with X?" → query, confidence=0.0 (asking for help, not giving items)
- "lets go somewhere" → query, confidence=0.0 (casual conversation)
- "want to go to X?" → query, confidence=0.0 (casual conversation/invitation)
- "throwing my dildo at @user" → query, confidence=0.0 (joke/casual statement, not a real action command)
- "throwing X at Y" → query, confidence=0.0 (casual statement/joke, not an action command)
- Phrases describing physical actions metaphorically or jokingly → query, confidence=0.0 (casual conversation, not real action commands)
- Any greeting, small talk, casual conversation, jokes, or requests for help/companionship without action verbs → query, confidence=0.0
- Phrases like "lets go", "help me", "pick out", "want to go", "throwing X at Y" are CASUAL CONVERSATION, not action commands → query, confidence=0.0

Extract:
1. Action type: give, take, transfer, set, add, remove, query (use "query" for questions)
2. Item name: normalize it (gold/coins/silver → "gold")
3. Quantity: extract any number mentioned (only for actions, not queries)
4. Source: who/where it's coming from (if not mentioned, assume the speaker)
5. Destination: who/where it's going to (extract from mentions)
6. Confidence: HIGH (0.8-1.0) if you're certain it's an action, LOW (<0.3) if it's a query/question

Respond ONLY with valid JSON:
{{
    "action": "give|take|transfer|set|add|remove|query",
    "item_name": "normalized item name (gold/coins/silver → gold)",
    "item_type": "currency|weapon|armor|consumable|misc",
    "quantity": 1,
    "source_user_id": "extract from <@123456789> or null if speaker",
    "source_location": "location or null",
    "dest_user_id": "extract from <@123456789> format",
    "dest_location": "location or null",
    "properties": {{}},
    "confidence": 0.8
}}

CRITICAL INSTRUCTIONS:
- Extract user IDs from Discord mentions: <@123456789> or <@!123456789> → "123456789"
- If command starts with "how many", "how much", "what", "who", "when", "where", "why" → action="query", confidence=0.0
- If command is asking about state (has/have/own) → action="query", confidence=0.0
- If command is casual conversation (greetings, "how are you", "what's up", "lets go", "help me", etc.) → action="query", confidence=0.0
- If command contains "lets go", "let's go", "help me", "pick out", "want to go" → action="query", confidence=0.0 (casual conversation/invitation, NOT an action command)
- If command is asking for help/companionship (not giving items) → action="query", confidence=0.0
- If command is asking about documents, files, or information (e.g., "what model is X training?", "how many steps did X run?") → action="query", confidence=0.0
- If command mentions "training", "running", "using", "doing" in a question context (not an action) → action="query", confidence=0.0
- If command has NO action verbs (give, take, transfer, send, etc.) → action="query", confidence=0.0
- ONLY parse as action if user is DOING something (giving, taking, transferring, etc.)
- ONLY parse as action if there's a clear action verb (give, take, transfer, send) AND an item/resource mentioned
- "what model is X training?" is a QUESTION about information, NOT an action → action="query", confidence=0.0
- "how many steps did X run?" is a QUESTION about information, NOT an action → action="query", confidence=0.0
- "lets go to the store and help me pick out some things" is CASUAL CONVERSATION, NOT an action → action="query", confidence=0.0
- ANY mention of giving/sending/transferring to someone → action is "give" or "transfer" (if not a query AND if there's an item mentioned AND it's clearly an action command, not casual conversation)
- ANY number before an item → that's the quantity (only for actions)
- "gold coins", "coins", "gold pieces", "gold" → all normalize to "gold"
- If user says "I'm giving X to Y" → action=give, dest_user_id=Y, quantity=X
- Be CONFIDENT (0.8+) ONLY if you can clearly identify: action + item + quantity + destination AND it's clearly an action command (NOT casual conversation)
- Set confidence LOW (<0.3) if it's a query/question (how many, how much, what, etc.)
- Set confidence LOW (<0.3) if it's casual conversation, small talk, jokes, or invitations ("lets go", "help me", "throwing X at Y", etc.)
- Set confidence LOW (<0.3) if there's no clear action verb or item mentioned
- Set confidence LOW (<0.3) if it's asking about information (what, how many, etc.) even if it contains words like "training" or "running"
- Set confidence LOW (<0.3) if it contains phrases like "lets go", "help me", "pick out", "want to go", "throwing X at Y" (these are casual conversation/jokes, not actions)
- Set confidence LOW (<0.3) if it's a joke, metaphor, or casual statement describing a physical action (like "throwing my dildo at X") - these are NOT real action commands
- Default quantity to 1 if not specified (only for actions)
- Item type "currency" for gold, coins, silver, money, gp, sp, etc.
"""
        
        try:
            response = self.llm_client.generate_response(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,  # Even lower temperature for more consistent parsing
                max_tokens=300
            )
            
            logger.debug(f"LLM action parsing response: {response[:200]}")
            
            # Extract JSON from response (try multiple patterns)
            import re
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
            if not json_match:
                # Try simpler pattern
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
            
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                    logger.debug(f"Parsed JSON: {parsed}")
                except json.JSONDecodeError as e:
                    logger.warn(f"JSON decode error: {e}, raw: {json_match.group()[:200]}")
                    parsed = {"action": "unknown", "confidence": 0.0}
            else:
                logger.warn(f"Could not extract JSON from LLM response: {response[:200]}")
                parsed = {"action": "unknown", "confidence": 0.0}
            
            # Always extract user IDs from text (more reliable than LLM extraction)
            user_mentions = re.findall(r'<@!?(\d+)>', text)
            if user_mentions:
                action_type = parsed.get("action", "").lower()
                logger.debug(f"Found {len(user_mentions)} mention(s), action_type={action_type}")
                
                # For give/transfer/add actions, mentions are typically the destination
                if action_type in ["give", "add", "transfer", "send"]:
                    if not parsed.get("dest_user_id"):
                        parsed["dest_user_id"] = user_mentions[0]
                        logger.debug(f"Set dest_user_id from mention: {user_mentions[0]}")
                    # If there's a second mention, it might be the source
                    if len(user_mentions) > 1 and not parsed.get("source_user_id"):
                        parsed["source_user_id"] = user_mentions[1]
                # For take/remove actions, mentions are typically the source
                elif action_type in ["take", "remove"]:
                    if not parsed.get("source_user_id"):
                        parsed["source_user_id"] = user_mentions[0]
                # For query actions, mentions are the target
                elif action_type == "query":
                    if not parsed.get("dest_user_id"):
                        parsed["dest_user_id"] = user_mentions[0]
                # If action is unknown but we have mentions and keywords, assume it's a give action
                # BUT only if it's clearly an action command, not casual conversation
                elif action_type == "unknown" and user_mentions:
                    # Check if text contains action keywords AND an item/resource
                    text_lower = text.lower()
                    has_action_keyword = any(kw in text_lower for kw in ["giving", "give", "transfer", "send", "gift", "hand", "pass"])
                    has_item_keyword = any(kw in text_lower for kw in ["gold", "coin", "silver", "item", "sword", "potion", "armor"])
                    # Don't infer if it's casual conversation (greetings, "how are you", etc.)
                    is_casual = any(phrase in text_lower for phrase in ["how's it going", "how are you", "what's up", "whats up", "hey", "hi", "hello"])
                    
                    if has_action_keyword and has_item_keyword and not is_casual:
                        parsed["action"] = "give"
                        parsed["dest_user_id"] = user_mentions[0]
                        parsed["confidence"] = 0.5  # Lower confidence since we inferred it
                        logger.info(f"Inferred 'give' action from keywords and mentions")
                    else:
                        # If we can't clearly infer an action, mark as query
                        parsed["action"] = "query"
                        parsed["confidence"] = 0.0
                        logger.debug(f"Could not infer action - marking as query")
            
            # Ensure confidence is set
            action_type = parsed.get("action", "").lower()
            # Force confidence to 0.0 for queries (even if LLM set it incorrectly)
            if action_type == "query":
                parsed["confidence"] = 0.0
            elif "confidence" not in parsed or parsed["confidence"] is None:
                # Set confidence based on how complete the parsing is
                if action_type and action_type != "unknown":
                    if parsed.get("dest_user_id") or parsed.get("source_user_id"):
                        parsed["confidence"] = 0.8  # High confidence if we have action + user
                    else:
                        parsed["confidence"] = 0.5  # Medium confidence if we have action but no user
                else:
                    parsed["confidence"] = 0.0
            
            logger.info(f"Final parsed action: {parsed}")
            return parsed
        except Exception as e:
            logger.error(f"Error parsing item action with LLM: {e}", exc_info=True)
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
        
        # Extract user ID from Discord mention format if needed
        actual_owner_id = owner_id
        if owner_id and isinstance(owner_id, str) and owner_id.startswith("<@"):
            import re
            mention_match = re.search(r'<@!?(\d+)>', owner_id)
            if mention_match:
                actual_owner_id = mention_match.group(1)
                logger.debug(f"Extracted owner_id from Discord mention: {actual_owner_id}")
        
        item_id = f"item_{normalized_name}_{actual_owner_id or 'unowned'}"
        
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
            """,
                item_id=item_id,
                normalized_name=normalized_name,
                item_type=item_type,
                quantity=quantity,
                owner_id=actual_owner_id or "unowned",
                properties_json=json.dumps(properties or item_info.get("properties", {}))
            )
            
            # Only create location relationship if location is provided (Location label may not exist)
            if location:
                try:
                    session.run("""
                        MATCH (i:Item {id: $item_id})
                        MERGE (l:Location {name: $location})
                        MERGE (i)-[:LOCATED_AT]->(l)
                    """,
                        item_id=item_id,
                        location=location
                    )
                except Exception as e:
                    logger.debug(f"Could not create location relationship (Location label might not exist): {e}")
        
        logger.info(f"Tracked item: {normalized_name} (owner: {actual_owner_id}, location: {location}, qty: {quantity})")
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
        
        # Extract user IDs from Discord mention format if needed
        import re
        if from_user_id and isinstance(from_user_id, str) and from_user_id.startswith("<@"):
            mention_match = re.search(r'<@!?(\d+)>', from_user_id)
            if mention_match:
                from_user_id = mention_match.group(1)
                logger.debug(f"Extracted from_user_id from Discord mention: {from_user_id}")
        
        if to_user_id and isinstance(to_user_id, str) and to_user_id.startswith("<@"):
            mention_match = re.search(r'<@!?(\d+)>', to_user_id)
            if mention_match:
                to_user_id = mention_match.group(1)
                logger.debug(f"Extracted to_user_id from Discord mention: {to_user_id}")
        
        # Ensure quantity is valid (default to 1 if None)
        if quantity is None:
            quantity = 1
        else:
            quantity = int(quantity) if quantity else 1
        
        # Track removal from source
        if from_user_id:
            self.track_item(normalized_name, owner_id=from_user_id, quantity=-quantity)
        
        # Track addition to destination
        if to_user_id:
            self.track_item(normalized_name, owner_id=to_user_id, quantity=quantity)
        
        # Create transfer relationship (only if both user IDs are valid)
        if from_user_id and to_user_id and from_user_id != "unowned" and to_user_id != "unowned":
            with self.driver.session() as session:
                try:
                    session.run("""
                        MATCH (from:User {id: $from_user_id})
                        MATCH (to:User {id: $to_user_id})
                        MATCH (i:Item {name: $normalized_name})
                        MERGE (from)-[t:TRANSFERRED {quantity: $quantity, created_at: datetime()}]->(i)
                        MERGE (i)-[t2:TRANSFERRED_TO {quantity: $quantity, created_at: datetime()}]->(to)
                    """,
                        from_user_id=from_user_id,
                        to_user_id=to_user_id,
                        normalized_name=normalized_name,
                        quantity=quantity
                    )
                except Exception as e:
                    logger.debug(f"Could not create transfer relationship (item might not exist yet): {e}")
        
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
            # Extract user ID from Discord mention format if needed
            actual_user_id = user_id
            if user_id and isinstance(user_id, str) and user_id.startswith("<@"):
                import re
                mention_match = re.search(r'<@!?(\d+)>', user_id)
                if mention_match:
                    actual_user_id = mention_match.group(1)
            
            if actual_user_id:
                # Removed LOCATED_AT relationship to avoid Neo4j warnings
                result = session.run("""
                    MATCH (i:Item {name: $normalized_name})-[:OWNED_BY]->(u:User {id: $user_id})
                    RETURN i.name AS name, i.quantity AS quantity, u.id AS owner, null AS location, i.properties AS properties
                """,
                    normalized_name=normalized_name,
                    user_id=actual_user_id
                )
            else:
                # Removed LOCATED_AT relationship to avoid Neo4j warnings
                result = session.run("""
                    MATCH (i:Item {name: $normalized_name})
                    OPTIONAL MATCH (i)-[:OWNED_BY]->(u:User)
                    RETURN i.name AS name, i.quantity AS quantity, u.id AS owner, null AS location, i.properties AS properties
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
        # Extract user ID from Discord mention format if needed
        actual_user_id = user_id
        if user_id and isinstance(user_id, str) and user_id.startswith("<@"):
            import re
            mention_match = re.search(r'<@!?(\d+)>', user_id)
            if mention_match:
                actual_user_id = mention_match.group(1)
                logger.debug(f"Extracted user_id from Discord mention: {actual_user_id}")
        
        with self.driver.session() as session:
            # Removed LOCATED_AT relationship to avoid Neo4j warnings when Location label doesn't exist
            result = session.run("""
                MATCH (i:Item)-[:OWNED_BY]->(u:User {id: $user_id})
                RETURN i.name AS name, i.quantity AS quantity, i.item_type AS type, 
                       null AS location, i.properties AS properties
                ORDER BY i.item_type, i.name
            """,
                user_id=actual_user_id
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

