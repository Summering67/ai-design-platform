package design

import "testing"

func TestCanonicalWriteAndMigrationBoundaries(t *testing.T) {
	canonical, err := PrepareCanonical(v2Fixture(t), true)
	if err != nil || canonical.OriginalVersion != "2.0.0" {
		t.Fatalf("合法 v2 文档必须进入普通写边界: %v", err)
	}

	legacy := []byte(`{"version":"1.0.0","pages":[]}`)
	if _, err := PrepareCanonical(legacy, true); err == nil {
		t.Fatal("普通写边界不得接受 v1")
	}
	migration, err := PrepareV1MigrationInput(legacy, true)
	if err != nil || string(migration.Payload) != string(legacy) {
		t.Fatalf("显式迁移入口必须保留原始 v1 payload: %v", err)
	}
}
