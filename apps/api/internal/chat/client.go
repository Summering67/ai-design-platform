package chat

import (
	"bufio"
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

type Streamer interface {
	Stream(context.Context, []Message, func(string)) error
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

func (client *Client) Stream(ctx context.Context, messages []Message, onDelta func(string)) error {
	if err := ValidateMessages(messages); err != nil {
		return err
	}
	payload, err := json.Marshal(completionRequest{Messages: messages, Model: client.model, Stream: true})
	if err != nil {
		return fmt.Errorf("编码上游请求: %w", ErrUnavailable)
	}
	requestContext, cancel := context.WithTimeout(ctx, client.timeout)
	defer cancel()
	request, err := http.NewRequestWithContext(requestContext, http.MethodPost, client.endpoint, bytes.NewReader(payload))
	if err != nil {
		return fmt.Errorf("创建上游请求: %w", ErrUnavailable)
	}
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("Authorization", "Bearer "+client.apiKey)
	response, err := client.httpClient.Do(request)
	if err != nil {
		if errors.Is(ctx.Err(), context.Canceled) {
			return context.Canceled
		}
		if errors.Is(requestContext.Err(), context.DeadlineExceeded) {
			return ErrTimeout
		}
		return fmt.Errorf("调用上游: %w", ErrUnavailable)
	}
	defer func() { _ = response.Body.Close() }()
	if response.StatusCode < http.StatusOK || response.StatusCode >= http.StatusMultipleChoices {
		return fmt.Errorf("上游状态异常: %w", ErrUnavailable)
	}
	scanner := bufio.NewScanner(io.LimitReader(response.Body, maxUpstreamResponseBytes))
	scanner.Buffer(make([]byte, 4096), maxUpstreamResponseBytes)
	seen := false
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if !strings.HasPrefix(line, "data:") {
			continue
		}
		data := strings.TrimSpace(strings.TrimPrefix(line, "data:"))
		if data == "[DONE]" {
			break
		}
		var event struct {
			Choices []struct {
				Delta struct {
					Content string `json:"content"`
				} `json:"delta"`
			} `json:"choices"`
		}
		if err := json.Unmarshal([]byte(data), &event); err != nil {
			return fmt.Errorf("解析上游流: %w", ErrUnavailable)
		}
		for _, choice := range event.Choices {
			if choice.Delta.Content != "" {
				seen = true
				onDelta(choice.Delta.Content)
			}
		}
	}
	if err := scanner.Err(); err != nil {
		if errors.Is(requestContext.Err(), context.DeadlineExceeded) {
			return ErrTimeout
		}
		if errors.Is(ctx.Err(), context.Canceled) {
			return context.Canceled
		}
		return fmt.Errorf("读取上游流: %w", ErrUnavailable)
	}
	if !seen {
		return fmt.Errorf("上游回复为空: %w", ErrUnavailable)
	}
	return nil
}

func completionEndpoint(baseURL string) (string, error) {
	parsedURL, err := url.Parse(strings.TrimSpace(baseURL))
	if err != nil || parsedURL.Host == "" || (parsedURL.Scheme != "http" && parsedURL.Scheme != "https") || parsedURL.RawQuery != "" || parsedURL.Fragment != "" {
		return "", errors.New("AI BaseURL 无效")
	}
	parsedURL.Path = strings.TrimRight(parsedURL.Path, "/") + "/chat/completions"

	return parsedURL.String(), nil
}
