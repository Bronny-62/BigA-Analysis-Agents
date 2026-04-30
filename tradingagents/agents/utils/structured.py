"""Shared helpers for invoking an agent with structured output and a graceful fallback.

The Portfolio Manager, Trader, and Research Manager all follow the same
canonical pattern:

1. At agent creation, wrap the LLM with ``with_structured_output(Schema)``
   so the model returns a typed Pydantic instance. If the provider does
   not support structured output (rare; mostly older Ollama models), the
   wrap is skipped and the agent uses free-text generation instead.
2. At invocation, run the structured call and render the result back to
   markdown. If the structured call itself fails for any reason
   (malformed JSON from a weak model, transient provider issue), fall
   back to a plain ``llm.invoke`` so the pipeline never blocks.

Centralising the pattern here keeps the agent factories small and ensures
all three agents log the same warnings when fallback fires.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Optional, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def _raw_attr(obj: Any, name: str) -> Any:
    try:
        return object.__getattribute__(obj, name)
    except AttributeError:
        return None


def _structured_output_disabled_reason(llm: Any) -> str | None:
    explicit_reason = _raw_attr(llm, "_tradingagents_structured_output_disabled_reason")
    if explicit_reason:
        return str(explicit_reason)

    if os.getenv("TRADINGAGENTS_ENABLE_DEEPSEEK_STRUCTURED_OUTPUT", "").strip().lower() in {"1", "true", "yes", "on"}:
        return None

    provider = _raw_attr(llm, "_tradingagents_provider") or _raw_attr(llm, "provider")
    if isinstance(provider, str) and provider.lower() == "deepseek":
        return "DeepSeek does not reliably support structured-output tool_choice"

    model_name = _raw_attr(llm, "model_name") or _raw_attr(llm, "model")
    if isinstance(model_name, str) and model_name.lower().startswith("deepseek"):
        return "DeepSeek does not reliably support structured-output tool_choice"
    return None


def bind_structured(llm: Any, schema: type[T], agent_name: str) -> Optional[Any]:
    """Return ``llm.with_structured_output(schema)`` or ``None`` if unsupported.

    Logs a warning when the binding fails so the user understands the agent
    will use free-text generation for every call instead of one-shot fallback.
    """
    disabled_reason = _structured_output_disabled_reason(llm)
    if disabled_reason:
        logger.info(
            "%s: structured output is disabled for this model (%s); "
            "falling back to free-text generation",
            agent_name,
            disabled_reason,
        )
        return None

    try:
        return llm.with_structured_output(schema)
    except (NotImplementedError, AttributeError) as exc:
        logger.warning(
            "%s: provider does not support with_structured_output (%s); "
            "falling back to free-text generation",
            agent_name, exc,
        )
        return None


def invoke_structured_or_freetext(
    structured_llm: Optional[Any],
    plain_llm: Any,
    prompt: Any,
    render: Callable[[T], str],
    agent_name: str,
) -> str:
    """Run the structured call and render to markdown; fall back to free-text on any failure.

    ``prompt`` is whatever the underlying LLM accepts (a string for chat
    invocations, a list of message dicts for chat models that take that
    shape). The same value is forwarded to the free-text path so the
    fallback sees the same input the structured call did.
    """
    if structured_llm is not None:
        try:
            result = structured_llm.invoke(prompt)
            return render(result)
        except Exception as exc:
            logger.warning(
                "%s: structured-output invocation failed (%s); retrying once as free text",
                agent_name, exc,
            )

    response = plain_llm.invoke(prompt)
    return response.content
