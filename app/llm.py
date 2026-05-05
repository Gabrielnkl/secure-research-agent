# app/llm.py
import os
import json
import time
from openai import AsyncOpenAI
from pydantic import BaseModel
from typing import TypeVar, Type
import logging

logger = logging.getLogger(__name__)
_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

T = TypeVar("T", bound=BaseModel)


async def call_llm_structured(
    system: str,
    user: str,
    schema: Type[T],
    model: str = "gpt-4o",
    max_tokens: int = 1000,
    attempt_label: str = "",
) -> T:
    """
    Call the LLM and parse the response as a Pydantic model.
    Appends the JSON schema to the system prompt so the model knows the exact format.
    Raises ValueError if the response can't be parsed after stripping markdown fences.
    """
    schema_json = json.dumps(schema.model_json_schema(), indent=2)
    full_system = (
        f"{system}\n\n"
        f"You must respond with ONLY valid JSON matching this schema. "
        f"No preamble, no explanation, no markdown fences.\n\n"
        f"Schema:\n{schema_json}"
    )

    logger.info(f"LLM call [{attempt_label or schema.__name__}] model={model}")
    start = time.monotonic()

    response = await _client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": full_system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},  # OpenAI JSON mode — enforces valid JSON output
    )

    elapsed_ms = int((time.monotonic() - start) * 1000)

    # After getting response, log usage to events.jsonl:
    from app.observability.event_log import log_event, compute_cost
    from datetime import datetime
    log_event({
        "timestamp": datetime.utcnow().isoformat(),
        "step": attempt_label or schema.__name__,
        "model": model,
        "tokens_in": response.usage.prompt_tokens,
        "tokens_out": response.usage.completion_tokens,
        "cost_usd": compute_cost(model, response.usage.prompt_tokens, response.usage.completion_tokens),
        "latency_ms": elapsed_ms,
    })

    raw = response.choices[0].message.content.strip()

    # Strip markdown fences if present despite JSON mode
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]

    parsed = schema.model_validate_json(raw)
    logger.info(
        f"LLM call [{attempt_label or schema.__name__}] "
        f"tokens_in={response.usage.prompt_tokens} "
        f"tokens_out={response.usage.completion_tokens} "
        f"latency={elapsed_ms}ms"
    )
    return parsed