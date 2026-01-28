"""Anthropic Claude model adapter."""

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, SecretStr

from elile.models.base import BaseModelAdapter, Message, MessageRole, ModelResponse, T


class AnthropicAdapter(BaseModelAdapter):
    """Adapter for Anthropic Claude models."""

    def __init__(self, api_key: SecretStr, model: str = "claude-sonnet-4-20250514") -> None:
        """Initialize the Anthropic adapter.

        Args:
            api_key: Anthropic API key.
            model: Model name to use.
        """
        self._model = model
        self._client = ChatAnthropic(
            api_key=api_key,
            model=model,
        )

    @property
    def model_name(self) -> str:
        """Return the model name being used."""
        return self._model

    def _convert_messages(self, messages: list[Message]) -> list[Any]:
        """Convert internal messages to LangChain format."""
        result: list[Any] = []
        for msg in messages:
            match msg.role:
                case MessageRole.SYSTEM:
                    result.append(SystemMessage(content=msg.content))
                case MessageRole.USER:
                    result.append(HumanMessage(content=msg.content))
                case MessageRole.ASSISTANT:
                    result.append(AIMessage(content=msg.content))
        return result

    async def generate(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ModelResponse:
        """Generate a response from Claude."""
        lc_messages = self._convert_messages(messages)
        response = await self._client.ainvoke(
            lc_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        usage = None
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = {
                "input_tokens": response.usage_metadata.get("input_tokens", 0),
                "output_tokens": response.usage_metadata.get("output_tokens", 0),
            }

        return ModelResponse(
            content=str(response.content),
            model=self._model,
            usage=usage,
            raw_response=response,
        )

    async def generate_structured(
        self,
        messages: list[Message],
        response_model: type[T],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> T:
        """Generate a structured response from Claude."""
        structured_client = self._client.with_structured_output(response_model)
        lc_messages = self._convert_messages(messages)
        response = await structured_client.ainvoke(
            lc_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response  # type: ignore[return-value]
