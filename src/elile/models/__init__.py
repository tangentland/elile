"""Model adapters for multi-model integration."""

from elile.models.base import BaseModelAdapter, Message, ModelResponse, MessageRole
from elile.models.registry import get_model

__all__ = [
    "BaseModelAdapter",
    "Message",
    "ModelResponse",
    "MessageRole",
    "get_model",
]
