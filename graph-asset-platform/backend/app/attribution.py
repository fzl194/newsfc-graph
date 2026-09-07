"""Agent 调用归因字段：REST 与 MCP 共用约束和 telemetry 映射。"""
from typing import Annotated

from pydantic import StringConstraints


AgentUsername = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]
AgentSessionId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


def telemetry_attribution(agent_username: str, agent_session_id: str) -> dict[str, str]:
    """将已校验的公共上下文字段映射到 telemetry 专列。"""
    return {"operator": agent_username, "session_id": agent_session_id}
