package chat

import (
	"errors"
	"strings"
	"unicode/utf8"
)

const (
	MaxMessages     = 50
	MaxContentRunes = 32000
	MaxRequestBytes = 512 * 1024
)

type Role string

const (
	RoleUser      Role = "user"
	RoleAssistant Role = "assistant"
)

var (
	ErrInvalidRequest = errors.New("对话请求无效")
	ErrUnavailable    = errors.New("AI 服务不可用")
	ErrTimeout        = errors.New("AI 服务响应超时")
)

type Message struct {
	Role    Role   `json:"role"`
	Content string `json:"content"`
}

func ValidateMessages(messages []Message) error {
	if len(messages) == 0 || len(messages) > MaxMessages {
		return ErrInvalidRequest
	}
	for _, message := range messages {
		if message.Role != RoleUser && message.Role != RoleAssistant {
			return ErrInvalidRequest
		}
		if strings.TrimSpace(message.Content) == "" || utf8.RuneCountInString(message.Content) > MaxContentRunes {
			return ErrInvalidRequest
		}
	}
	if messages[len(messages)-1].Role != RoleUser {
		return ErrInvalidRequest
	}

	return nil
}
