package project

import (
	"context"
	"crypto/rand"
	"errors"
	"fmt"
	"strings"
	"time"
	"unicode/utf8"

	"gorm.io/gorm"
)

const (
	maxContentRunes = 32000
	maxHistoryRunes = 120000
	leaseDuration   = 2 * time.Minute
)

var (
	ErrNotFound     = errors.New("项目不存在")
	ErrConflict     = errors.New("项目正在生成")
	ErrInvalid      = errors.New("消息无效")
	ErrNotRetryable = errors.New("消息不可重试")
)

type Service struct {
	database *gorm.DB
	now      func() time.Time
}

func NewService(database *gorm.DB) (*Service, error) {
	if database == nil {
		return nil, errors.New("项目服务数据库未初始化")
	}
	return &Service{database: database, now: time.Now}, nil
}

func (service *Service) Recent(ctx context.Context, userID string) ([]Project, error) {
	var projects []Project
	err := service.database.WithContext(ctx).Where("user_id = ?", userID).Order("updated_at DESC, id DESC").Limit(20).Find(&projects).Error
	if err != nil {
		return nil, fmt.Errorf("读取最近项目: %w", err)
	}
	return projects, nil
}

func (service *Service) Get(ctx context.Context, userID, projectID string) (Project, []Message, error) {
	var project Project
	err := service.database.WithContext(ctx).Where("id = ? AND user_id = ?", projectID, userID).First(&project).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return Project{}, nil, ErrNotFound
	}
	if err != nil {
		return Project{}, nil, fmt.Errorf("读取项目: %w", err)
	}
	var messages []Message
	err = service.database.WithContext(ctx).Where("project_id = ?", project.ID).Order("created_at ASC, id ASC").Find(&messages).Error
	if err != nil {
		return Project{}, nil, fmt.Errorf("读取项目消息: %w", err)
	}
	return project, messages, nil
}

func (service *Service) CreateWithMessage(ctx context.Context, userID, clientMessageID, content string) (Project, Message, Attempt, error) {
	if err := validate(content, clientMessageID); err != nil {
		return Project{}, Message{}, Attempt{}, err
	}
	now := service.now().UTC()
	project := Project{ID: id(), UserID: userID, Title: title(content), CreatedAt: now, UpdatedAt: now}
	message := Message{ID: id(), ProjectID: project.ID, ClientMessageID: &clientMessageID, Role: "user", Content: strings.TrimSpace(content), CreatedAt: now}
	attempt := newAttempt(project.ID, message.ID, now)
	err := service.database.WithContext(ctx).Transaction(func(transaction *gorm.DB) error {
		if err := transaction.Create(&project).Error; err != nil {
			return err
		}
		if err := transaction.Create(&message).Error; err != nil {
			return err
		}
		return transaction.Create(&attempt).Error
	})
	if err != nil {
		return Project{}, Message{}, Attempt{}, fmt.Errorf("创建项目消息: %w", err)
	}
	return project, message, attempt, nil
}

func (service *Service) AddMessage(ctx context.Context, userID, projectID, clientMessageID, content string) (Message, Attempt, bool, error) {
	if err := validate(content, clientMessageID); err != nil {
		return Message{}, Attempt{}, false, err
	}
	now := service.now().UTC()
	var message Message
	var attempt Attempt
	existing := false
	err := service.database.WithContext(ctx).Transaction(func(transaction *gorm.DB) error {
		var project Project
		if err := transaction.Where("id = ? AND user_id = ?", projectID, userID).First(&project).Error; err != nil {
			if errors.Is(err, gorm.ErrRecordNotFound) {
				return ErrNotFound
			}
			return err
		}
		if err := interruptExpired(transaction, projectID, now); err != nil {
			return err
		}
		if err := transaction.Where("project_id = ? AND client_message_id = ?", projectID, clientMessageID).First(&message).Error; err == nil {
			existing = true
			return transaction.Where("user_message_id = ?", message.ID).Order("created_at DESC, id DESC").First(&attempt).Error
		} else if !errors.Is(err, gorm.ErrRecordNotFound) {
			return err
		}
		var running Attempt
		if err := transaction.Where("project_id = ? AND status = ?", projectID, "running").First(&running).Error; err == nil {
			return ErrConflict
		} else if !errors.Is(err, gorm.ErrRecordNotFound) {
			return err
		}
		message = Message{ID: id(), ProjectID: projectID, ClientMessageID: &clientMessageID, Role: "user", Content: strings.TrimSpace(content), CreatedAt: now}
		attempt = newAttempt(projectID, message.ID, now)
		if err := transaction.Create(&message).Error; err != nil {
			return err
		}
		if err := transaction.Create(&attempt).Error; err != nil {
			return err
		}
		return transaction.Model(&project).Update("updated_at", now).Error
	})
	if err != nil {
		return Message{}, Attempt{}, false, err
	}
	return message, attempt, existing, nil
}

func (service *Service) Retry(ctx context.Context, userID, projectID, messageID string) (Project, Message, Attempt, error) {
	now := service.now().UTC()
	var project Project
	var message Message
	var attempt Attempt
	err := service.database.WithContext(ctx).Transaction(func(transaction *gorm.DB) error {
		if err := transaction.Where("id = ? AND user_id = ?", projectID, userID).First(&project).Error; err != nil {
			if errors.Is(err, gorm.ErrRecordNotFound) {
				return ErrNotFound
			}
			return err
		}
		if err := interruptExpired(transaction, projectID, now); err != nil {
			return err
		}
		if err := transaction.Where("id = ? AND project_id = ? AND role = ?", messageID, projectID, "user").First(&message).Error; err != nil {
			if errors.Is(err, gorm.ErrRecordNotFound) {
				return ErrNotRetryable
			}
			return err
		}
		var completed int64
		if err := transaction.Model(&Attempt{}).Where("user_message_id = ? AND status = ?", message.ID, "completed").Count(&completed).Error; err != nil {
			return err
		}
		if completed > 0 {
			return ErrNotRetryable
		}
		var running Attempt
		if err := transaction.Where("project_id = ? AND status = ?", projectID, "running").First(&running).Error; err == nil {
			return ErrConflict
		} else if !errors.Is(err, gorm.ErrRecordNotFound) {
			return err
		}
		attempt = newAttempt(projectID, message.ID, now)
		return transaction.Create(&attempt).Error
	})
	if err != nil {
		return Project{}, Message{}, Attempt{}, err
	}
	return project, message, attempt, nil
}

func (service *Service) Context(ctx context.Context, projectID, messageID string) ([]Message, error) {
	var target Message
	if err := service.database.WithContext(ctx).Where("id = ? AND project_id = ? AND role = ?", messageID, projectID, "user").First(&target).Error; err != nil {
		return nil, err
	}
	var attempts []Attempt
	if err := service.database.WithContext(ctx).Where("project_id = ? AND status = ? AND assistant_message_id IS NOT NULL", projectID, "completed").Order("created_at DESC, id DESC").Limit(24).Find(&attempts).Error; err != nil {
		return nil, err
	}
	messages := make([]Message, 0, len(attempts)*2+1)
	for index := len(attempts) - 1; index >= 0; index-- {
		var pair []Message
		if err := service.database.WithContext(ctx).Where("id IN ?", []string{attempts[index].UserMessageID, *attempts[index].AssistantMessageID}).Order("created_at ASC, id ASC").Find(&pair).Error; err != nil {
			return nil, err
		}
		messages = append(messages, pair...)
	}
	for len(messages) >= 2 && runeLength(messages)+utf8.RuneCountInString(target.Content) > maxHistoryRunes {
		messages = messages[2:]
	}
	return append(messages, target), nil
}

func (service *Service) Finish(ctx context.Context, attemptID, content string, failure error) (Message, Attempt, error) {
	now := service.now().UTC()
	var assistant Message
	var result Attempt
	err := service.database.WithContext(ctx).Transaction(func(transaction *gorm.DB) error {
		if err := transaction.First(&result, "id = ?", attemptID).Error; err != nil {
			return err
		}
		if result.Status != "running" {
			return nil
		}
		fields := map[string]any{"lease_expires_at": nil, "finished_at": now}
		if failure != nil || strings.TrimSpace(content) == "" {
			fields["status"] = "failed"
			fields["error_code"] = errorCode(failure)
			return transaction.Model(&result).Updates(fields).Error
		}
		assistant = Message{ID: id(), ProjectID: result.ProjectID, Role: "assistant", Content: strings.TrimSpace(content), CreatedAt: now}
		if err := transaction.Create(&assistant).Error; err != nil {
			return err
		}
		fields["status"] = "completed"
		fields["assistant_message_id"] = assistant.ID
		if err := transaction.Model(&result).Updates(fields).Error; err != nil {
			return err
		}
		result.AssistantMessageID = &assistant.ID
		result.Status = "completed"
		return transaction.Model(&Project{}).Where("id = ?", result.ProjectID).Update("updated_at", now).Error
	})
	return assistant, result, err
}

func (service *Service) Interrupt(ctx context.Context, projectID, attemptID string) (Attempt, error) {
	var attempt Attempt
	now := service.now().UTC()
	err := service.database.WithContext(ctx).Transaction(func(transaction *gorm.DB) error {
		if err := transaction.Where("id = ? AND project_id = ?", attemptID, projectID).First(&attempt).Error; err != nil {
			if errors.Is(err, gorm.ErrRecordNotFound) {
				return ErrNotFound
			}
			return err
		}
		if attempt.Status != "running" {
			return nil
		}
		attempt.Status = "interrupted"
		return transaction.Model(&attempt).Updates(map[string]any{"status": attempt.Status, "finished_at": now, "lease_expires_at": nil}).Error
	})
	return attempt, err
}

func interruptExpired(transaction *gorm.DB, projectID string, now time.Time) error {
	return transaction.Model(&Attempt{}).Where("project_id = ? AND status = ? AND lease_expires_at <= ?", projectID, "running", now).Updates(map[string]any{"status": "interrupted", "finished_at": now, "lease_expires_at": nil}).Error
}
func newAttempt(projectID, messageID string, now time.Time) Attempt {
	lease := now.Add(leaseDuration)
	return Attempt{ID: id(), ProjectID: projectID, UserMessageID: messageID, Status: "running", LeaseExpiresAt: &lease, CreatedAt: now}
}
func validate(content, messageID string) error {
	if strings.TrimSpace(content) == "" || utf8.RuneCountInString(content) > maxContentRunes || len(messageID) != 36 {
		return ErrInvalid
	}
	return nil
}
func title(content string) string {
	value := strings.Join(strings.Fields(content), " ")
	runes := []rune(value)
	if len(runes) <= 30 {
		return value
	}
	return string(runes[:30]) + "..."
}
func runeLength(messages []Message) int {
	total := 0
	for _, message := range messages {
		total += utf8.RuneCountInString(message.Content)
	}
	return total
}
func errorCode(err error) string {
	if errors.Is(err, context.DeadlineExceeded) {
		return "ai_timeout"
	}
	return "ai_unavailable"
}
func id() string {
	bytes := make([]byte, 16)
	if _, err := rand.Read(bytes); err != nil {
		return fmt.Sprintf("%d", time.Now().UnixNano())
	}
	bytes[6] = (bytes[6] & 0x0f) | 0x40
	bytes[8] = (bytes[8] & 0x3f) | 0x80
	return fmt.Sprintf("%08x-%04x-%04x-%04x-%012x", bytes[:4], bytes[4:6], bytes[6:8], bytes[8:10], bytes[10:])
}
