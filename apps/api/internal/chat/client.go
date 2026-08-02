package chat

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

const maxUpstreamResponseBytes = 1024 * 1024

type Client struct {
	httpClient *http.Client
	endpoint   string
	apiKey     string
	model      string
	timeout    time.Duration
}

type completionRequest struct {
	Messages []Message `json:"messages"`
	Model    string    `json:"model"`
	Stream   bool      `json:"stream"`
}

type completionResponse struct {
	Choices []struct {
		Message Message `json:"message"`
	} `json:"choices"`
}

func NewClient(httpClient *http.Client, baseURL, apiKey, model string, timeout time.Duration) (*Client, error) {
	endpoint, err := completionEndpoint(baseURL)
	if err != nil {
		return nil, err
	}
	if httpClient == nil {
		httpClient = http.DefaultClient
	}

	return &Client{
		httpClient: httpClient,
		endpoint:   endpoint,
		apiKey:     apiKey,
		model:      model,
		timeout:    timeout,
	}, nil
}

func (client *Client) Complete(ctx context.Context, messages []Message) (Message, error) {
	if err := ValidateMessages(messages); err != nil {
		return Message{}, err
	}
	payload, err := json.Marshal(completionRequest{Messages: messages, Model: client.model, Stream: false})
	if err != nil {
		return Message{}, fmt.Errorf("编码上游请求: %w", ErrUnavailable)
	}
	requestContext, cancel := context.WithTimeout(ctx, client.timeout)
	defer cancel()
	request, err := http.NewRequestWithContext(requestContext, http.MethodPost, client.endpoint, bytes.NewReader(payload))
	if err != nil {
		return Message{}, fmt.Errorf("创建上游请求: %w", ErrUnavailable)
	}
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("Authorization", "Bearer "+client.apiKey)

	response, err := client.httpClient.Do(request)
	if err != nil {
		if errors.Is(ctx.Err(), context.Canceled) {
			return Message{}, context.Canceled
		}
		if errors.Is(requestContext.Err(), context.DeadlineExceeded) {
			return Message{}, ErrTimeout
		}
		return Message{}, fmt.Errorf("调用上游: %w", ErrUnavailable)
	}
	defer func() { _ = response.Body.Close() }()
	if response.StatusCode < http.StatusOK || response.StatusCode >= http.StatusMultipleChoices {
		return Message{}, fmt.Errorf("上游状态异常: %w", ErrUnavailable)
	}

	var completion completionResponse
	decoder := json.NewDecoder(io.LimitReader(response.Body, maxUpstreamResponseBytes))
	if err := decoder.Decode(&completion); err != nil || len(completion.Choices) == 0 {
		return Message{}, fmt.Errorf("解析上游响应: %w", ErrUnavailable)
	}
	message := completion.Choices[0].Message
	message.Content = strings.TrimSpace(message.Content)
	if message.Role != RoleAssistant || message.Content == "" {
		return Message{}, fmt.Errorf("上游回复为空: %w", ErrUnavailable)
	}

	return message, nil
}

func completionEndpoint(baseURL string) (string, error) {
	parsedURL, err := url.Parse(strings.TrimSpace(baseURL))
	if err != nil || parsedURL.Host == "" || (parsedURL.Scheme != "http" && parsedURL.Scheme != "https") || parsedURL.RawQuery != "" || parsedURL.Fragment != "" {
		return "", errors.New("AI BaseURL 无效")
	}
	parsedURL.Path = strings.TrimRight(parsedURL.Path, "/") + "/chat/completions"

	return parsedURL.String(), nil
}
