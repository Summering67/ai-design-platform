package auth

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

const userContextKey = "current-user"

type loginRequest struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}
type userResponse struct {
	ID          string `json:"id"`
	Email       string `json:"email"`
	DisplayName string `json:"display_name"`
}

func NewHandler(service *Service) gin.HandlerFunc {
	return func(request *gin.Context) {
		var input loginRequest
		decoder := json.NewDecoder(request.Request.Body)
		decoder.DisallowUnknownFields()
		if err := decoder.Decode(&input); err != nil || decoder.Decode(&struct{}{}) != io.EOF || strings.TrimSpace(input.Email) == "" || input.Password == "" {
			writeError(request, http.StatusBadRequest, "invalid_request", "登录信息无效")
			return
		}
		user, token, err := service.Login(request.Request.Context(), input.Email, input.Password)
		if errors.Is(err, ErrUnauthorized) {
			writeError(request, http.StatusUnauthorized, "invalid_credentials", "邮箱或密码错误")
			return
		}
		if err != nil {
			writeError(request, http.StatusInternalServerError, "internal_error", "登录失败")
			return
		}
		http.SetCookie(request.Writer, &http.Cookie{Name: SessionCookie, Value: token, Path: "/", HttpOnly: true, SameSite: http.SameSiteLaxMode, MaxAge: int(SessionDuration / time.Second)})
		request.JSON(http.StatusOK, userResponse{ID: user.ID, Email: user.Email, DisplayName: user.DisplayName})
	}
}

func RequireUser(service *Service) gin.HandlerFunc {
	return func(request *gin.Context) {
		token, err := request.Cookie(SessionCookie)
		if err != nil {
			writeError(request, http.StatusUnauthorized, "unauthorized", "请先登录")
			request.Abort()
			return
		}
		user, err := service.CurrentUser(request.Request.Context(), token)
		if err != nil {
			writeError(request, http.StatusUnauthorized, "unauthorized", "请先登录")
			request.Abort()
			return
		}
		request.Set(userContextKey, user)
		request.Next()
	}
}

func CurrentUser(request *gin.Context) (User, bool) {
	value, ok := request.Get(userContextKey)
	user, isUser := value.(User)
	return user, ok && isUser
}

func MeHandler() gin.HandlerFunc {
	return func(request *gin.Context) {
		user, ok := CurrentUser(request)
		if !ok {
			writeError(request, http.StatusUnauthorized, "unauthorized", "请先登录")
			return
		}
		request.JSON(http.StatusOK, userResponse{ID: user.ID, Email: user.Email, DisplayName: user.DisplayName})
	}
}

func LogoutHandler(service *Service) gin.HandlerFunc {
	return func(request *gin.Context) {
		if token, err := request.Cookie(SessionCookie); err == nil {
			_ = service.Logout(request.Request.Context(), token)
		}
		http.SetCookie(request.Writer, &http.Cookie{Name: SessionCookie, Value: "", Path: "/", HttpOnly: true, MaxAge: -1})
		request.Status(http.StatusNoContent)
	}
}

func writeError(request *gin.Context, status int, code, message string) {
	request.JSON(status, gin.H{"error": gin.H{"code": code, "message": message}})
}
