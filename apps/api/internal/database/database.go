package database

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/Summering67/ai-design-platform/apps/api/internal/config"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

type Connection struct {
	DB  *gorm.DB
	SQL *sql.DB
}

func Open(ctx context.Context, config config.DatabaseConfig) (*Connection, error) {
	database, err := gorm.Open(postgres.Open(config.DSN), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Silent),
	})
	if err != nil {
		return nil, fmt.Errorf("连接 PostgreSQL: %w", err)
	}

	sqlDatabase, err := database.DB()
	if err != nil {
		return nil, fmt.Errorf("获取底层数据库连接: %w", err)
	}
	sqlDatabase.SetMaxOpenConns(config.MaxOpenConns)
	sqlDatabase.SetMaxIdleConns(config.MaxIdleConns)
	sqlDatabase.SetConnMaxLifetime(config.ConnMaxLifetime)

	pingContext, cancel := context.WithTimeout(ctx, config.PingTimeout)
	defer cancel()
	if err := sqlDatabase.PingContext(pingContext); err != nil {
		_ = sqlDatabase.Close()
		return nil, fmt.Errorf("验证 PostgreSQL 连接: %w", err)
	}

	return &Connection{DB: database, SQL: sqlDatabase}, nil
}

func (connection *Connection) PingContext(ctx context.Context) error {
	if connection == nil || connection.SQL == nil {
		return fmt.Errorf("数据库连接未初始化")
	}

	return connection.SQL.PingContext(ctx)
}

func (connection *Connection) Close() error {
	if connection == nil || connection.SQL == nil {
		return nil
	}

	return connection.SQL.Close()
}
