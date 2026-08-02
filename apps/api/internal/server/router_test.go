package server

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
	"go.uber.org/zap/zaptest/observer"
)

type pingerFunc func(context.Context) error

func (ping pingerFunc) PingContext(ctx context.Context) error {
	return ping(ctx)
}

func TestHealthLive(t *testing.T) {
	response := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodGet, "/health/live", nil)
	NewRouter(zap.NewNop(), pingerFunc(func(context.Context) error { return nil }), time.Second, "development").ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("期望状态码 %d，实际为 %d", http.StatusOK, response.Code)
	}
	if response.Body.String() != `{"status":"ok"}` {
		t.Fatalf("存活响应不符合预期: %s", response.Body.String())
	}
}

func TestHealthReady(t *testing.T) {
	tests := []struct {
		name       string
		pingError  error
		statusCode int
		body       string
	}{
		{name: "数据库就绪", statusCode: http.StatusOK, body: `{"status":"ready"}`},
		{name: "数据库未就绪", pingError: errors.New("数据库不可用"), statusCode: http.StatusServiceUnavailable, body: `{"status":"not_ready"}`},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			response := httptest.NewRecorder()
			request := httptest.NewRequest(http.MethodGet, "/health/ready", nil)
			pinger := pingerFunc(func(ctx context.Context) error {
				if _, ok := ctx.Deadline(); !ok {
					t.Fatal("数据库 Ping context 必须包含截止时间")
				}
				return test.pingError
			})
			NewRouter(zap.NewNop(), pinger, 100*time.Millisecond, "development").ServeHTTP(response, request)

			if response.Code != test.statusCode {
				t.Fatalf("期望状态码 %d，实际为 %d", test.statusCode, response.Code)
			}
			if response.Body.String() != test.body {
				t.Fatalf("就绪响应不符合预期: %s", response.Body.String())
			}
		})
	}
}

func TestAccessLoggerRecordsRequiredFields(t *testing.T) {
	core, logs := observer.New(zapcore.InfoLevel)
	response := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodGet, "/health/live?secret=hidden", nil)
	NewRouter(zap.New(core), pingerFunc(func(context.Context) error { return nil }), time.Second, "development").ServeHTTP(response, request)

	entries := logs.FilterMessage("HTTP 请求完成").All()
	if len(entries) != 1 {
		t.Fatalf("期望一条访问日志，实际为 %d", len(entries))
	}
	fields := entries[0].ContextMap()
	for _, field := range []string{"method", "path", "status", "latency", "client_ip"} {
		if _, ok := fields[field]; !ok {
			t.Fatalf("访问日志缺少字段 %s", field)
		}
	}
	if fields["path"] != "/health/live" {
		t.Fatalf("访问日志不应包含查询参数: %v", fields["path"])
	}
}
