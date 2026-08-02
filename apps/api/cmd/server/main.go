package main

import (
	"fmt" // 用于格式化输入输出（如打印错误信息）
	"os"  // 用于与操作系统交互（如获取环境变量、退出程序等）

	"github.com/Summering67/ai-design-platform/apps/api/internal/server"
)

func main() {
	if err := server.Run(); err != nil {
		// 将错误信息打印到标准错误输出，并以状态码 1 退出程序
		_, _ = fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
