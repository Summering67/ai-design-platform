package auth

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
	"time"

	"gorm.io/gorm"
)

const (
	FixedUserID     = "00000000-0000-0000-0000-000000000001"
	FixedUserEmail  = "developer@local.test"
	SessionCookie   = "aidp_session"
	SessionDuration = 7 * 24 * time.Hour
)

var ErrUnauthorized = errors.New("未认证")

type User struct {
	ID          string `gorm:"type:uuid;primaryKey"`
	Email       string
	DisplayName string
}

func (User) TableName() string { return "users" }

type session struct {
	ID        string `gorm:"type:uuid;primaryKey"`
	UserID    string `gorm:"type:uuid"`
	TokenHash string
	ExpiresAt time.Time
}

func (session) TableName() string { return "user_sessions" }

type Service struct {
	database *gorm.DB
	password string
	now      func() time.Time
}

func NewService(database *gorm.DB, password string) (*Service, error) {
	if database == nil || strings.TrimSpace(password) == "" {
		return nil, errors.New("认证服务配置无效")
	}
	return &Service{database: database, password: password, now: time.Now}, nil
}

func (service *Service) Login(ctx context.Context, email, password string) (User, string, error) {
	if strings.TrimSpace(email) != FixedUserEmail || subtle.ConstantTimeCompare([]byte(password), []byte(service.password)) != 1 {
		return User{}, "", ErrUnauthorized
	}
	var user User
	if err := service.database.WithContext(ctx).First(&user, "id = ?", FixedUserID).Error; err != nil {
		return User{}, "", fmt.Errorf("读取固定用户: %w", err)
	}
	token, err := randomToken()
	if err != nil {
		return User{}, "", err
	}
	now := service.now().UTC()
	entry := session{ID: randomUUID(), UserID: user.ID, TokenHash: tokenHash(token), ExpiresAt: now.Add(SessionDuration)}
	if err := service.database.WithContext(ctx).Create(&entry).Error; err != nil {
		return User{}, "", fmt.Errorf("创建登录会话: %w", err)
	}
	return user, token, nil
}

func (service *Service) CurrentUser(ctx context.Context, token string) (User, error) {
	if strings.TrimSpace(token) == "" {
		return User{}, ErrUnauthorized
	}
	var entry session
	now := service.now().UTC()
	err := service.database.WithContext(ctx).Where("token_hash = ? AND expires_at > ?", tokenHash(token), now).First(&entry).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return User{}, ErrUnauthorized
	}
	if err != nil {
		return User{}, fmt.Errorf("读取登录会话: %w", err)
	}
	var user User
	if err := service.database.WithContext(ctx).First(&user, "id = ?", entry.UserID).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return User{}, ErrUnauthorized
		}
		return User{}, fmt.Errorf("读取会话用户: %w", err)
	}
	return user, nil
}

func (service *Service) Logout(ctx context.Context, token string) error {
	if strings.TrimSpace(token) == "" {
		return nil
	}
	if err := service.database.WithContext(ctx).Where("token_hash = ?", tokenHash(token)).Delete(&session{}).Error; err != nil {
		return fmt.Errorf("删除登录会话: %w", err)
	}
	return nil
}

func tokenHash(token string) string {
	digest := sha256.Sum256([]byte(token))
	return hex.EncodeToString(digest[:])
}

func randomToken() (string, error) {
	bytes := make([]byte, 32)
	if _, err := rand.Read(bytes); err != nil {
		return "", fmt.Errorf("生成会话令牌: %w", err)
	}
	return base64.RawURLEncoding.EncodeToString(bytes), nil
}

func randomUUID() string {
	bytes := make([]byte, 16)
	if _, err := rand.Read(bytes); err != nil {
		panic(err)
	}
	bytes[6] = (bytes[6] & 0x0f) | 0x40
	bytes[8] = (bytes[8] & 0x3f) | 0x80
	return fmt.Sprintf("%08x-%04x-%04x-%04x-%012x", bytes[:4], bytes[4:6], bytes[6:8], bytes[8:10], bytes[10:])
}
