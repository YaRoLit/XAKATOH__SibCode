import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.schemas import PriceMockResult, validate_result
from app.settings import prompt_text, settings, yaml_config


def _usage(response) -> tuple[int | None, int | None]:
    meta = getattr(response, "usage_metadata", None) or {}
    if not meta and hasattr(response, "response_metadata"):
        token_usage = (response.response_metadata or {}).get("token_usage") or {}
        return token_usage.get("prompt_tokens"), token_usage.get("completion_tokens")
    return meta.get("input_tokens"), meta.get("output_tokens")


def generate(spec: dict) -> tuple[PriceMockResult, dict]:
    version, system = prompt_text()
    temperature = float((yaml_config.get("llm") or {}).get("temperature", 0.3))
    llm = ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=temperature,
    )
    messages = [
        SystemMessage(content=system),
        HumanMessage(content=json.dumps(spec, ensure_ascii=False, default=str)),
    ]
    structured = llm.with_structured_output(PriceMockResult)
    try:
        result = structured.invoke(messages)
        tokens_in = tokens_out = None
    except Exception:
        raw = llm.invoke(messages)
        tokens_in, tokens_out = _usage(raw)
        content = raw.content if isinstance(raw.content, str) else json.dumps(raw.content)
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        result = PriceMockResult.model_validate_json(text.strip())
    if not isinstance(result, PriceMockResult):
        result = PriceMockResult.model_validate(result)
    validate_result(result)
    return result, {
        "prompt_version": version,
        "llm_model": settings.llm_model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    }
