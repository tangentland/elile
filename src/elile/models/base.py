"""Abstract base class for model adapters."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel


class MessageRole(str, Enum):
    """Role of a message in the conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    """A single message in a conversation."""

    role: MessageRole
    content: str


class ModelResponse(BaseModel):
    """Response from a model generation."""

    content: str
    model: str
    usage: dict[str, int] | None = None
    raw_response: Any = None


T = TypeVar("T", bound=BaseModel)


class BaseModelAdapter(ABC):
    """Abstract base class for model adapters."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name being used."""
        ...

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ModelResponse:
        """Generate a response from the model.

        Args:
            messages: List of messages in the conversation.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in the response.

        Returns:
            ModelResponse containing the generated content.
        """
        ...

    @abstractmethod
    async def generate_structured(
        self,
        messages: list[Message],
        response_model: type[T],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> T:
        """Generate a structured response from the model.

        Args:
            messages: List of messages in the conversation.
            response_model: Pydantic model class for the expected response.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in the response.

        Returns:
            Instance of response_model populated with the model's output.
        """
        ...
