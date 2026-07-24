"""
LLM Client wrapper.
FR-V1: Dual-auth strategy via config.py (ADC vs API Key).
Only Anthropic (Claude Sonnet) is implemented for v1.
"""

from typing import Any, AsyncGenerator

from anthropic import AsyncAnthropic, AsyncAnthropicVertex
from anthropic.types import MessageStreamEvent

from app.core.config import get_settings


class LLMClient:
    """Wrapper around Anthropic SDK handling dual-auth via VERTEX_AI flag."""

    def __init__(self):
        settings = get_settings()
        self.use_vertex = settings.ai.vertex_ai

        if self.use_vertex:
            # Vertex AI auth via Google ADC (Application Default Credentials)
            # Region/Project are automatically inferred from ADC environment variables
            self.client = AsyncAnthropicVertex(
                region="us-central1",
                project_id=settings.ai.google_cloud_project,
            )
            self.model_name = "claude-3-5-sonnet@20240620"
        else:
            # Direct Anthropic auth via API key
            self.client = AsyncAnthropic(
                api_key=settings.ai.anthropic_api_key.get_secret_value() if settings.ai.anthropic_api_key else None
            )
            self.model_name = "claude-3-5-sonnet-20240620"

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[MessageStreamEvent, None]:
        """Stream a chat completion from the LLM."""
        
        # Format for anthropic tool schema
        anthropic_tools = []
        if tools:
            for t in tools:
                anthropic_tools.append({
                    "name": t["name"],
                    "description": t["description"],
                    "input_schema": t["input_schema"]
                })

        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": messages, # type: ignore
        }

        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        stream = await self.client.messages.create(
            stream=True,
            **kwargs
        )
        
        async for event in stream:
            yield event
