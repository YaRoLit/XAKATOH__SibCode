import base64
import logging
import time
from pathlib import Path
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from app.agent.tools import (
    CROP_IMAGE_TOOL_SCHEMA,
    CROP_TOOL_SCHEMA,
    SELECT_TOOL_SCHEMA,
    crop_photo_func,
    encode_image,
    select_photo_func,
    thumbnail_side,
)
from app.schemas import ReportNoPlan, ReportWithPlan
from app.settings import yaml_config

log = logging.getLogger("analysis_agent")


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    photos: list
    crop_dir: str
    crops_meta: list
    selected_views: list
    views_used: int
    llm_calls: int
    crops_used: int
    tokens_in: int
    tokens_out: int
    processing_ms: float


def _usage(response) -> tuple[int, int]:
    um = getattr(response, "usage_metadata", None)
    if isinstance(um, dict):
        return int(um.get("input_tokens") or 0), int(um.get("output_tokens") or 0)
    usage = getattr(response, "response_metadata", {}) or {}
    token_usage = usage.get("token_usage") or {}
    return int(token_usage.get("prompt_tokens") or 0), int(token_usage.get("completion_tokens") or 0)


def _tool_schemas(photo_count: int) -> list:
    if photo_count <= 1:
        return [CROP_TOOL_SCHEMA, CROP_IMAGE_TOOL_SCHEMA]
    return [SELECT_TOOL_SCHEMA, CROP_TOOL_SCHEMA]


def _limits(photo_count: int) -> tuple[int, int]:
    agent_cfg = yaml_config.get("agent") or {}
    max_views = int(agent_cfg.get("max_full_views", 4))
    if photo_count <= 1:
        return 0, int(agent_cfg.get("max_crops", 4))
    return max_views, int(agent_cfg.get("max_crops_total", 6))


def _make_llms(photo_count: int):
    from app.settings import settings

    llm = ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=float((yaml_config.get("llm") or {}).get("temperature", 0.1)),
        timeout=180,
    )
    llm_json = ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=float((yaml_config.get("llm") or {}).get("temperature", 0.1)),
        timeout=180,
        model_kwargs={"response_format": {"type": "json_object"}},
    )
    return llm.bind_tools(_tool_schemas(photo_count)), llm_json


def compile_graph(system_prompt: str, schema_cls, photo_count: int = 1):
    llm_with_tools, llm_json = _make_llms(photo_count)
    max_views, max_crops = _limits(photo_count)

    def agent_node(state: AgentState):
        t0 = time.perf_counter()
        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        response = llm_with_tools.invoke(messages)
        tin, tout = _usage(response)
        dt = time.perf_counter() - t0
        log.info(
            "agent node done",
            extra={"extra_data": {"dt": round(dt, 2), "tool_calls": bool(getattr(response, "tool_calls", None))}},
        )
        return {
            "messages": [response],
            "llm_calls": state.get("llm_calls", 0) + 1,
            "tokens_in": state.get("tokens_in", 0) + tin,
            "tokens_out": state.get("tokens_out", 0) + tout,
            "processing_ms": state.get("processing_ms", 0) + dt * 1000,
        }

    def tools_node(state: AgentState):
        last = state["messages"][-1]
        if not getattr(last, "tool_calls", None):
            return {"messages": []}
        photos = list(state.get("photos") or [])
        crop_dir = Path(state["crop_dir"])
        crop_dir.mkdir(parents=True, exist_ok=True)
        views_used = int(state.get("views_used") or 0)
        crops_used = int(state.get("crops_used") or 0)
        crops_meta = list(state.get("crops_meta") or [])
        selected_views = list(state.get("selected_views") or [])
        tool_messages = []
        for tc in last.tool_calls:
            args = dict(tc.get("args") or {})
            name = tc.get("name") or ""
            if name in {"crop_photo_tool", "crop_image_tool"}:
                if crops_used >= max_crops:
                    tool_messages.append(
                        ToolMessage(
                            content=f"Лимит кропов исчерпан ({max_crops}). Выдавай финальный отчёт.",
                            tool_call_id=tc["id"],
                        )
                    )
                    continue
                if "photo_index" not in args:
                    args["photo_index"] = 1
                try:
                    result = crop_photo_func(photos, **args)
                    if len(str(result)) > 1000:
                        crops_used += 1
                        crop_path = crop_dir / f"crop_{crops_used}.jpg"
                        crop_path.write_bytes(base64.b64decode(result))
                        crops_meta.append(
                            {
                                "index": crops_used,
                                "photo_index": args.get("photo_index"),
                                "reason": args.get("reason"),
                                "bbox": {
                                    "xmin": args.get("xmin"),
                                    "ymin": args.get("ymin"),
                                    "xmax": args.get("xmax"),
                                    "ymax": args.get("ymax"),
                                },
                                "local_path": str(crop_path),
                                "storage_key": None,
                            }
                        )
                        content = [
                            {
                                "type": "text",
                                "text": f"Кроп фото {args.get('photo_index')} получен. Причина: {args.get('reason', '')}",
                            },
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{result}"}},
                        ]
                    else:
                        content = str(result)
                    tool_messages.append(ToolMessage(content=content, tool_call_id=tc["id"]))
                except Exception as exc:
                    log.exception("crop tool failed")
                    tool_messages.append(ToolMessage(content=f"Ошибка: {exc}", tool_call_id=tc["id"]))
                continue

            if name == "select_photo_tool":
                if views_used >= max_views:
                    tool_messages.append(
                        ToolMessage(
                            content=f"Лимит полных фото исчерпан ({max_views}). Выдавай финальный отчёт.",
                            tool_call_id=tc["id"],
                        )
                    )
                    continue
                try:
                    result = select_photo_func(photos, int(args.get("photo_index") or 1), str(args.get("reason") or ""))
                    if len(str(result)) > 1000:
                        views_used += 1
                        selected_views.append(int(args.get("photo_index") or 1))
                        content = [
                            {
                                "type": "text",
                                "text": f"Фото {args.get('photo_index')} целиком. Причина: {args.get('reason', '')}",
                            },
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{result}"}},
                        ]
                    else:
                        content = str(result)
                    tool_messages.append(ToolMessage(content=content, tool_call_id=tc["id"]))
                except Exception as exc:
                    log.exception("select photo failed")
                    tool_messages.append(ToolMessage(content=f"Ошибка: {exc}", tool_call_id=tc["id"]))
                continue

            tool_messages.append(ToolMessage(content=f"Неизвестный инструмент: {name}", tool_call_id=tc["id"]))
        return {
            "messages": tool_messages,
            "crops_meta": crops_meta,
            "selected_views": selected_views,
            "views_used": views_used,
            "crops_used": crops_used,
        }

    def final_node(state: AgentState):
        t0 = time.perf_counter()
        messages = state["messages"] + [HumanMessage(content="Выдай финальный структурированный отчёт.")]
        try:
            structured = llm_json.with_structured_output(schema_cls)
            response = structured.invoke(messages)
            payload = response.model_dump_json()
            tin, tout = _usage(response)
        except Exception as exc:
            log.warning("structured output failed: %s", exc)
            raw = llm_json.invoke(messages)
            payload = raw.content if isinstance(raw.content, str) else str(raw.content)
            tin, tout = _usage(raw)
        dt = time.perf_counter() - t0
        return {
            "messages": [AIMessage(content=payload)],
            "llm_calls": state.get("llm_calls", 0) + 1,
            "tokens_in": state.get("tokens_in", 0) + tin,
            "tokens_out": state.get("tokens_out", 0) + tout,
            "processing_ms": state.get("processing_ms", 0) + dt * 1000,
        }

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tools_node)
    workflow.add_node("final", final_node)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        lambda x: "tools" if getattr(x["messages"][-1], "tool_calls", None) else "final",
        {"tools": "tools", "final": "final"},
    )
    workflow.add_edge("tools", "agent")
    workflow.add_edge("final", END)
    return workflow.compile()


def encode_overview(image_path: str) -> str:
    image_cfg = yaml_config.get("image") or {}
    max_side = int(image_cfg.get("overview_max_side", 1024))
    quality = int(image_cfg.get("overview_quality", 85))
    return encode_image(image_path, max_side, quality)


def _caption(photo: dict) -> str:
    meta = photo.get("meta") or {}
    when = meta.get("datetime_original") or meta.get("captured_at") or "время неизвестно"
    yaw = meta.get("yaw")
    alt = meta.get("altitude")
    yaw_s = f"{yaw:.0f}" if isinstance(yaw, (int, float)) else "—"
    alt_s = f"{alt:.1f}" if isinstance(alt, (int, float)) else "—"
    return f"Фото {photo.get('index')} — {when}, азимут {yaw_s}°, высота {alt_s} м"


def run_agent(mode: str, photos: list[dict], crop_dir: str, context_text: str, system_prompt: str) -> dict:
    schema_cls = ReportWithPlan if mode == "with_plan" else ReportNoPlan
    n = max(len(photos), 1)
    app = compile_graph(system_prompt, schema_cls, photo_count=n)
    side = thumbnail_side(n)
    quality = 85 if n == 1 else 78
    content: list = [{"type": "text", "text": context_text}]
    for photo in photos:
        content.append({"type": "text", "text": _caption(photo)})
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{encode_image(photo['path'], side, quality)}"},
            }
        )
    initial = {
        "messages": [HumanMessage(content=content)],
        "photos": photos,
        "crop_dir": crop_dir,
        "crops_meta": [],
        "selected_views": [],
        "views_used": 0,
        "llm_calls": 0,
        "crops_used": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "processing_ms": 0.0,
    }
    final_state = app.invoke(initial)
    raw = final_state["messages"][-1].content
    report = None
    parse_error = None
    try:
        report = schema_cls.model_validate_json(raw)
    except Exception as exc:
        parse_error = str(exc)
        try:
            import json

            report = schema_cls.model_validate(json.loads(raw))
            parse_error = None
        except Exception as exc2:
            parse_error = str(exc2)
    return {
        "report": report,
        "raw": raw,
        "parse_error": parse_error,
        "crops_meta": final_state.get("crops_meta") or [],
        "selected_views": final_state.get("selected_views") or [],
        "llm_calls": final_state.get("llm_calls") or 0,
        "crops_used": final_state.get("crops_used") or 0,
        "tokens_in": final_state.get("tokens_in") or 0,
        "tokens_out": final_state.get("tokens_out") or 0,
        "processing_ms": int(final_state.get("processing_ms") or 0),
    }
