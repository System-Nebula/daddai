"""
Action parser for understanding user commands and actions.
Parses commands like "give @alexei 20 gold pieces" and extracts:
- Action type (give, take, set, etc.)
- Target user
- Item/resource
- Quantity
"""
from typing import Dict, Any, Optional, List, Tuple
import re
from logger_config import logger


class ActionParser:
    """
    Parses user commands to extract actions, targets, and parameters.
    Understands commands like:
    - "give @user 20 gold pieces"
    - "give @user a sword"
    - "set @user level to 10"
    - "add 50 gold to @user"
    """
    
    # Action patterns
    ACTION_PATTERNS = {
        "give": [
            r"give\s+(?:@|to\s+)?(\w+|<@!?\d+>)\s+(\d+)\s+(\w+(?:\s+\w+)*)",  # give @user 20 gold pieces
            r"give\s+(?:@|to\s+)?(\w+|<@!?\d+>)\s+(?:a|an|the)?\s*(\w+(?:\s+\w+)*)",  # give @user a sword
            r"give\s+(\d+)\s+(\w+(?:\s+\w+)*)\s+(?:to|@)\s+(\w+|<@!?\d+>)",  # give 20 gold pieces to @user
        ],
        "take": [
            r"take\s+(\d+)\s+(\w+(?:\s+\w+)*)\s+from\s+(\w+|<@!?\d+>)",
            r"take\s+(?:a|an|the)?\s*(\w+(?:\s+\w+)*)\s+from\s+(\w+|<@!?\d+>)",
        ],
        "set": [
            r"set\s+(\w+|<@!?\d+>)\s+(\w+)\s+to\s+(\d+)",
            r"set\s+(\w+)\s+to\s+(\d+)\s+for\s+(\w+|<@!?\d+>)",
        ],
        "add": [
            r"add\s+(\d+)\s+(\w+(?:\s+\w+)*)\s+(?:to|for)\s+(\w+|<@!?\d+>)",
        ],
        "remove": [
            r"remove\s+(\d+)\s+(\w+(?:\s+\w+)*)\s+from\s+(\w+|<@!?\d+>)",
        ],
    }
    
    # Common items/resources
    ITEM_PATTERNS = {
        "gold": ["gold", "gold pieces", "gp", "coins", "coin"],
        "silver": ["silver", "silver pieces", "sp"],
        "sword": ["sword", "swords"],
        "potion": ["potion", "potions", "health potion"],
        "armor": ["armor", "armour"],
    }
    
    def parse_action(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Parse an action from text.
        
        Returns:
            Dict with:
            - action: Action type (give, take, set, etc.)
            - target_user: Target user ID or username
            - item: Item/resource name
            - quantity: Quantity (default 1)
            - original_text: Original text
            - confidence: Confidence score (0-1)
        """
        text_lower = text.lower().strip()
        
        # Extract Discord user mentions first
        user_mentions = self._extract_user_mentions(text)
        
        best_match = None
        best_confidence = 0.0
        
        # Try each action type
        for action_type, patterns in self.ACTION_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text_lower, re.IGNORECASE)
                if match:
                    parsed = self._parse_match(action_type, match, text, user_mentions)
                    if parsed and parsed.get("confidence", 0) > best_confidence:
                        best_match = parsed
                        best_confidence = parsed.get("confidence", 0)
        
        return best_match
    
    def _extract_user_mentions(self, text: str) -> List[str]:
        """Extract Discord user mentions from text."""
        mentions = re.findall(r'<@!?(\d+)>', text)
        return mentions
    
    def _parse_match(self,
                    action_type: str,
                    match: re.Match,
                    original_text: str,
                    user_mentions: List[str]) -> Optional[Dict[str, Any]]:
        """Parse a regex match into an action dict."""
        groups = match.groups()
        
        parsed = {
            "action": action_type,
            "original_text": original_text,
            "confidence": 0.5
        }
        
        # Extract user mentions
        if user_mentions:
            parsed["target_user_id"] = user_mentions[0]
            parsed["confidence"] += 0.3
        
        # Parse based on action type
        if action_type == "give":
            parsed = self._parse_give_action(groups, parsed, user_mentions)
        elif action_type == "take":
            parsed = self._parse_take_action(groups, parsed, user_mentions)
        elif action_type == "set":
            parsed = self._parse_set_action(groups, parsed, user_mentions)
        elif action_type == "add":
            parsed = self._parse_add_action(groups, parsed, user_mentions)
        elif action_type == "remove":
            parsed = self._parse_remove_action(groups, parsed, user_mentions)
        
        return parsed
    
    def _parse_give_action(self,
                          groups: Tuple,
                          parsed: Dict[str, Any],
                          user_mentions: List[str]) -> Dict[str, Any]:
        """Parse a 'give' action."""
        # Pattern 1: "give @user 20 gold pieces"
        if len(groups) >= 3:
            user_ref = groups[0]
            quantity = groups[1]
            item = groups[2]
            
            # Extract user ID if it's a mention
            user_id = self._extract_user_id(user_ref, user_mentions)
            if user_id:
                parsed["target_user_id"] = user_id
            
            try:
                parsed["quantity"] = int(quantity)
            except:
                parsed["quantity"] = 1
            
            parsed["item"] = self._normalize_item(item)
            parsed["confidence"] += 0.2
        
        # Pattern 2: "give @user a sword"
        elif len(groups) >= 2:
            user_ref = groups[0]
            item = groups[1]
            
            user_id = self._extract_user_id(user_ref, user_mentions)
            if user_id:
                parsed["target_user_id"] = user_id
            
            parsed["quantity"] = 1
            parsed["item"] = self._normalize_item(item)
            parsed["confidence"] += 0.1
        
        # Pattern 3: "give 20 gold pieces to @user"
        elif len(groups) >= 3:
            quantity = groups[0]
            item = groups[1]
            user_ref = groups[2]
            
            user_id = self._extract_user_id(user_ref, user_mentions)
            if user_id:
                parsed["target_user_id"] = user_id
            
            try:
                parsed["quantity"] = int(quantity)
            except:
                parsed["quantity"] = 1
            
            parsed["item"] = self._normalize_item(item)
            parsed["confidence"] += 0.2
        
        return parsed
    
    def _parse_take_action(self, groups: Tuple, parsed: Dict[str, Any], user_mentions: List[str]) -> Dict[str, Any]:
        """Parse a 'take' action."""
        if len(groups) >= 2:
            if len(groups) == 3:  # "take 20 gold from @user"
                quantity = groups[0]
                item = groups[1]
                user_ref = groups[2]
                
                try:
                    parsed["quantity"] = int(quantity)
                except:
                    parsed["quantity"] = 1
            else:  # "take sword from @user"
                item = groups[0]
                user_ref = groups[1]
                parsed["quantity"] = 1
            
            user_id = self._extract_user_id(user_ref, user_mentions)
            if user_id:
                parsed["target_user_id"] = user_id
            
            parsed["item"] = self._normalize_item(item)
            parsed["confidence"] += 0.2
        
        return parsed
    
    def _parse_set_action(self, groups: Tuple, parsed: Dict[str, Any], user_mentions: List[str]) -> Dict[str, Any]:
        """Parse a 'set' action."""
        if len(groups) >= 2:
            if len(groups) == 3:  # "set @user level to 10"
                user_ref = groups[0]
                key = groups[1]
                value = groups[2]
            else:  # "set level to 10 for @user"
                key = groups[0]
                value = groups[1]
                user_ref = groups[2] if len(groups) > 2 else None
            
            if user_ref:
                user_id = self._extract_user_id(user_ref, user_mentions)
                if user_id:
                    parsed["target_user_id"] = user_id
            
            parsed["key"] = key
            try:
                parsed["value"] = int(value)
            except:
                parsed["value"] = value
            
            parsed["confidence"] += 0.2
        
        return parsed
    
    def _parse_add_action(self, groups: Tuple, parsed: Dict[str, Any], user_mentions: List[str]) -> Dict[str, Any]:
        """Parse an 'add' action."""
        if len(groups) >= 3:
            quantity = groups[0]
            item = groups[1]
            user_ref = groups[2]
            
            user_id = self._extract_user_id(user_ref, user_mentions)
            if user_id:
                parsed["target_user_id"] = user_id
            
            try:
                parsed["quantity"] = int(quantity)
            except:
                parsed["quantity"] = 1
            
            parsed["item"] = self._normalize_item(item)
            parsed["confidence"] += 0.2
        
        return parsed
    
    def _parse_remove_action(self, groups: Tuple, parsed: Dict[str, Any], user_mentions: List[str]) -> Dict[str, Any]:
        """Parse a 'remove' action."""
        if len(groups) >= 3:
            quantity = groups[0]
            item = groups[1]
            user_ref = groups[2]
            
            user_id = self._extract_user_id(user_ref, user_mentions)
            if user_id:
                parsed["target_user_id"] = user_id
            
            try:
                parsed["quantity"] = int(quantity)
            except:
                parsed["quantity"] = 1
            
            parsed["item"] = self._normalize_item(item)
            parsed["confidence"] += 0.2
        
        return parsed
    
    def _extract_user_id(self, user_ref: str, user_mentions: List[str]) -> Optional[str]:
        """Extract user ID from a user reference."""
        # Check if it's a Discord mention
        mention_match = re.search(r'<@!?(\d+)>', user_ref)
        if mention_match:
            return mention_match.group(1)
        
        # Check if we have mentions in the text
        if user_mentions:
            return user_mentions[0]
        
        return None
    
    def _normalize_item(self, item: str) -> str:
        """Normalize item name (e.g., "gold pieces" -> "gold")."""
        item_lower = item.lower().strip()
        
        # Check against known patterns
        for normalized, patterns in self.ITEM_PATTERNS.items():
            for pattern in patterns:
                if pattern in item_lower:
                    return normalized
        
        # Return cleaned version
        return item_lower.strip()
    
    def is_action(self, text: str) -> bool:
        """Check if text contains an action command."""
        parsed = self.parse_action(text)
        return parsed is not None and parsed.get("confidence", 0) > 0.5
    
    def get_action_type(self, text: str) -> Optional[str]:
        """Get the action type from text, if any."""
        parsed = self.parse_action(text)
        return parsed.get("action") if parsed else None

