package server

import (
	"context"
	"net/http"
	"runtime/debug"
	"time"

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
