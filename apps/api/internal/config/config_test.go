package config

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

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

func TestValidateRejectsInvalidConfig(t *testing.T) {
	tests := []struct {
		name   string
		change func(*Config)
	}{
		{name: "服务地址无效", change: func(config *Config) { config.Server.Address = "8080" }},
		{name: "数据库 DSN 为空", change: func(config *Config) { config.Database.DSN = "" }},
		{name: "空闲连接超过打开连接", change: func(config *Config) { config.Database.MaxIdleConns = 21 }},
		{name: "日志环境无效", change: func(config *Config) { config.Log.Environment = "staging" }},
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
			WriteTimeout:    10 * time.Second,
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
	}
}
