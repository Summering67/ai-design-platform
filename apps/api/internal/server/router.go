package server

import (
	"context"
	"net/http"
	"runtime/debug"
	"time"

	"github.com/Summering67/ai-design-platform/apps/api/internal/auth"
	"github.com/Summering67/ai-design-platform/apps/api/internal/project"
	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

type Pinger interface {
	PingContext(ctx context.Context) error
}

func NewRouter(logger *zap.Logger, pinger Pinger, pingTimeout time.Duration, environment string) http.Handler {
	modes := map[string]string{
		"development": gin.DebugMode,
		"production":  gin.ReleaseMode,
	}
	gin.SetMode(modes[environment])

	router := gin.New()
	router.Use(accessLogger(logger), recovery(logger))
	router.GET("/health/live", func(context *gin.Context) {
		context.JSON(http.StatusOK, gin.H{"status": "ok"})
	})
	router.GET("/health/ready", func(request *gin.Context) {
		pingContext, cancel := context.WithTimeout(request.Request.Context(), pingTimeout)
		defer cancel()
		if err := pinger.PingContext(pingContext); err != nil {
			logger.Warn("数据库未就绪", zap.Error(err))
			request.JSON(http.StatusServiceUnavailable, gin.H{"status": "not_ready"})
			return
		}

		request.JSON(http.StatusOK, gin.H{"status": "ready"})
	})
	return router
}

func NewApplicationRouter(logger *zap.Logger, pinger Pinger, pingTimeout time.Duration, environment string, authService *auth.Service, projects *project.Handler) http.Handler {
	modes := map[string]string{"development": gin.DebugMode, "production": gin.ReleaseMode}
	gin.SetMode(modes[environment])
	router := gin.New()
	router.Use(accessLogger(logger), recovery(logger))
	router.GET("/health/live", func(context *gin.Context) { context.JSON(http.StatusOK, gin.H{"status": "ok"}) })
	router.GET("/health/ready", func(request *gin.Context) {
		pingContext, cancel := context.WithTimeout(request.Request.Context(), pingTimeout)
		defer cancel()
		if err := pinger.PingContext(pingContext); err != nil {
			request.JSON(http.StatusServiceUnavailable, gin.H{"status": "not_ready"})
			return
		}
		request.JSON(http.StatusOK, gin.H{"status": "ready"})
	})
	router.POST("/api/auth/login", auth.NewHandler(authService))
	protected := router.Group("/api")
	protected.Use(auth.RequireUser(authService))
	protected.GET("/auth/me", auth.MeHandler())
	protected.POST("/auth/logout", auth.LogoutHandler(authService))
	protected.GET("/projects", projects.Recent)
	protected.POST("/projects", projects.Create)
	protected.GET("/projects/:projectId", projects.Get)
	protected.POST("/projects/:projectId/generations", projects.Send)
	protected.POST("/projects/:projectId/messages/:messageId/generations", projects.Retry)
	protected.POST("/projects/:projectId/generations/:generationId/stop", projects.Stop)
	return router
}

func accessLogger(logger *zap.Logger) gin.HandlerFunc {
	return func(context *gin.Context) {
		startedAt := time.Now()
		context.Next()

		path := context.FullPath()
		if path == "" {
			path = context.Request.URL.Path
		}
		logger.Info("HTTP 请求完成",
			zap.String("method", context.Request.Method),
			zap.String("path", path),
			zap.Int("status", context.Writer.Status()),
			zap.Duration("latency", time.Since(startedAt)),
			zap.String("client_ip", context.ClientIP()),
		)
	}
}

func recovery(logger *zap.Logger) gin.HandlerFunc {
	return func(context *gin.Context) {
		defer func() {
			panicValue := recover()
			if panicValue == nil {
				return
			}

			logger.Error("HTTP 请求发生 panic",
				zap.Any("panic", panicValue),
				zap.ByteString("stack", debug.Stack()),
			)
			context.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"status": "error"})
		}()

		context.Next()
	}
}
