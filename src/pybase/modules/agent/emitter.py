import json
from typing import Literal

type StreamEventType = Literal["text", "thinking", "tool_call", "tool_result", "done", "error"]


def send_text(content: str) -> dict:
    return {"type": "text", "content": content}


def send_thinking(content: str) -> dict:
    return {"type": "thinking", "content": content}


def send_tool_call(id: str, name: str, args: dict) -> dict:
    return {"type": "tool_call", "id": id, "name": name, "args": args}


def send_tool_result(id: str, content: str) -> dict:
    return {"type": "tool_result", "id": id, "content": content}


def send_done(conversation_id: str | None = None) -> dict:
    result: dict = {"type": "done"}
    if conversation_id is not None:
        result["conversation_id"] = conversation_id
    return result


def send_error(content: str) -> dict:
    return {"type": "error", "content": content}


def format_sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"