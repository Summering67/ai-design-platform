from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class InputQuestion:
    id: str
    text: str


class InputRequired(Exception):
    """结构化 Agent 调用要求用户补充信息时使用的控制信号。"""

    def __init__(self, questions: list[InputQuestion]) -> None:
        super().__init__("Agent 需要用户输入")
        self.questions = questions


class AgentError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class ContractError(AgentError):
    pass


class AgentCancelled(AgentError):
    def __init__(self) -> None:
        super().__init__("cancelled", "Agent 运行已取消")
