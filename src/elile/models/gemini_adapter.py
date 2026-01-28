"""Google Gemini model adapter."""

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import SecretStr

from elile.models.base import BaseModelAdapter, Message, MessageRole, ModelResponse, T


class GeminiAdapter(BaseModelAdapter):
    """Adapter for Google Gemini models."""

    def __init__(self, api_key: SecretStr, model: str = "gemini-2.0-flash") -> None:
        """Initialize the Gemini adapter.

        Args:
            api_key: Google API key.
            model: Model name to use.
        """
        self._model = model
        self._client = ChatGoogleGenerativeAI(
            google_api_key=api_key,
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
        """Generate a response from Gemini."""
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
        """Generate a structured response from Gemini."""
        structured_client = self._client.with_structured_output(response_model)
        lc_messages = self._convert_messages(messages)
        response = await structured_client.ainvoke(
            lc_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response  # type: ignore[return-value]
