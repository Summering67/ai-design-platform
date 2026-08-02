package chat

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestClientCompleteConvertsRequestAndResponse(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(response http.ResponseWriter, request *http.Request) {
		if request.URL.Path != "/v1/chat/completions" {
			t.Errorf("上游路径不符合预期: %s", request.URL.Path)
		}
		if request.Header.Get("Authorization") != "Bearer test-key" {
			t.Error("上游认证信息不符合预期")
		}
		var input completionRequest
		if err := json.NewDecoder(request.Body).Decode(&input); err != nil {
			t.Errorf("解析上游请求失败: %v", err)
		}
		if input.Model != "test-model" || input.Stream || len(input.Messages) != 1 {
			t.Errorf("上游请求不符合预期: %#v", input)
		}
		response.Header().Set("Content-Type", "application/json")
		_, _ = response.Write([]byte(`{"choices":[{"message":{"role":"assistant","content":"  已完成  "}}]}`))
	}))
	defer server.Close()
	client, err := NewClient(server.Client(), server.URL+"/v1/", "test-key", "test-model", time.Second)
	if err != nil {
		t.Fatalf("创建 client 失败: %v", err)
	}

	message, err := client.Complete(context.Background(), []Message{{Role: RoleUser, Content: "开始"}})
	if err != nil {
		t.Fatalf("调用上游失败: %v", err)
	}
	if message.Role != RoleAssistant || message.Content != "已完成" {
		t.Fatalf("回复不符合预期: %#v", message)
	}
}

func TestClientCompleteMapsUnavailableResponses(t *testing.T) {
	tests := []struct {
		name   string
		status int
		body   string
	}{
		{name: "非成功状态", status: http.StatusUnauthorized, body: `{"secret":"do-not-forward"}`},
		{name: "响应格式错误", status: http.StatusOK, body: `{`},
		{name: "回复为空", status: http.StatusOK, body: `{"choices":[]}`},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(response http.ResponseWriter, _ *http.Request) {
				response.WriteHeader(test.status)
				_, _ = response.Write([]byte(test.body))
			}))
			defer server.Close()
			client, err := NewClient(server.Client(), server.URL, "test-key", "test-model", time.Second)
			if err != nil {
				t.Fatalf("创建 client 失败: %v", err)
			}

			_, err = client.Complete(context.Background(), []Message{{Role: RoleUser, Content: "开始"}})
			if !errors.Is(err, ErrUnavailable) {
				t.Fatalf("期望服务不可用错误，实际为 %v", err)
			}
			if err != nil && strings.Contains(err.Error(), "do-not-forward") {
				t.Fatal("错误不应包含上游响应正文")
			}
		})
	}
}

func TestClientCompleteTimesOut(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(response http.ResponseWriter, _ *http.Request) {
		time.Sleep(50 * time.Millisecond)
		_, _ = response.Write([]byte(`{"choices":[{"message":{"role":"assistant","content":"太晚"}}]}`))
	}))
	defer server.Close()
	client, err := NewClient(server.Client(), server.URL, "test-key", "test-model", 10*time.Millisecond)
	if err != nil {
		t.Fatalf("创建 client 失败: %v", err)
	}

	_, err = client.Complete(context.Background(), []Message{{Role: RoleUser, Content: "开始"}})
	if !errors.Is(err, ErrTimeout) {
		t.Fatalf("期望超时错误，实际为 %v", err)
	}
}

func TestClientCompleteStopsWhenCallerCancels(t *testing.T) {
	requestStarted := make(chan struct{})
	server := httptest.NewServer(http.HandlerFunc(func(_ http.ResponseWriter, request *http.Request) {
		close(requestStarted)
		select {
		case <-request.Context().Done():
		case <-time.After(50 * time.Millisecond):
		}
	}))
	defer server.Close()
	client, err := NewClient(server.Client(), server.URL, "test-key", "test-model", time.Second)
	if err != nil {
		t.Fatalf("创建 client 失败: %v", err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	go func() {
		<-requestStarted
		cancel()
	}()

	_, err = client.Complete(ctx, []Message{{Role: RoleUser, Content: "开始"}})
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("期望取消错误，实际为 %v", err)
	}
}
