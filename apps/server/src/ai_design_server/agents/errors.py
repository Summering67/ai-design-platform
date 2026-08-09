from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class InputQuestionOption:
    label: str
    description: str


@dataclass(slots=True)
class InputQuestion:
    id: str
    text: str
    header: str = "需要确认"
    options: list[InputQuestionOption] = field(default_factory=list)
    is_other: bool = False


class InputRequired(Exception):
    """结构化 Agent 调用要求用户补充信息时使用的控制信号。"""

    def __init__(self, questions: list[InputQuestion]) -> None:
        super().__init__("Agent 需要用户输入")
        self.questions = questions
        self.source_stage: str | None = None
        self.source_task_id: str | None = None
        self.source_attempt: int | None = None


class AgentError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        path: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.path = path


class ContractError(AgentError):
    pass


class AgentCancelled(AgentError):
    def __init__(self) -> None:
        super().__init__("cancelled", "Agent 运行已取消")
