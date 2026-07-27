"""
LLM Client wrapper.
FR-V1: Dual-auth strategy via config.py (ADC vs API Key).
Only Anthropic (Claude Sonnet) is implemented for v1.
"""

from typing import Any, AsyncGenerator
import json
import httpx

from app.core.config import get_settings, AIProvider


class LLMClient:
    """Wrapper around LLM APIs handling dual-provider (Anthropic / Gemini)."""

    def __init__(self):
        self.settings = get_settings()
        self.provider = self.settings.ai.resolved_provider
        self.model_name = self.settings.ai.resolved_model_name

        if self.provider == AIProvider.ANTHROPIC:
            from anthropic import AsyncAnthropic
            self.client = AsyncAnthropic(
                api_key=self.settings.ai.anthropic_api_key if self.settings.ai.anthropic_api_key else None
            )

    async def complete(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
    ) -> str:
        """Generate a single non-streaming completion from the LLM."""
        if self.provider == AIProvider.GEMINI:
            api_key = self.settings.ai.gemini_api_key
            if not api_key:
                raise ValueError("GEMINI_API_KEY is not set.")
            gemini_contents = []
            for m in messages:
                role = "user" if m["role"] == "user" else "model"
                gemini_contents.append({"role": role, "parts": [{"text": m["content"]}]})
            payload = {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": gemini_contents,
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 512},
            }
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={api_key}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            resp = await self.client.messages.create(
                model=self.model_name,
                max_tokens=512,
                system=system_prompt,
                messages=messages,
            )
            return resp.content[0].text

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream a chat completion from the LLM, yielding dict chunks."""
        
        if self.provider == AIProvider.GEMINI:
            # Manually stream using httpx (Google AI Studio REST API)
            api_key = self.settings.ai.gemini_api_key
            if not api_key:
                raise ValueError("GEMINI_API_KEY is not set.")
                
            # Construct standard Gemini format
            gemini_contents = []
            for m in messages:
                role = "user" if m["role"] == "user" else "model"
                gemini_contents.append({
                    "role": role,
                    "parts": [{"text": m["content"]}]
                })
                
            payload = {
                "systemInstruction": {
                    "parts": [{"text": system_prompt}]
                },
                "contents": gemini_contents,
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 1024,
                }
            }
            
            # Using alt=sse so we get Server-Sent Events
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:streamGenerateContent?alt=sse&key={api_key}"
            
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str and data_str != "[DONE]":
                                try:
                                    data = json.loads(data_str)
                                    if "candidates" in data and len(data["candidates"]) > 0:
                                        parts = data["candidates"][0].get("content", {}).get("parts", [])
                                        if parts and "text" in parts[0]:
                                            yield {"type": "chunk", "content": parts[0]["text"]}
                                        
                                        # Tool calls (function calls) in Gemini streaming
                                        if parts and "functionCall" in parts[0]:
                                            fc = parts[0]["functionCall"]
                                            yield {"type": "tool_call", "name": fc["name"], "args": fc["args"]}
                                except json.JSONDecodeError:
                                    pass

        else:
            # Anthropic stream
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
                "messages": messages,
            }
            if anthropic_tools:
                kwargs["tools"] = anthropic_tools

            stream = await self.client.messages.create(stream=True, **kwargs)
            async for event in stream:
                if event.type == "content_block_delta" and event.delta.type == "text_delta":
                    yield {"type": "chunk", "content": event.delta.text}
                elif event.type == "content_block_start" and event.content_block.type == "tool_use":
                    yield {"type": "tool_call", "name": event.content_block.name, "args": {}}
                elif event.type == "content_block_delta" and event.delta.type == "input_json_delta":
                    yield {"type": "tool_call_delta", "partial_json": event.delta.partial_json}
