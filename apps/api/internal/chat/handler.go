package chat

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"

	"github.com/gin-gonic/gin"
)

type Completer interface {
	Complete(ctx context.Context, messages []Message) (Message, error)
}

type chatRequest struct {
	Messages []Message `json:"messages"`
}

type chatResponse struct {
	Message Message `json:"message"`
}

type errorBody struct {
	Error errorResponse `json:"error"`
}

type errorResponse struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

func NewHandler(completer Completer) gin.HandlerFunc {
	return func(request *gin.Context) {
		request.Request.Body = http.MaxBytesReader(request.Writer, request.Request.Body, MaxRequestBytes)
		decoder := json.NewDecoder(request.Request.Body)
		decoder.DisallowUnknownFields()
		var input chatRequest
		if err := decoder.Decode(&input); err != nil || decoder.Decode(&struct{}{}) != io.EOF || ValidateMessages(input.Messages) != nil {
			writeError(request, http.StatusBadRequest, "invalid_request", "请求消息无效")
			return
		}

		message, err := completer.Complete(request.Request.Context(), input.Messages)
		if err == nil {
			request.JSON(http.StatusOK, chatResponse{Message: message})
			return
		}
		if errors.Is(err, context.Canceled) {
			return
		}
		if errors.Is(err, ErrTimeout) {
			writeError(request, http.StatusGatewayTimeout, "ai_timeout", "AI 服务响应超时")
			return
		}
		writeError(request, http.StatusBadGateway, "ai_unavailable", "AI 服务暂时不可用")
	}
}

func writeError(request *gin.Context, status int, code, message string) {
	request.JSON(status, errorBody{Error: errorResponse{Code: code, Message: message}})
}
