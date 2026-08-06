from __future__ import annotations


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
