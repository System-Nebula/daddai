"""
Tests for utility functions.
"""
import pytest
from unittest.mock import Mock
from src.utils.user_state_manager import UserStateManager


class TestUserStateManager:
    """Test user state management."""
    
    @pytest.mark.unit
    def test_set_get_user_state(self):
        """Test setting and getting user state."""
        manager = UserStateManager()
        
        manager.set_user_state("user1", "gold", 100)
        gold = manager.get_user_state("user1", "gold")
        
        assert gold == 100
    
    @pytest.mark.unit
    def test_get_all_states(self):
        """Test getting all user states."""
        manager = UserStateManager()
        
        manager.set_user_state("user1", "gold", 100)
        manager.set_user_state("user1", "level", 5)
        
        all_states = manager.get_user_all_states("user1")
        
        assert all_states["gold"] == 100
        assert all_states["level"] == 5
    
    @pytest.mark.unit
    def test_increment_user_state(self):
        """Test incrementing user state."""
        manager = UserStateManager()
        
        manager.set_user_state("user1", "gold", 100)
        manager.increment_user_state("user1", "gold", 50)
        
        gold = manager.get_user_state("user1", "gold")
        assert gold == 150
    
    @pytest.mark.unit
    def test_get_nonexistent_state(self):
        """Test getting state that doesn't exist."""
        manager = UserStateManager()
        
        gold = manager.get_user_state("user1", "gold")
        assert gold is None

