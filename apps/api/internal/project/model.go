package project

import "time"

type Project struct {
	ID        string    `gorm:"type:uuid;primaryKey" json:"id"`
	UserID    string    `gorm:"type:uuid" json:"user_id"`
	Title     string    `json:"title"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

func (Project) TableName() string { return "projects" }

type Message struct {
	ID              string    `gorm:"type:uuid;primaryKey" json:"id"`
	ProjectID       string    `gorm:"type:uuid" json:"project_id"`
	ClientMessageID *string   `gorm:"type:uuid" json:"client_message_id,omitempty"`
	Role            string    `json:"role"`
	Content         string    `json:"content"`
	CreatedAt       time.Time `json:"created_at"`
}

func (Message) TableName() string { return "messages" }

type Attempt struct {
	ID                 string     `gorm:"type:uuid;primaryKey" json:"id"`
	ProjectID          string     `gorm:"type:uuid" json:"project_id"`
	UserMessageID      string     `gorm:"type:uuid" json:"user_message_id"`
	AssistantMessageID *string    `gorm:"type:uuid" json:"assistant_message_id,omitempty"`
	Status             string     `json:"status"`
	ErrorCode          *string    `json:"error_code,omitempty"`
	LeaseExpiresAt     *time.Time `json:"lease_expires_at,omitempty"`
	CreatedAt          time.Time  `json:"created_at"`
	FinishedAt         *time.Time `json:"finished_at,omitempty"`
}

func (Attempt) TableName() string { return "generation_attempts" }
