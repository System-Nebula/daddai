"""
Unit tests for AgentMessage and AgentResponse.
"""
import pytest
from Refactored.src.agents.base.agent_message import (
    AgentMessage, AgentResponse, MessageType, MessagePriority
)


def test_agent_message_creation():
    """Test AgentMessage creation."""
    message = AgentMessage(
        sender_id="sender",
        receiver_id="receiver",
        action="test_action",
        payload={"test": "data"}
    )
    assert message.sender_id == "sender"
    assert message.receiver_id == "receiver"
    assert message.action == "test_action"
    assert message.message_type == MessageType.REQUEST


def test_agent_message_to_dict():
    """Test AgentMessage serialization."""
    message = AgentMessage(
        sender_id="sender",
        receiver_id="receiver",
        action="test_action",
        payload={"test": "data"}
    )
    data = message.to_dict()
    assert data["sender_id"] == "sender"
    assert data["action"] == "test_action"
    assert data["message_type"] == "request"


def test_agent_message_from_dict():
    """Test AgentMessage deserialization."""
    data = {
        "sender_id": "sender",
        "receiver_id": "receiver",
        "action": "test_action",
        "payload": {"test": "data"},
        "message_type": "request"
    }
    message = AgentMessage.from_dict(data)
    assert message.sender_id == "sender"
    assert message.action == "test_action"


def test_create_response():
    """Test creating response message."""
    request = AgentMessage(
        sender_id="sender",
        receiver_id="receiver",
        action="test_action",
        payload={}
    )
    response = request.create_response({"result": "success"})
    assert response.correlation_id == request.message_id
    assert response.receiver_id == request.sender_id
    assert response.message_type == MessageType.RESPONSE


def test_agent_response_success():
    """Test success response creation."""
    response = AgentResponse.success_response(data={"result": "success"})
    assert response.success is True
    assert response.data == {"result": "success"}


def test_agent_response_error():
    """Test error response creation."""
    response = AgentResponse.error_response("Test error", error_code="TEST_ERROR")
    assert response.success is False
    assert response.error == "Test error"
    assert response.error_code == "TEST_ERROR"

