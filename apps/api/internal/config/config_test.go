package config

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestMain(main *testing.M) {
	_ = os.Setenv("API_LOCAL_ENV_FILE", "off")
	os.Exit(main.Run())
}

func TestLoadEnvironmentOverridesConfigFile(t *testing.T) {
	configPath := filepath.Join(t.TempDir(), "config.yaml")
	content := []byte(`
server:
  address: ":8081"
database:
  dsn: "postgres://file-value"
`)
	if err := os.WriteFile(configPath, content, 0o600); err != nil {
		t.Fatalf("写入测试配置失败: %v", err)
	}

	t.Setenv("API_CONFIG_FILE", configPath)
	t.Setenv("API_SERVER_ADDRESS", ":9090")
	t.Setenv("API_DATABASE_DSN", "postgres://environment-value")
	t.Setenv("API_AI_BASE_URL", "https://environment.example")
	t.Setenv("API_AI_API_KEY", "environment-key")
	t.Setenv("API_AUTH_FIXED_USER_PASSWORD", "test-password")

	loaded, err := Load()
	if err != nil {
		t.Fatalf("加载配置失败: %v", err)
	}
	if loaded.Server.Address != ":9090" {
		t.Fatalf("期望环境变量覆盖服务地址，实际为 %q", loaded.Server.Address)
	}
	if loaded.Database.DSN != "postgres://environment-value" {
		t.Fatalf("期望环境变量覆盖数据库 DSN，实际为 %q", loaded.Database.DSN)
	}
}

func TestLoadUsesLocalAIConfigInDevelopment(t *testing.T) {
	localPath := filepath.Join(t.TempDir(), ".env.local")
	if err := os.WriteFile(localPath, []byte("DS_BASE_URL=https://local.example\nDS_API_KEY=local-key\nAPI_AUTH_FIXED_USER_PASSWORD=local-password\n"), 0o600); err != nil {
		t.Fatalf("写入本地配置失败: %v", err)
	}
	t.Setenv("API_LOCAL_ENV_FILE", localPath)
	t.Setenv("API_DATABASE_DSN", "postgres://example")

	loaded, err := Load()
	if err != nil {
		t.Fatalf("加载配置失败: %v", err)
	}
	if loaded.AI.BaseURL != "https://local.example" || loaded.AI.APIKey != "local-key" || loaded.Auth.FixedUserPassword != "local-password" {
		t.Fatalf("本地 AI 配置不符合预期: %#v", loaded.AI)
	}
}

func TestLoadEnvironmentOverridesLocalAIConfig(t *testing.T) {
	localPath := filepath.Join(t.TempDir(), ".env.local")
	if err := os.WriteFile(localPath, []byte("DS_BASE_URL=https://local.example\nDS_API_KEY=local-key\n"), 0o600); err != nil {
		t.Fatalf("写入本地配置失败: %v", err)
	}
	t.Setenv("API_LOCAL_ENV_FILE", localPath)
	t.Setenv("API_DATABASE_DSN", "postgres://example")
	t.Setenv("API_AI_BASE_URL", "https://environment.example")
	t.Setenv("API_AI_API_KEY", "environment-key")
	t.Setenv("API_AUTH_FIXED_USER_PASSWORD", "test-password")

	loaded, err := Load()
	if err != nil {
		t.Fatalf("加载配置失败: %v", err)
	}
	if loaded.AI.BaseURL != "https://environment.example" || loaded.AI.APIKey != "environment-key" {
		t.Fatalf("环境变量未覆盖本地 AI 配置: %#v", loaded.AI)
	}
}

func TestLoadProductionDoesNotReadLocalAIConfig(t *testing.T) {
	localPath := filepath.Join(t.TempDir(), ".env.local")
	if err := os.WriteFile(localPath, []byte("DS_BASE_URL=https://local.example\nDS_API_KEY=local-key\n"), 0o600); err != nil {
		t.Fatalf("写入本地配置失败: %v", err)
	}
	t.Setenv("API_LOCAL_ENV_FILE", localPath)
	t.Setenv("API_DATABASE_DSN", "postgres://example")
	t.Setenv("API_LOG_ENVIRONMENT", "production")
	t.Setenv("API_AUTH_FIXED_USER_PASSWORD", "test-password")

	if _, err := Load(); err == nil {
		t.Fatal("production 缺少进程 AI 配置时应加载失败")
	}
}

func TestValidateRejectsInvalidConfig(t *testing.T) {
	tests := []struct {
		name   string
		change func(*Config)
	}{
		{name: "服务地址无效", change: func(config *Config) { config.Server.Address = "8080" }},
		{name: "数据库 DSN 为空", change: func(config *Config) { config.Database.DSN = "" }},
		{name: "空闲连接超过打开连接", change: func(config *Config) { config.Database.MaxIdleConns = 21 }},
		{name: "日志环境无效", change: func(config *Config) { config.Log.Environment = "staging" }},
		{name: "AI BaseURL 无效", change: func(config *Config) { config.AI.BaseURL = "invalid" }},
		{name: "AI APIKey 为空", change: func(config *Config) { config.AI.APIKey = "" }},
		{name: "AI Model 为空", change: func(config *Config) { config.AI.Model = "" }},
		{name: "AI 请求超时无效", change: func(config *Config) { config.AI.RequestTimeout = 0 }},
		{name: "固定用户密码为空", change: func(config *Config) { config.Auth.FixedUserPassword = "" }},
		{name: "HTTP 写超时不大于 AI 超时", change: func(config *Config) { config.Server.WriteTimeout = config.AI.RequestTimeout }},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			config := validConfig()
			test.change(&config)
			if err := config.Validate(); err == nil {
				t.Fatal("期望配置校验失败")
			}
		})
	}
}

func validConfig() Config {
	return Config{
		Server: ServerConfig{
			Address:         ":8080",
			ReadTimeout:     5 * time.Second,
			WriteTimeout:    75 * time.Second,
			IdleTimeout:     time.Minute,
			ShutdownTimeout: 10 * time.Second,
		},
		Database: DatabaseConfig{
			DSN:             "postgres://example",
			MaxOpenConns:    20,
			MaxIdleConns:    10,
			ConnMaxLifetime: 30 * time.Minute,
			PingTimeout:     3 * time.Second,
		},
		Log: LogConfig{Environment: "development", Level: "info"},
		AI: AIConfig{
			BaseURL:        "https://api.example.com",
			APIKey:         "example-key",
			Model:          "example-model",
			RequestTimeout: time.Minute,
		},
		Auth: AuthConfig{FixedUserPassword: "test-password"},
	}
}
