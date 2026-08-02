package logging

import (
	"fmt"

	"github.com/Summering67/ai-design-platform/apps/api/internal/config"
	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
)

func New(config config.LogConfig) (*zap.Logger, error) {
	level, err := zapcore.ParseLevel(config.Level)
	if err != nil {
		return nil, fmt.Errorf("解析日志级别: %w", err)
	}

	builders := map[string]func() zap.Config{
		"development": zap.NewDevelopmentConfig,
		"production":  zap.NewProductionConfig,
	}
	buildConfig, ok := builders[config.Environment]
	if !ok {
		return nil, fmt.Errorf("不支持的日志环境: %s", config.Environment)
	}

	zapConfig := buildConfig()
	zapConfig.Level = zap.NewAtomicLevelAt(level)
	logger, err := zapConfig.Build()
	if err != nil {
		return nil, fmt.Errorf("创建日志实例: %w", err)
	}

	return logger, nil
}
