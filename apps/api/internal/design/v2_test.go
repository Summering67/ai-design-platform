package design

import (
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func v2Fixture(t *testing.T) []byte {
	t.Helper()
	path := filepath.Join("..", "..", "..", "..", "packages", "design-contract", "fixtures", "v2", "login-page.document.json")
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	return data
}

func TestPrepareV2AcceptsCanonicalFixture(t *testing.T) {
	prepared, err := PrepareV2(v2Fixture(t), true)
	if err != nil || prepared.OriginalVersion != "2.0.0" || len(prepared.Document) == 0 {
		t.Fatalf("准备 v2 fixture 失败: %v", err)
	}
}

func TestPrepareV2RejectsLegacyVersion(t *testing.T) {
	if _, err := PrepareV2([]byte(`{"version":"1.0.0"}`), true); !errors.Is(err, ErrUnsupportedVersion) {
		t.Fatalf("期望 v2 版本错误，实际 %v", err)
	}
}

func TestPrepareCanonicalRejectsLegacyPayload(t *testing.T) {
	if _, err := PrepareCanonical([]byte(`{"version":"1.0.0"}`), true); !errors.Is(err, ErrUnsupportedVersion) {
		t.Fatalf("普通 v2 写入口应拒绝旧版本，实际 %v", err)
	}
}

func TestPrepareV2ReportsStableSchemaError(t *testing.T) {
	path := filepath.Join("..", "..", "..", "..", "packages", "design-contract", "fixtures", "v2", "invalid", "runtime-field.document.json")
	payload, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var validation *V2ValidationError
	if _, err := PrepareV2(payload, true); !errors.As(err, &validation) || validation.Code != "schema_validation" || validation.Path == "" {
		t.Fatalf("期望稳定 Schema 错误和路径，实际 %v", err)
	}
}

func TestPrepareV1MigrationInputPreservesPayload(t *testing.T) {
	payload := []byte(`{"version":"1.0.0","pages":[]}`)
	migration, err := PrepareV1MigrationInput(payload, true)
	if err != nil || migration.OriginalVersion != "1.0.0" || string(migration.Payload) != string(payload) {
		t.Fatalf("迁移入口必须保留原始 v1 payload: %v", err)
	}
}
