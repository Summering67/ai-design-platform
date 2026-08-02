package chat

import (
	"errors"
	"strings"
	"testing"
)

func TestValidateMessages(t *testing.T) {
	validHistory := []Message{
		{Role: RoleUser, Content: "创建一个作品集"},
		{Role: RoleAssistant, Content: "你偏好什么风格？"},
		{Role: RoleUser, Content: "极简风格"},
	}
	tests := []struct {
		name     string
		messages []Message
		valid    bool
	}{
		{name: "合法多轮消息", messages: validHistory, valid: true},
		{name: "消息为空", messages: nil},
		{name: "消息过多", messages: make([]Message, MaxMessages+1)},
		{name: "角色无效", messages: []Message{{Role: "system", Content: "规则"}}},
		{name: "内容为空", messages: []Message{{Role: RoleUser, Content: ""}}},
		{name: "内容仅空白", messages: []Message{{Role: RoleUser, Content: "   "}}},
		{name: "内容过长", messages: []Message{{Role: RoleUser, Content: strings.Repeat("界", MaxContentRunes+1)}}},
		{name: "末条不是用户", messages: []Message{{Role: RoleUser, Content: "问题"}, {Role: RoleAssistant, Content: "回复"}}},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			err := ValidateMessages(test.messages)
			if test.valid && err != nil {
				t.Fatalf("合法消息校验失败: %v", err)
			}
			if !test.valid && !errors.Is(err, ErrInvalidRequest) {
				t.Fatalf("期望无效请求错误，实际为 %v", err)
			}
		})
	}
}
