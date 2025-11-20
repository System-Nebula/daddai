"""
AgentMessage protocol for standardized agent-to-agent communication.
"""
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import uuid


class MessageType(Enum):
    """Types of agent messages."""
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    ERROR = "error"


class MessagePriority(Enum):
    """Message priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class AgentMessage:
    """
    Standardized message format for agent-to-agent communication.
    
    Attributes:
        message_id: Unique message identifier
        message_type: Type of message (REQUEST, RESPONSE, EVENT, ERROR)
        sender_id: ID of the agent sending the message
        receiver_id: ID of the target agent (None for events)
        correlation_id: ID to correlate request/response pairs
        action: Action or method name to invoke
        payload: Message data/content
        metadata: Additional metadata
        timestamp: Message creation timestamp
        priority: Message priority level
        timeout: Timeout in seconds for request messages
        retry_count: Number of retries attempted
    """
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    message_type: MessageType = MessageType.REQUEST
    sender_id: str = ""
    receiver_id: Optional[str] = None
    correlation_id: Optional[str] = None
    action: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    priority: MessagePriority = MessagePriority.NORMAL
    timeout: float = 30.0
    retry_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "message_id": self.message_id,
            "message_type": self.message_type.value,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "correlation_id": self.correlation_id,
            "action": self.action,
            "payload": self.payload,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority.value,
            "timeout": self.timeout,
            "retry_count": self.retry_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """Create message from dictionary."""
        return cls(
            message_id=data.get("message_id", str(uuid.uuid4())),
            message_type=MessageType(data.get("message_type", "request")),
            sender_id=data.get("sender_id", ""),
            receiver_id=data.get("receiver_id"),
            correlation_id=data.get("correlation_id"),
            action=data.get("action", ""),
            payload=data.get("payload", {}),
            metadata=data.get("metadata", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]) if isinstance(data.get("timestamp"), str) else datetime.utcnow(),
            priority=MessagePriority(data.get("priority", 2)),
            timeout=data.get("timeout", 30.0),
            retry_count=data.get("retry_count", 0)
        )
    
    def create_response(self, payload: Dict[str, Any], success: bool = True) -> "AgentMessage":
        """Create a response message for this request."""
        return AgentMessage(
            message_type=MessageType.RESPONSE if success else MessageType.ERROR,
            sender_id=self.receiver_id or "",
            receiver_id=self.sender_id,
            correlation_id=self.message_id,
            action=f"{self.action}_response",
            payload=payload,
            metadata={"original_action": self.action}
        )
    
    def create_error_response(self, error: str, error_code: Optional[str] = None) -> "AgentMessage":
        """Create an error response message."""
        return AgentMessage(
            message_type=MessageType.ERROR,
            sender_id=self.receiver_id or "",
            receiver_id=self.sender_id,
            correlation_id=self.message_id,
            action=f"{self.action}_error",
            payload={"error": error, "error_code": error_code},
            metadata={"original_action": self.action}
        )


@dataclass
class AgentResponse:
    """
    Standardized response format for agent operations.
    
    Attributes:
        success: Whether the operation succeeded
        data: Response data
        error: Error message if failed
        error_code: Optional error code
        metadata: Additional metadata
        execution_time: Time taken to execute (seconds)
    """
    success: bool = True
    data: Any = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "error_code": self.error_code,
            "metadata": self.metadata,
            "execution_time": self.execution_time
        }
    
    @classmethod
    def success_response(cls, data: Any = None, metadata: Optional[Dict[str, Any]] = None, execution_time: float = 0.0) -> "AgentResponse":
        """Create a success response."""
        return cls(
            success=True,
            data=data,
            metadata=metadata or {},
            execution_time=execution_time
        )
    
    @classmethod
    def error_response(cls, error: str, error_code: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> "AgentResponse":
        """Create an error response."""
        return cls(
            success=False,
            error=error,
            error_code=error_code,
            metadata=metadata or {}
        )

