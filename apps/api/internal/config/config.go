package config

import (
	"errors"
	"fmt"
	"io"
	"net"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/spf13/viper"
	"go.uber.org/zap/zapcore"
)

type Config struct {
	Server   ServerConfig   `mapstructure:"server"`
	Database DatabaseConfig `mapstructure:"database"`
	Log      LogConfig      `mapstructure:"log"`
	AI       AIConfig       `mapstructure:"ai"`
}

type ServerConfig struct {
	Address         string        `mapstructure:"address"`
	ReadTimeout     time.Duration `mapstructure:"read_timeout"`
	WriteTimeout    time.Duration `mapstructure:"write_timeout"`
	IdleTimeout     time.Duration `mapstructure:"idle_timeout"`
	ShutdownTimeout time.Duration `mapstructure:"shutdown_timeout"`
}

type DatabaseConfig struct {
	DSN             string        `mapstructure:"dsn"`
	MaxOpenConns    int           `mapstructure:"max_open_conns"`
	MaxIdleConns    int           `mapstructure:"max_idle_conns"`
	ConnMaxLifetime time.Duration `mapstructure:"conn_max_lifetime"`
	PingTimeout     time.Duration `mapstructure:"ping_timeout"`
}

type LogConfig struct {
	Environment string `mapstructure:"environment"`
	Level       string `mapstructure:"level"`
}

type AIConfig struct {
	BaseURL        string        `mapstructure:"base_url"`
	APIKey         string        `mapstructure:"api_key"`
	Model          string        `mapstructure:"model"`
	RequestTimeout time.Duration `mapstructure:"request_timeout"`
}

var configKeys = []string{
	"server.address",
	"server.read_timeout",
	"server.write_timeout",
	"server.idle_timeout",
	"server.shutdown_timeout",
	"database.dsn",
	"database.max_open_conns",
	"database.max_idle_conns",
	"database.conn_max_lifetime",
	"database.ping_timeout",
	"log.environment",
	"log.level",
	"ai.base_url",
	"ai.api_key",
	"ai.model",
	"ai.request_timeout",
}

func Load() (Config, error) {
	reader := viper.New()
	reader.SetConfigName("config")
	reader.SetConfigType("yaml")
	reader.AddConfigPath("./config")
	reader.SetEnvPrefix("API")
	reader.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))
	reader.AutomaticEnv()
	setDefaults(reader)

	for _, key := range configKeys {
		if err := reader.BindEnv(key); err != nil {
			return Config{}, fmt.Errorf("绑定环境变量 %s: %w", key, err)
		}
	}

	if path := strings.TrimSpace(os.Getenv("API_CONFIG_FILE")); path != "" {
		reader.SetConfigFile(path)
	}

	if err := reader.ReadInConfig(); err != nil {
		var notFound viper.ConfigFileNotFoundError
		if reader.ConfigFileUsed() != "" || !errors.As(err, &notFound) {
			return Config{}, fmt.Errorf("读取配置文件: %w", err)
		}
	}
	if err := applyLocalAIConfig(reader); err != nil {
		return Config{}, err
	}

	var config Config
	if err := reader.Unmarshal(&config); err != nil {
		return Config{}, fmt.Errorf("解析配置: %w", err)
	}
	if err := config.Validate(); err != nil {
		return Config{}, err
	}

	return config, nil
}

func (config Config) Validate() error {
	if err := validateAddress(config.Server.Address); err != nil {
		return err
	}
	if config.Server.ReadTimeout <= 0 || config.Server.WriteTimeout <= 0 || config.Server.IdleTimeout <= 0 || config.Server.ShutdownTimeout <= 0 {
		return errors.New("服务超时必须为正数")
	}
	if strings.TrimSpace(config.Database.DSN) == "" {
		return errors.New("数据库 DSN 不能为空")
	}
	if config.Database.MaxOpenConns <= 0 || config.Database.MaxIdleConns <= 0 {
		return errors.New("数据库连接池大小必须为正数")
	}
	if config.Database.MaxIdleConns > config.Database.MaxOpenConns {
		return errors.New("数据库最大空闲连接数不能超过最大打开连接数")
	}
	if config.Database.ConnMaxLifetime <= 0 || config.Database.PingTimeout <= 0 {
		return errors.New("数据库连接生命周期和 Ping 超时必须为正数")
	}
	if config.Log.Environment != "development" && config.Log.Environment != "production" {
		return errors.New("日志环境必须为 development 或 production")
	}
	if _, err := zapcore.ParseLevel(config.Log.Level); err != nil {
		return fmt.Errorf("日志级别无效: %w", err)
	}
	if err := validateAIConfig(config.AI); err != nil {
		return err
	}
	if config.Server.WriteTimeout <= config.AI.RequestTimeout {
		return errors.New("HTTP 写超时必须大于 AI 请求超时")
	}

	return nil
}

// 提供开箱即用的默认配置值，确保在没有配置文件或环境变量的情况下，应用仍能启动并运行。
func validateAddress(address string) error {
	_, port, err := net.SplitHostPort(address)
	if err != nil {
		return fmt.Errorf("服务地址无效: %w", err)
	}
	portNumber, err := strconv.Atoi(port)
	if err != nil || portNumber < 1 || portNumber > 65535 {
		return errors.New("服务端口必须在 1 到 65535 之间")
	}

	return nil
}

func setDefaults(reader *viper.Viper) {
	reader.SetDefault("server.address", ":8080")
	reader.SetDefault("server.read_timeout", "5s")
	reader.SetDefault("server.write_timeout", "75s")
	reader.SetDefault("server.idle_timeout", "60s")
	reader.SetDefault("server.shutdown_timeout", "10s")
	reader.SetDefault("database.max_open_conns", 20)
	reader.SetDefault("database.max_idle_conns", 10)
	reader.SetDefault("database.conn_max_lifetime", "30m")
	reader.SetDefault("database.ping_timeout", "3s")
	reader.SetDefault("log.environment", "development")
	reader.SetDefault("log.level", "info")
	reader.SetDefault("ai.model", "deepseek-v4-flash")
	reader.SetDefault("ai.request_timeout", "60s")
}

func validateAIConfig(config AIConfig) error {
	parsedURL, err := url.ParseRequestURI(strings.TrimSpace(config.BaseURL))
	if err != nil || parsedURL.Host == "" || (parsedURL.Scheme != "http" && parsedURL.Scheme != "https") {
		return errors.New("AI BaseURL 必须是有效的 HTTP 地址")
	}
	if strings.TrimSpace(config.APIKey) == "" {
		return errors.New("AI APIKey 不能为空")
	}
	if strings.TrimSpace(config.Model) == "" {
		return errors.New("AI Model 不能为空")
	}
	if config.RequestTimeout <= 0 {
		return errors.New("AI 请求超时必须为正数")
	}

	return nil
}

func applyLocalAIConfig(reader *viper.Viper) error {
	if reader.GetString("log.environment") != "development" {
		return nil
	}
	path, required, err := localEnvPath()
	if err != nil || path == "" {
		return err
	}
	values, err := readDotEnv(path)
	if err != nil {
		if !required && errors.Is(err, os.ErrNotExist) {
			return nil
		}
		return fmt.Errorf("读取本地 AI 配置: %w", err)
	}
	if reader.GetString("ai.base_url") == "" {
		reader.SetDefault("ai.base_url", values["DS_BASE_URL"])
	}
	if reader.GetString("ai.api_key") == "" {
		reader.SetDefault("ai.api_key", values["DS_API_KEY"])
	}

	return nil
}

func localEnvPath() (string, bool, error) {
	if configuredPath := strings.TrimSpace(os.Getenv("API_LOCAL_ENV_FILE")); configuredPath != "" {
		if configuredPath == "off" {
			return "", false, nil
		}
		return configuredPath, true, nil
	}
	cwd, err := os.Getwd()
	if err != nil {
		return "", false, fmt.Errorf("获取当前目录: %w", err)
	}
	for directory := cwd; ; directory = filepath.Dir(directory) {
		if _, err := os.Stat(filepath.Join(directory, "pnpm-workspace.yaml")); err == nil {
			return filepath.Join(directory, ".env.local"), false, nil
		} else if !errors.Is(err, os.ErrNotExist) {
			return "", false, fmt.Errorf("检查 workspace 标记: %w", err)
		}
		parent := filepath.Dir(directory)
		if parent == directory {
			return "", false, nil
		}
	}
}

func readDotEnv(path string) (map[string]string, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer func() { _ = file.Close() }()
	reader := viper.New()
	reader.SetConfigType("env")
	if err := reader.ReadConfig(io.LimitReader(file, 64*1024)); err != nil {
		return nil, err
	}

	return map[string]string{
		"DS_BASE_URL": reader.GetString("DS_BASE_URL"),
		"DS_API_KEY":  reader.GetString("DS_API_KEY"),
	}, nil
}
