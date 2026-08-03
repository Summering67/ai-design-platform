package server

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	"github.com/Summering67/ai-design-platform/apps/api/internal/auth"
	"github.com/Summering67/ai-design-platform/apps/api/internal/chat"
	"github.com/Summering67/ai-design-platform/apps/api/internal/config"
	"github.com/Summering67/ai-design-platform/apps/api/internal/database"
	"github.com/Summering67/ai-design-platform/apps/api/internal/logging"
	"github.com/Summering67/ai-design-platform/apps/api/internal/project"
	"go.uber.org/zap"
)

type HTTPServer struct {
	server *http.Server
}

func NewHTTPServer(config config.ServerConfig, handler http.Handler) *HTTPServer {
	return &HTTPServer{server: &http.Server{
		Addr:         config.Address,
		Handler:      handler,
		ReadTimeout:  config.ReadTimeout,
		WriteTimeout: config.WriteTimeout,
		IdleTimeout:  config.IdleTimeout,
	}}
}

func (server *HTTPServer) Serve() error {
	if err := server.server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		return fmt.Errorf("HTTP 服务异常退出: %w", err)
	}

	return nil
}

func (server *HTTPServer) Shutdown(ctx context.Context) error {
	if err := server.server.Shutdown(ctx); err != nil {
		return fmt.Errorf("关闭 HTTP 服务: %w", err)
	}

	return nil
}

func Run() error {
	runtimeConfig, err := config.Load()
	if err != nil {
		return fmt.Errorf("加载运行配置: %w", err)
	}

	logger, err := logging.New(runtimeConfig.Log)
	if err != nil {
		return err
	}
	defer func() { _ = logger.Sync() }()
	aiClient, err := chat.NewClient(http.DefaultClient, runtimeConfig.AI.BaseURL, runtimeConfig.AI.APIKey, runtimeConfig.AI.Model, runtimeConfig.AI.RequestTimeout)
	if err != nil {
		return fmt.Errorf("初始化 AI 客户端: %w", err)
	}

	connection, err := database.Open(context.Background(), runtimeConfig.Database)
	if err != nil {
		logger.Error("数据库初始化失败", zap.Error(err))
		return err
	}
	defer func() {
		if err := connection.Close(); err != nil {
			logger.Error("关闭数据库连接失败", zap.Error(err))
		}
	}()

	authService, err := auth.NewService(connection.DB, runtimeConfig.Auth.FixedUserPassword)
	if err != nil {
		return fmt.Errorf("初始化认证服务: %w", err)
	}
	projectService, err := project.NewService(connection.DB)
	if err != nil {
		return fmt.Errorf("初始化项目服务: %w", err)
	}
	router := NewApplicationRouter(logger, connection, runtimeConfig.Database.PingTimeout, runtimeConfig.Log.Environment, authService, project.NewHandler(projectService, aiClient))
	httpServer := NewHTTPServer(runtimeConfig.Server, router)
	serverErrors := make(chan error, 1)
	go func() { serverErrors <- httpServer.Serve() }()

	signalContext, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	logger.Info("HTTP 服务已启动", zap.String("address", runtimeConfig.Server.Address))

	select {
	case err := <-serverErrors:
		return err
	case <-signalContext.Done():
		logger.Info("正在关闭 HTTP 服务")
	}

	shutdownContext, cancel := context.WithTimeout(context.Background(), runtimeConfig.Server.ShutdownTimeout)
	defer cancel()
	if err := httpServer.Shutdown(shutdownContext); err != nil {
		return err
	}

	logger.Info("HTTP 服务已关闭")
	return nil
}
