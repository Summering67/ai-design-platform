package project

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"strings"
	"sync"

	"github.com/Summering67/ai-design-platform/apps/api/internal/auth"
	"github.com/Summering67/ai-design-platform/apps/api/internal/chat"
	"github.com/gin-gonic/gin"
)

type Handler struct {
	service *Service
	stream  chat.Streamer
	active  sync.Map
}
type sendRequest struct {
	MessageID string `json:"message_id"`
	Content   string `json:"content"`
}

func NewHandler(service *Service, stream chat.Streamer) *Handler {
	return &Handler{service: service, stream: stream}
}
func (handler *Handler) Recent(request *gin.Context) {
	user, _ := auth.CurrentUser(request)
	projects, err := handler.service.Recent(request.Request.Context(), user.ID)
	if err != nil {
		errorJSON(request, 500, "internal_error", "读取项目失败")
		return
	}
	request.JSON(http.StatusOK, gin.H{"projects": projects})
}
func (handler *Handler) Get(request *gin.Context) {
	user, _ := auth.CurrentUser(request)
	project, messages, err := handler.service.Get(request.Request.Context(), user.ID, request.Param("projectId"))
	if err != nil {
		writeDomainError(request, err)
		return
	}
	request.JSON(http.StatusOK, gin.H{"project": project, "messages": messages})
}

func (handler *Handler) Create(request *gin.Context) {
	input, ok := decode(request)
	if !ok {
		return
	}
	user, _ := auth.CurrentUser(request)
	project, message, attempt, err := handler.service.CreateWithMessage(request.Request.Context(), user.ID, input.MessageID, input.Content)
	if err != nil {
		writeDomainError(request, err)
		return
	}
	handler.generate(request, project, message, attempt)
}
func (handler *Handler) Send(request *gin.Context) {
	input, ok := decode(request)
	if !ok {
		return
	}
	user, _ := auth.CurrentUser(request)
	message, attempt, existing, err := handler.service.AddMessage(request.Request.Context(), user.ID, request.Param("projectId"), input.MessageID, input.Content)
	if err != nil {
		writeDomainError(request, err)
		return
	}
	if existing {
		request.JSON(http.StatusOK, gin.H{"message": message, "generation": attempt})
		return
	}
	project, _, err := handler.service.Get(request.Request.Context(), user.ID, request.Param("projectId"))
	if err != nil {
		writeDomainError(request, err)
		return
	}
	handler.generate(request, project, message, attempt)
}
func (handler *Handler) Retry(request *gin.Context) {
	user, _ := auth.CurrentUser(request)
	project, message, attempt, err := handler.service.Retry(request.Request.Context(), user.ID, request.Param("projectId"), request.Param("messageId"))
	if err != nil {
		writeDomainError(request, err)
		return
	}
	handler.generate(request, project, message, attempt)
}
func (handler *Handler) Stop(request *gin.Context) {
	user, _ := auth.CurrentUser(request)
	project, _, err := handler.service.Get(request.Request.Context(), user.ID, request.Param("projectId"))
	if err != nil {
		writeDomainError(request, err)
		return
	}
	attempt, err := handler.service.Interrupt(request.Request.Context(), project.ID, request.Param("generationId"))
	if err != nil {
		writeDomainError(request, err)
		return
	}
	if cancel, ok := handler.active.Load(request.Param("generationId")); ok {
		cancel.(context.CancelFunc)()
	}
	request.JSON(http.StatusOK, gin.H{"generation": attempt})
}

func (handler *Handler) generate(request *gin.Context, project Project, message Message, attempt Attempt) {
	history, err := handler.service.Context(request.Request.Context(), project.ID, message.ID)
	if err != nil {
		writeDomainError(request, err)
		return
	}
	messages := make([]chat.Message, 0, len(history))
	for _, item := range history {
		messages = append(messages, chat.Message{Role: chat.Role(item.Role), Content: item.Content})
	}
	request.Header("Content-Type", "text/event-stream")
	request.Header("Cache-Control", "no-cache")
	request.Header("Connection", "keep-alive")
	request.Stream(func(writer io.Writer) bool {
		streamContext, cancel := context.WithCancel(request.Request.Context())
		defer cancel()
		handler.active.Store(attempt.ID, cancel)
		defer handler.active.Delete(attempt.ID)
		writeEvent(writer, "generation", gin.H{"project_id": project.ID, "message_id": message.ID, "generation_id": attempt.ID})
		var content strings.Builder
		err := handler.stream.Stream(streamContext, messages, func(delta string) { content.WriteString(delta); writeEvent(writer, "delta", gin.H{"content": delta}) })
		if err != nil {
			if errors.Is(err, context.Canceled) || errors.Is(request.Request.Context().Err(), context.Canceled) {
				_, _ = handler.service.Interrupt(context.Background(), attempt.ProjectID, attempt.ID)
				writeEvent(writer, "interrupted", gin.H{"generation_id": attempt.ID})
				return false
			}
			_, result, _ := handler.service.Finish(context.Background(), attempt.ID, "", err)
			writeEvent(writer, "failed", gin.H{"generation_id": attempt.ID, "code": result.ErrorCode})
			return false
		}
		assistant, _, finishErr := handler.service.Finish(context.Background(), attempt.ID, content.String(), nil)
		if finishErr != nil {
			writeEvent(writer, "failed", gin.H{"generation_id": attempt.ID, "code": "internal_error"})
			return false
		}
		writeEvent(writer, "completed", gin.H{"generation_id": attempt.ID, "message": assistant})
		return false
	})
}
func decode(request *gin.Context) (sendRequest, bool) {
	decoder := json.NewDecoder(request.Request.Body)
	decoder.DisallowUnknownFields()
	var input sendRequest
	if err := decoder.Decode(&input); err != nil || decoder.Decode(&struct{}{}) != io.EOF {
		errorJSON(request, 400, "invalid_request", "请求无效")
		return sendRequest{}, false
	}
	return input, true
}
func writeEvent(writer io.Writer, event string, value any) {
	payload, _ := json.Marshal(value)
	_, _ = writer.Write([]byte("event: " + event + "\ndata: " + string(payload) + "\n\n"))
}
func writeDomainError(request *gin.Context, err error) {
	if errors.Is(err, ErrNotFound) {
		errorJSON(request, 404, "not_found", "项目不存在")
		return
	}
	if errors.Is(err, ErrConflict) {
		errorJSON(request, 409, "generation_in_progress", "项目正在生成")
		return
	}
	if errors.Is(err, ErrNotRetryable) {
		errorJSON(request, 409, "not_retryable", "消息不可重新生成")
		return
	}
	errorJSON(request, 400, "invalid_request", "请求无效")
}
func errorJSON(request *gin.Context, status int, code, message string) {
	request.JSON(status, gin.H{"error": gin.H{"code": code, "message": message}})
}
