"""
D&D Dice Tool - Smart context-aware dice rolling for D&D.
Automatically determines appropriate dice based on actions and character stats.
"""
from typing import Dict, Any, Optional, List, Tuple
import random
import re
from Refactored.logger_config import logger


class DnDDiceTool:
    """
    Smart dice rolling system for D&D.
    Automatically determines appropriate dice based on context.
    """
    
    # Common dice types
    DICE_TYPES = {
        "d4": 4, "d6": 6, "d8": 8, "d10": 10,
        "d12": 12, "d20": 20, "d100": 100
    }
    
    # Action to dice mapping
    ACTION_DICE = {
        "attack": "d20",
        "damage": "weapon",  # Depends on weapon
        "ability_check": "d20",
        "saving_throw": "d20",
        "skill_check": "d20",
        "initiative": "d20",
        "healing": "dice",  # Depends on spell/ability
        "hit_points": "hit_die",  # Depends on class
        "percentile": "d100"
    }
    
    # Weapon damage dice
    WEAPON_DAMAGE = {
        "dagger": "d4",
        "shortsword": "d6",
        "longsword": "d8",
        "greatsword": "2d6",
        "rapier": "d8",
        "handaxe": "d6",
        "warhammer": "d8",
        "longbow": "d8",
        "shortbow": "d6",
        "crossbow": "d8",
        "quarterstaff": "d6",
        "mace": "d6",
        "club": "d4"
    }
    
    def roll_dice(self, dice_notation: str, modifier: int = 0, advantage: bool = False, disadvantage: bool = False) -> Dict[str, Any]:
        """
        Roll dice using standard D&D notation (e.g., "2d6+3", "d20", "1d8+1d6").
        
        Args:
            dice_notation: Dice notation (e.g., "2d6", "d20+5", "1d8+1d6")
            modifier: Additional modifier to add
            advantage: Roll with advantage (roll twice, take higher)
            disadvantage: Roll with disadvantage (roll twice, take lower)
            
        Returns:
            Roll result with details
        """
        try:
            # Parse dice notation
            # Handle patterns like: "2d6", "d20+5", "1d8+1d6", "2d6+3"
            total = 0
            rolls = []
            details = []
            
            # Split by + to handle multiple dice types
            parts = re.split(r'\s*\+\s*', dice_notation.lower().replace(' ', ''))
            
            for part in parts:
                if part.startswith('d'):
                    # Single die (e.g., "d20")
                    die_type = int(part[1:])
                    roll = random.randint(1, die_type)
                    rolls.append(roll)
                    total += roll
                    details.append(f"d{die_type}: {roll}")
                elif 'd' in part:
                    # Multiple dice (e.g., "2d6")
                    match = re.match(r'(\d+)d(\d+)', part)
                    if match:
                        count = int(match.group(1))
                        die_type = int(match.group(2))
                        die_rolls = [random.randint(1, die_type) for _ in range(count)]
                        rolls.extend(die_rolls)
                        total += sum(die_rolls)
                        details.append(f"{count}d{die_type}: {die_rolls} = {sum(die_rolls)}")
                elif part.isdigit():
                    # Static modifier
                    mod = int(part)
                    modifier += mod
            
            # Handle advantage/disadvantage for d20 rolls
            if advantage and disadvantage:
                advantage = False
                disadvantage = False  # Cancel out
            
            if advantage or disadvantage:
                # Re-roll d20s
                d20_rolls = [r for r in rolls if r <= 20]
                if d20_rolls:
                    d20_index = rolls.index(d20_rolls[0])
                    reroll = random.randint(1, 20)
                    if advantage:
                        rolls[d20_index] = max(rolls[d20_index], reroll)
                        details.append(f"Advantage reroll: {reroll}, using: {rolls[d20_index]}")
                    else:
                        rolls[d20_index] = min(rolls[d20_index], reroll)
                        details.append(f"Disadvantage reroll: {reroll}, using: {rolls[d20_index]}")
                    
                    # Recalculate total
                    total = sum(rolls) + modifier
            
            final_total = total + modifier
            
            return {
                "success": True,
                "dice_notation": dice_notation,
                "rolls": rolls,
                "modifier": modifier,
                "total": final_total,
                "details": details,
                "advantage": advantage,
                "disadvantage": disadvantage,
                "natural_20": 20 in rolls if rolls else False,
                "natural_1": 1 in rolls if rolls else False
            }
        except Exception as e:
            logger.error(f"Error rolling dice: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to roll dice: {str(e)}"
            }
    
    def roll_ability_check(
        self,
        ability_name: str,
        ability_modifier: int,
        proficiency_bonus: int = 0,
        proficient: bool = False,
        advantage: bool = False,
        disadvantage: bool = False
    ) -> Dict[str, Any]:
        """
        Roll an ability check (d20 + ability modifier + proficiency if applicable).
        
        Args:
            ability_name: Name of ability (e.g., "Strength", "Dexterity")
            ability_modifier: Ability modifier
            proficiency_bonus: Proficiency bonus
            proficient: Whether character is proficient in this check
            advantage: Roll with advantage
            disadvantage: Roll with disadvantage
            
        Returns:
            Ability check result
        """
        modifier = ability_modifier
        if proficient:
            modifier += proficiency_bonus
        
        result = self.roll_dice("d20", modifier, advantage, disadvantage)
        
        if result.get("success"):
            result["ability_name"] = ability_name
            result["ability_modifier"] = ability_modifier
            result["proficiency_bonus"] = proficiency_bonus if proficient else 0
            result["proficient"] = proficient
            result["check_type"] = "ability_check"
            
            # Determine success level for DC checks
            roll_total = result["total"]
            if result.get("natural_20"):
                result["success_level"] = "critical_success"
            elif result.get("natural_1"):
                result["success_level"] = "critical_failure"
            elif roll_total >= 20:
                result["success_level"] = "great_success"
            elif roll_total >= 15:
                result["success_level"] = "good_success"
            elif roll_total >= 10:
                result["success_level"] = "moderate_success"
            else:
                result["success_level"] = "failure"
        
        return result
    
    def roll_attack(
        self,
        attack_bonus: int,
        weapon_name: Optional[str] = None,
        damage_dice: Optional[str] = None,
        damage_modifier: int = 0,
        advantage: bool = False,
        disadvantage: bool = False
    ) -> Dict[str, Any]:
        """
        Roll an attack roll and damage.
        
        Args:
            attack_bonus: Attack bonus (ability modifier + proficiency)
            weapon_name: Name of weapon (for damage dice lookup)
            damage_dice: Dice notation for damage (e.g., "1d8")
            damage_modifier: Damage modifier
            advantage: Roll with advantage
            disadvantage: Roll with disadvantage
            
        Returns:
            Attack roll and damage result
        """
        # Roll attack
        attack_result = self.roll_dice("d20", attack_bonus, advantage, disadvantage)
        
        if not attack_result.get("success"):
            return attack_result
        
        # Determine damage dice
        if not damage_dice and weapon_name:
            damage_dice = self.WEAPON_DAMAGE.get(weapon_name.lower(), "d4")
        
        if not damage_dice:
            damage_dice = "d4"  # Default
        
        # Roll damage if hit
        damage_result = None
        hit = attack_result["total"] > 0  # Will be compared to AC
        
        if hit or attack_result.get("natural_20"):
            damage_result = self.roll_dice(damage_dice, damage_modifier)
            
            # Critical hit on natural 20
            if attack_result.get("natural_20"):
                # Roll damage dice again and add
                crit_damage = self.roll_dice(damage_dice, 0)
                if crit_damage.get("success"):
                    damage_result["total"] += crit_damage["total"]
                    damage_result["details"].append(f"Critical hit bonus: {crit_damage['total']}")
                    damage_result["critical_hit"] = True
        
        return {
            "success": True,
            "attack_roll": attack_result,
            "damage_roll": damage_result,
            "weapon": weapon_name,
            "hit": hit,
            "critical_hit": attack_result.get("natural_20", False)
        }
    
    def roll_saving_throw(
        self,
        ability_name: str,
        ability_modifier: int,
        proficiency_bonus: int = 0,
        proficient: bool = False,
        advantage: bool = False,
        disadvantage: bool = False
    ) -> Dict[str, Any]:
        """
        Roll a saving throw.
        
        Args:
            ability_name: Ability name
            ability_modifier: Ability modifier
            proficiency_bonus: Proficiency bonus
            proficient: Whether proficient in this save
            advantage: Roll with advantage
            disadvantage: Roll with disadvantage
            
        Returns:
            Saving throw result
        """
        return self.roll_ability_check(
            ability_name, ability_modifier, proficiency_bonus,
            proficient, advantage, disadvantage
        )
    
    def roll_initiative(self, dexterity_modifier: int) -> Dict[str, Any]:
        """
        Roll initiative (d20 + Dexterity modifier).
        
        Args:
            dexterity_modifier: Dexterity modifier
            
        Returns:
            Initiative roll result
        """
        result = self.roll_dice("d20", dexterity_modifier)
        if result.get("success"):
            result["initiative"] = result["total"]
            result["check_type"] = "initiative"
        return result
    
    def smart_roll(
        self,
        action: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Smart dice rolling based on action context.
        Automatically determines appropriate dice and modifiers.
        
        Args:
            action: Action description (e.g., "attack with sword", "strength check", "fireball damage")
            context: Optional context with character stats, etc.
            
        Returns:
            Appropriate roll result
        """
        action_lower = action.lower()
        context = context or {}
        
        # Determine roll type from action
        if "attack" in action_lower or "hit" in action_lower:
            # Attack roll
            attack_bonus = context.get("attack_bonus", 0)
            weapon = context.get("weapon") or self._extract_weapon(action_lower)
            damage_dice = context.get("damage_dice")
            damage_mod = context.get("damage_modifier", 0)
            
            return self.roll_attack(attack_bonus, weapon, damage_dice, damage_mod)
        
        elif "check" in action_lower or "skill" in action_lower:
            # Ability or skill check
            ability = self._extract_ability(action_lower)
            ability_mod = context.get(f"{ability.lower()}_modifier", 0)
            prof_bonus = context.get("proficiency_bonus", 0)
            proficient = context.get("proficient", False)
            
            return self.roll_ability_check(ability, ability_mod, prof_bonus, proficient)
        
        elif "save" in action_lower or "saving throw" in action_lower:
            # Saving throw
            ability = self._extract_ability(action_lower)
            ability_mod = context.get(f"{ability.lower()}_modifier", 0)
            prof_bonus = context.get("proficiency_bonus", 0)
            proficient = context.get("proficient", False)
            
            return self.roll_saving_throw(ability, ability_mod, prof_bonus, proficient)
        
        elif "initiative" in action_lower:
            # Initiative
            dex_mod = context.get("dexterity_modifier", 0)
            return self.roll_initiative(dex_mod)
        
        elif "damage" in action_lower:
            # Damage roll
            damage_dice = context.get("damage_dice") or self._extract_damage_dice(action_lower)
            damage_mod = context.get("damage_modifier", 0)
            return self.roll_dice(damage_dice or "d6", damage_mod)
        
        else:
            # Default: try to parse as dice notation
            dice_match = re.search(r'(\d*)d(\d+)', action_lower)
            if dice_match:
                dice_notation = dice_match.group(0)
                return self.roll_dice(dice_notation)
            else:
                # Default d20 roll
                return self.roll_dice("d20")
    
    def _extract_ability(self, text: str) -> str:
        """Extract ability name from text."""
        abilities = ["Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"]
        text_lower = text.lower()
        for ability in abilities:
            if ability.lower() in text_lower:
                return ability
        return "Strength"  # Default
    
    def _extract_weapon(self, text: str) -> Optional[str]:
        """Extract weapon name from text."""
        for weapon in self.WEAPON_DAMAGE.keys():
            if weapon in text.lower():
                return weapon
        return None
    
    def _extract_damage_dice(self, text: str) -> Optional[str]:
        """Extract damage dice notation from text."""
        dice_match = re.search(r'(\d*)d(\d+)', text.lower())
        if dice_match:
            return dice_match.group(0)
        return None

