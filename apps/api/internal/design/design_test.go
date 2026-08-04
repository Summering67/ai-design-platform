package design

import (
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func fixture(t *testing.T) []byte {
	t.Helper()
	path := filepath.Join("..", "..", "..", "..", "packages", "design-contract", "fixtures", "v1", "login-page.document.json")
	data, err := os.ReadFile(path)
	if err != nil { t.Fatal(err) }
	return data
}

func TestPrepareAcceptsFixture(t *testing.T) {
	prepared, err := Prepare(fixture(t), true)
	if err != nil || prepared.OriginalVersion != "1.0.0" || len(prepared.Document) == 0 { t.Fatalf("准备 fixture 失败: %v", err) }
}

func TestPrepareRejectsInvalidInput(t *testing.T) {
	if _, err := Prepare([]byte(`{"version":"2.0.0"}`), true); !errors.Is(err, ErrUnsupportedVersion) { t.Fatalf("期望版本错误，实际 %v", err) }
	if _, err := Prepare(fixture(t), false); !errors.Is(err, ErrForbidden) { t.Fatalf("期望权限错误，实际 %v", err) }
	if _, err := Prepare([]byte(`{"version":"1.0.0","pages":[]}`), true); !errors.Is(err, ErrInvalidDocument) { t.Fatalf("期望文档错误，实际 %v", err) }
}
