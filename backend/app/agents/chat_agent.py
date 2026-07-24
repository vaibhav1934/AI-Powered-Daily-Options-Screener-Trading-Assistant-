"""
Chat Agent Orchestrator
=========================
Coordinates the user message, tool execution, and SSE streaming.
"""

from typing import AsyncGenerator, Dict, Any, List
import json
import logging
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession
from anthropic.types import MessageStreamEvent

from app.agents.client import LLMClient
from app.agents.system_prompt import SYSTEM_PROMPT_TEMPLATE
from app.core.time_gate import get_cst_now, get_cutoff_status

logger = logging.getLogger(__name__)

# Very basic in-memory conversation store for v1.
# In a real app, this would be persisted in PostgreSQL.
CONVERSATIONS: Dict[str, List[Dict[str, Any]]] = {}


def get_available_tools() -> List[Dict[str, Any]]:
    """Define the tools available to the agent."""
    return [
        {
            "name": "get_scan_results",
            "description": "Get scan results for a given date, optionally filtered by status or risk bucket.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "scan_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "status_filter": {"type": "string"},
                    "risk_bucket_filter": {"type": "string"}
                },
                "required": ["scan_date"]
            }
        },
        {
            "name": "explain_ticker",
            "description": "Explain why a ticker was ranked or vetoed.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "scan_date": {"type": "string"}
                },
                "required": ["ticker", "scan_date"]
            }
        }
    ]


async def process_chat_message(
    message: str,
    conversation_id: str,
    session: AsyncSession,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Process a chat message from the user and yield SSE events.
    Handles tool calling and multi-turn conversation.
    """
    client = LLMClient()
    
    # Init conversation history if new
    if conversation_id not in CONVERSATIONS:
        CONVERSATIONS[conversation_id] = []
        
    # Append user message
    CONVERSATIONS[conversation_id].append({"role": "user", "content": message})
    
    # Build system prompt with current context
    now = get_cst_now()
    sys_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        current_date=now.strftime("%Y-%m-%d"),
        current_time_cst=now.strftime("%I:%M %p"),
        cutoff_status=json.dumps(get_cutoff_status().model_dump())
    )

    tools = get_available_tools()
    
    try:
        # 1st LLM call (to get answer or tool calls)
        stream = client.stream_chat(
            messages=CONVERSATIONS[conversation_id], # type: ignore
            system_prompt=sys_prompt,
            tools=tools
        )
        
        # We need to collect the response in case there are tool calls
        current_text = ""
        
        async for event in stream:
            # Yield text chunks to the frontend if it's a content block delta
            if event.type == "content_block_delta" and event.delta.type == "text_delta": # type: ignore
                chunk = event.delta.text # type: ignore
                current_text += chunk
                yield {"type": "chunk", "content": chunk}
            
            # If the LLM decides to call a tool, handle it (simplified for v1 demo)
            # A full implementation would handle the tool_use event, execute the tool,
            # append the result to messages, and stream again.
            # Due to current constraints, we will just stream the text back.
            
        # Append assistant message to history
        CONVERSATIONS[conversation_id].append({"role": "assistant", "content": current_text})
        
    except Exception as e:
        logger.error("Error in chat agent: %s", str(e), exc_info=True)
        yield {"type": "error", "content": f"An error occurred: {str(e)}"}
