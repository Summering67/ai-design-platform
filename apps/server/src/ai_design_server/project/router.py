from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..agents.contracts import load_default_generation_contract
from ..agents.runner import run_agent
from ..auth.router import current_user
from ..database import AttemptModel, InputRequestModel, MessageModel, ProjectModel, UserModel
from ..dependencies import get_session
from ..dto import (
    AttemptResponse,
    ClientMessageRequest,
    InputAnswersRequest,
    MessageResponse,
    ProjectDetailResponse,
    ProjectResponse,
)
from .service import ProjectService

router = APIRouter(prefix="/api/projects")


def get_project_service(request: Request) -> ProjectService:
    return request.app.state.project_service  # type: ignore[no-any-return]


@router.get("")
async def recent(
    user: UserModel = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    service: ProjectService = Depends(get_project_service),
) -> dict[str, list[ProjectResponse]]:
    return {"projects": [_project(item) for item in await service.recent(session, user.id)]}


@router.get("/{project_id}", response_model=ProjectDetailResponse, response_model_exclude_none=True)
async def get_project(
    project_id: str,
    user: UserModel = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    service: ProjectService = Depends(get_project_service),
) -> ProjectDetailResponse:
    project, messages = await service.get(session, user.id, project_id)
    pending = await service.pending_input(session, user.id, project_id)
    return ProjectDetailResponse(
        project=_project(project), messages=[_message(item) for item in messages], pending_input_request=_input_request(pending) if pending else None
    )


@router.post("")
async def create_project(
    body: ClientMessageRequest,
    request: Request,
    user: UserModel = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    service: ProjectService = Depends(get_project_service),
) -> StreamingResponse:
    project, message, attempt = await service.create_with_message(
        session, user.id, body.message_id, body.content
    )
    return _stream(request, service, project, message, attempt)


@router.post("/{project_id}/generations", response_model=None)
async def generate(
    project_id: str,
    body: ClientMessageRequest,
    request: Request,
    user: UserModel = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    service: ProjectService = Depends(get_project_service),
) -> StreamingResponse | dict[str, object]:
    message, attempt, existing = await service.add_message(
        session, user.id, project_id, body.message_id, body.content
    )
    project, _ = await service.get(session, user.id, project_id)
    return (
        {
            "message": jsonable_encoder(_message(message), exclude_none=True),
            "generation": _attempt(attempt),
        }
        if existing
        else _stream(request, service, project, message, attempt)
    )


@router.post("/{project_id}/messages/{message_id}/generations")
async def retry(
    project_id: str,
    message_id: str,
    request: Request,
    user: UserModel = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    service: ProjectService = Depends(get_project_service),
) -> StreamingResponse:
    project, message, attempt = await service.retry(session, user.id, project_id, message_id)
    return _stream(request, service, project, message, attempt)


@router.post("/{project_id}/generations/{generation_id}/stop")
async def stop(
    project_id: str,
    generation_id: str,
    request: Request,
    user: UserModel = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    service: ProjectService = Depends(get_project_service),
) -> dict[str, object]:
    attempt = await service.interrupt(session, project_id, generation_id, user.id)
    task = request.app.state.active_generations.get(generation_id)
    if task is not None:
        task.cancel()
    return {"generation": _attempt(attempt)}


@router.post("/{project_id}/generations/{generation_id}/input-requests/{request_id}/answers")
async def answer_input(
    project_id: str,
    generation_id: str,
    request_id: str,
    body: InputAnswersRequest,
    request: Request,
    user: UserModel = Depends(current_user),
    session: AsyncSession = Depends(get_session),
    service: ProjectService = Depends(get_project_service),
) -> StreamingResponse:
    project, message, attempt, inputs = await service.answer_input(
        session,
        user.id,
        project_id,
        generation_id,
        request_id,
        body.response_id,
        [item.model_dump() for item in body.answers],
    )
    return _stream(request, service, project, message, attempt, inputs)


def _stream(
    request: Request,
    service: ProjectService,
    project: ProjectModel,
    message: MessageModel,
    attempt: AttemptModel,
    input_context: list[dict[str, object]] | None = None,
) -> StreamingResponse:
    return StreamingResponse(
        _events(request, service, project, message, attempt, input_context or []),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


def _stream_replay(
    project: ProjectModel, message: MessageModel, attempt: AttemptModel
) -> StreamingResponse:
    async def replay() -> AsyncIterator[str]:
        yield _event(
            "generation",
            {"project_id": project.id, "message_id": message.id, "generation_id": attempt.id},
        )
        yield _event("completed", {"generation_id": attempt.id, "message": _message(message)})

    return StreamingResponse(replay(), media_type="text/event-stream")


async def _events(
    request: Request,
    service: ProjectService,
    project: ProjectModel,
    message: MessageModel,
    attempt: AttemptModel,
    input_context: list[dict[str, object]],
) -> AsyncIterator[str]:
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    request.app.state.logger.info(
        "Agent generation started",
        extra={"generation_id": attempt.id, "project_id": project.id},
    )
    yield _event(
        "generation",
        {"project_id": project.id, "message_id": message.id, "generation_id": attempt.id},
    )
    async def run() -> None:
        failure: BaseException | None = None
        document: object | None = None
        awaiting_input = False
        try:
            async for agent_event in run_agent(
                {"requirement": message.content, "generation_contract": load_default_generation_contract(), "generation_id": attempt.id, "resolved_user_inputs": input_context},
                request.app.state.agent_model,
                request.app.state.config.agent,
            ):
                if agent_event["event"] == "input_required":
                    payload = agent_event.get("payload", {})
                    async with request.app.state.database.session() as input_session:
                        input_request = await service.await_input(
                            input_session,
                            attempt.id,
                            agent_event.get("stage", "root"),
                            agent_event.get("taskId", "root"),
                            payload.get("questions", []),
                        )
                    awaiting_input = True
                    await queue.put(_event("input_required", {"generation_id": attempt.id, **_input_request(input_request)}))
                    continue
                await queue.put(_event("agent", agent_event))
                if agent_event["event"] == "result":
                    document = agent_event.get("payload", {}).get("document")
                if agent_event["event"] == "failed":
                    failure = RuntimeError("Agent 运行失败")
                    request.app.state.logger.warning(
                        "Agent generation failed",
                        extra={"generation_id": attempt.id, "code": agent_event.get("payload", {}).get("code", "agent_failed")},
                    )
        except asyncio.CancelledError:
            async with request.app.state.database.session() as interrupt_session:
                finished = await service.interrupt(interrupt_session, project.id, attempt.id)
            await queue.put(_event("interrupted", {"generation_id": finished.id}))
            await queue.put(None)
            return
        except BaseException as error:
            failure = error
        if awaiting_input:
            await queue.put(None)
            return
        async with request.app.state.database.session() as finish_session:
            assistant, finished = await service.finish(
                finish_session, attempt.id, "设计已生成。" if document is not None else "", failure
            )
        request.app.state.logger.info(
            "Agent generation finished",
            extra={"generation_id": finished.id, "status": finished.status},
        )
        event = (
            "completed"
            if assistant is not None
            else "interrupted"
            if finished.status == "interrupted"
            else "failed"
        )
        payload: object = (
            {"generation_id": finished.id, "message": _message(assistant), "document": document}
            if assistant is not None
            else {"generation_id": finished.id}
            if event == "interrupted"
            else {"generation_id": finished.id, "code": finished.error_code or "ai_unavailable"}
        )
        await queue.put(_event(event, payload))
        await queue.put(None)

    task = asyncio.create_task(run())
    request.app.state.active_generations[attempt.id] = task
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
        await task
    finally:
        # 客户端断开时，必须终止上游 HTTPX 流并释放 generation 租约。
        # stop 路由也会取消同一个 task；这里保持幂等，避免重复写入状态。
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        request.app.state.active_generations.pop(attempt.id, None)


def _event(name: str, payload: object) -> str:
    encoded = jsonable_encoder(payload, exclude_none=True)
    return (
        f"event: {name}\ndata: {json.dumps(encoded, ensure_ascii=False, separators=(',', ':'))}\n\n"
    )


def _project(item: ProjectModel) -> ProjectResponse:
    return ProjectResponse(
        id=item.id,
        user_id=item.user_id,
        title=item.title,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _message(item: MessageModel) -> MessageResponse:
    return MessageResponse(
        id=item.id,
        project_id=item.project_id,
        client_message_id=item.client_message_id,
        role=item.role,
        content=item.content,
        created_at=item.created_at,
    )


def _attempt(item: AttemptModel) -> dict[str, object]:
    return AttemptResponse(
        id=item.id,
        project_id=item.project_id,
        user_message_id=item.user_message_id,
        assistant_message_id=item.assistant_message_id,
        status=item.status,
        error_code=item.error_code,
        lease_expires_at=item.lease_expires_at,
        created_at=item.created_at,
        finished_at=item.finished_at,
    ).model_dump(mode="json", exclude_none=True)


def _input_request(item: InputRequestModel) -> dict[str, object]:
    return {
        "id": item.id,
        "generation_id": item.generation_id,
        "source_stage": item.source_stage,
        "source_task_id": item.source_task_id,
        "round": item.round,
        "questions": item.questions,
        "status": item.status,
    }
