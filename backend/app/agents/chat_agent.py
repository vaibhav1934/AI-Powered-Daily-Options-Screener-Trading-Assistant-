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

from app.agents.client import LLMClient
from app.agents.system_prompt import SYSTEM_PROMPT_TEMPLATE
from app.core.time_gate import get_cst_now, get_cutoff_status
from app.services.scan_service import get_scan_results, trigger_scan
from app.services.synthesis_service import check_compliance

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
        },
        {
            "name": "apply_ui_filter",
            "description": "Apply a filter to the user's UI watchlist to hide or show tickers based on criteria. Use this when the user asks to filter or hide tickers. Fields available: ticker, score, risk_bucket, price, list_type.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "description": "The field to filter on, e.g. price, risk_bucket, ticker"},
                    "operator": {"type": "string", "description": "The operator to use: =, <, >, or contains"},
                    "value": {"type": "string", "description": "The value to filter against as a string"}
                },
                "required": ["field", "operator", "value"]
            }
        },
        {
            "name": "trigger_scan",
            "description": "Trigger the full 50-factor / 10-layer universe scan for today. Use this when the user explicitly asks to run or trigger the scan, OR when scan data is empty and the user confirms they want to start it. Do NOT call this automatically without user confirmation.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "confirmed": {"type": "boolean", "description": "Must be true — user has confirmed they want to trigger the scan."}
                },
                "required": ["confirmed"]
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
    # Fetch today's results for context
    today_results = await get_scan_results(session, now.date())
    scan_summary = []
    for r in today_results:
        market_data = {}
        factor_evaluations = []
        if r.factor_results_json and isinstance(r.factor_results_json, dict):
            market_data = r.factor_results_json.get("market_data", {})
            for f in r.factor_results_json.get("results", []):
                if f.get("triggered") or f.get("vetoed"):
                    factor_evaluations.append({
                        "id": f.get("factor_id"),
                        "name": f.get("factor_name"),
                        "layer": f.get("layer_number"),
                        "triggered": f.get("triggered"),
                        "vetoed": f.get("vetoed"),
                        "detail": str(f.get("detail", ""))[:120],
                    })

        scan_summary.append({
            "ticker": r.ticker,
            "name": market_data.get("name", ""),
            "sector": market_data.get("sector", ""),
            "score": r.score,
            "status": r.status.value,
            "risk_bucket": r.risk_bucket.value if r.risk_bucket else "UNASSIGNED",
            "veto_rule": r.veto_rule,
            "veto_reason": r.veto_reason,
            "execution_details": {
                "entry_price": r.entry_price,
                "strike_price": r.strike_price,
                "stop_loss": r.stop_loss,
            },
            "live_market_data": market_data,
            "factor_evaluations_and_news": factor_evaluations,
        })
    
    scan_empty = len(scan_summary) == 0
    sys_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        current_date=now.strftime("%Y-%m-%d"),
        current_time_cst=now.strftime("%I:%M %p"),
        cutoff_status=json.dumps(get_cutoff_status().model_dump()),
        scan_results=json.dumps(scan_summary, indent=2),
        scan_empty=scan_empty,
    )

    tools = get_available_tools()
    
    try:
        # 1st LLM call (to get answer or tool calls)
        stream = client.stream_chat(
            messages=CONVERSATIONS[conversation_id][-10:], # type: ignore
            system_prompt=sys_prompt,
            tools=tools
        )
        
        # We need to collect the response in case there are tool calls
        current_text = ""
        current_tool_name = None
        current_tool_args_str = ""
        
        async for chunk in stream:
            if chunk["type"] == "chunk":
                current_text += chunk["content"]
                if not check_compliance(current_text):
                    logger.warning("[COMPLIANCE INTERVENTION] Advisory violation in chat stream. Redacting response.")
                    yield {"type": "error", "content": "\n\n[COMPLIANCE INTERVENTION: Response terminated per institutional compliance rules prohibiting direct trading recommendations (e.g. 'buy', 'sell', 'target price').]"}
                    return
                yield chunk
            elif chunk["type"] == "tool_call":
                current_tool_name = chunk["name"]
                # For Gemini, args might already be parsed dict
                if isinstance(chunk.get("args"), dict):
                    current_tool_args_str = json.dumps(chunk["args"])
                    yield chunk
                else:
                    current_tool_args_str = ""
            elif chunk["type"] == "tool_call_delta":
                current_tool_args_str += chunk["partial_json"]
            
            # If using Anthropic and stream ends, we should ideally yield the assembled tool call.
            # But the stream chunking in anthropic doesn't explicitly send a "tool_call_end".
            # We'll just yield it after the loop if we built one.

        if current_tool_name and current_tool_args_str:
            try:
                args = json.loads(current_tool_args_str)
                tool_result = None

                # Execute the tool
                if "trigger_scan" in current_tool_name:
                    if args.get("confirmed") is True:
                        # Run scan as background task so the SSE stream doesn't timeout
                        import asyncio
                        from app.db.session import async_session_factory

                        async def _run_scan_background():
                            try:
                                async with async_session_factory() as bg_session:
                                    result = await trigger_scan(bg_session)
                                    logger.info("Background scan complete: %s", result)
                            except Exception as scan_err:
                                logger.error("Background scan failed: %s", scan_err, exc_info=True)

                        task = asyncio.create_task(_run_scan_background())
                        global _bg_tasks
                        if '_bg_tasks' not in globals():
                            globals()['_bg_tasks'] = set()
                        _bg_tasks.add(task)
                        task.add_done_callback(_bg_tasks.discard)
                        
                        yield {"type": "chunk", "content": "\n\n⚙️ **Scan triggered!** The full 50-factor / 10-layer scan is now running in the background. This typically takes 30–90 seconds.\n\n📋 **What to do next:**\n1. Wait about 60 seconds for the scan to complete.\n2. Refresh the screener table page to see the newly scanned tickers.\n3. Come back to the chat and ask me anything about the results!\n"}
                    else:
                        tool_result = "Scan not triggered — user confirmation required."

                yield {"type": "tool_call", "name": current_tool_name, "args": args}
            except json.JSONDecodeError:
                pass

        # Append assistant message to history
        CONVERSATIONS[conversation_id].append({"role": "assistant", "content": current_text})
        
    except Exception as e:
        logger.error("Error in chat agent: %s", str(e), exc_info=True)
        err_msg = str(e)
        if "429" in err_msg or "Too Many Requests" in err_msg or "quota" in err_msg.lower():
            friendly_content = "\n\n⚠️ **AI Provider Rate Limit / Quota Exceeded (429)**: The AI API key has temporarily reached its per-minute request or token limit. Please wait **30–60 seconds** for the quota bucket to reset, then send your message again."
        elif "timeout" in err_msg.lower() or "readtimeout" in err_msg.lower():
            friendly_content = "\n\n⚠️ **AI Connection Timeout**: The AI provider took too long to respond or the streaming connection dropped. Please try your question again."
        else:
            friendly_content = f"\n\n⚠️ **AI Assistant Error**: {err_msg}"
        yield {"type": "error", "content": friendly_content}
