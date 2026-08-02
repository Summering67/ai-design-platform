package chat

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
)

type completerFunc func(context.Context, []Message) (Message, error)

func (complete completerFunc) Complete(ctx context.Context, messages []Message) (Message, error) {
	return complete(ctx, messages)
}

func TestHandlerReturnsAssistantMessage(t *testing.T) {
	gin.SetMode(gin.TestMode)
	handler := NewHandler(completerFunc(func(_ context.Context, messages []Message) (Message, error) {
		if len(messages) != 3 {
			t.Fatalf("期望完整多轮历史，实际为 %d 条", len(messages))
		}
		return Message{Role: RoleAssistant, Content: "已完成"}, nil
	}))
	response := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodPost, "/api/chat", strings.NewReader(`{"messages":[{"role":"user","content":"开始"},{"role":"assistant","content":"继续吗"},{"role":"user","content":"继续"}]}`))
	request.Header.Set("Content-Type", "application/json")
	ginContext, _ := gin.CreateTestContext(response)
	ginContext.Request = request

	handler(ginContext)

	if response.Code != http.StatusOK || response.Body.String() != `{"message":{"role":"assistant","content":"已完成"}}` {
		t.Fatalf("响应不符合预期: %d %s", response.Code, response.Body.String())
	}
}

func TestHandlerRejectsInvalidRequestsBeforeCallingUpstream(t *testing.T) {
	gin.SetMode(gin.TestMode)
	tests := []struct {
		name string
		body string
	}{
		{name: "JSON 无效", body: `{`},
		{name: "字段未知", body: `{"messages":[{"role":"user","content":"开始"}],"unknown":true}`},
		{name: "消息无效", body: `{"messages":[{"role":"assistant","content":"回复"}]}`},
		{name: "请求过大", body: `{"messages":[{"role":"user","content":"` + strings.Repeat("x", MaxRequestBytes) + `"}]}`},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			called := false
			handler := NewHandler(completerFunc(func(context.Context, []Message) (Message, error) {
				called = true
				return Message{}, nil
			}))
			response := httptest.NewRecorder()
			request := httptest.NewRequest(http.MethodPost, "/api/chat", strings.NewReader(test.body))
			ginContext, _ := gin.CreateTestContext(response)
			ginContext.Request = request

			handler(ginContext)

			if called || response.Code != http.StatusBadRequest || !strings.Contains(response.Body.String(), `"code":"invalid_request"`) {
				t.Fatalf("非法请求响应不符合预期: called=%v code=%d body=%s", called, response.Code, response.Body.String())
			}
		})
	}
}

func TestHandlerMapsStableErrors(t *testing.T) {
	tests := []struct {
		name       string
		upstream   error
		statusCode int
		code       string
	}{
		{name: "服务不可用", upstream: errors.New("upstream secret detail"), statusCode: http.StatusBadGateway, code: "ai_unavailable"},
		{name: "服务超时", upstream: ErrTimeout, statusCode: http.StatusGatewayTimeout, code: "ai_timeout"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			response := httptest.NewRecorder()
			request := httptest.NewRequest(http.MethodPost, "/api/chat", strings.NewReader(`{"messages":[{"role":"user","content":"开始"}]}`))
			ginContext, _ := gin.CreateTestContext(response)
			ginContext.Request = request
			NewHandler(completerFunc(func(context.Context, []Message) (Message, error) {
				return Message{}, test.upstream
			}))(ginContext)

			if response.Code != test.statusCode || !strings.Contains(response.Body.String(), `"code":"`+test.code+`"`) || strings.Contains(response.Body.String(), "secret detail") {
				t.Fatalf("错误响应不符合预期: %d %s", response.Code, response.Body.String())
			}
		})
	}
}
