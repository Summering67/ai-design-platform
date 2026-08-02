package main

import (
	"fmt"
	"os"

	"github.com/Summering67/ai-design-platform/apps/api/internal/server"
)

func main() {
	if err := server.Run(); err != nil {
		_, _ = fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
