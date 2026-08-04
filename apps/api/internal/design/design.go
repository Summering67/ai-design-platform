package design

import (
	"encoding/json"
	"errors"
	"fmt"
	"strings"
)

const MaxDocumentBytes = 1 << 20

var (
	ErrInvalidDocument = errors.New("设计文档无效")
	ErrUnsupportedVersion = errors.New("设计文档版本不受支持")
	ErrDocumentTooLarge = errors.New("设计文档过大")
	ErrForbidden = errors.New("无权修改设计文档")
)

type Warning struct { Code string `json:"code"`; Message string `json:"message"` }
type PreparedDocument struct { OriginalVersion string `json:"original_version"`; Document json.RawMessage `json:"document"`; Warnings []Warning `json:"warnings"` }

func Prepare(payload []byte, allowed bool) (PreparedDocument, error) {
	if !allowed { return PreparedDocument{}, ErrForbidden }
	if len(payload) == 0 { return PreparedDocument{}, ErrInvalidDocument }
	if len(payload) > MaxDocumentBytes { return PreparedDocument{}, ErrDocumentTooLarge }
	var document map[string]json.RawMessage
	if err := json.Unmarshal(payload, &document); err != nil { return PreparedDocument{}, ErrInvalidDocument }
	var version string
	if err := json.Unmarshal(document["version"], &version); err != nil || version == "" { return PreparedDocument{}, ErrInvalidDocument }
	if major(version) != "1" || version > "1.0.0" { return PreparedDocument{}, ErrUnsupportedVersion }
	if err := validateGraph(document); err != nil { return PreparedDocument{}, err }
	warnings := []Warning{}
	if version != "1.0.0" { warnings = append(warnings, Warning{Code: "migrated_version", Message: "文档已迁移到 1.0.0"}); document["version"] = json.RawMessage(`"1.0.0"`) }
	normalized, err := json.Marshal(document)
	if err != nil { return PreparedDocument{}, fmt.Errorf("编码设计文档: %w", err) }
	return PreparedDocument{OriginalVersion: version, Document: normalized, Warnings: warnings}, nil
}

func major(version string) string { return strings.Split(version, ".")[0] }

func validateGraph(document map[string]json.RawMessage) error {
	for _, key := range []string{"id", "name", "assets", "tokens", "componentDefinitions", "componentBindings", "pages"} { if len(document[key]) == 0 { return ErrInvalidDocument } }
	var pages []struct { ID string `json:"id"`; RootID string `json:"rootId"`; Nodes map[string]struct { ID string `json:"id"`; Kind string `json:"kind"`; ParentID *string `json:"parentId"`; ChildIDs []string `json:"childIds"` } `json:"nodes"` }
	if err := json.Unmarshal(document["pages"], &pages); err != nil || len(pages) == 0 { return ErrInvalidDocument }
	for _, page := range pages {
		root, exists := page.Nodes[page.RootID]
		if !exists || root.Kind != "root" || root.ParentID != nil { return ErrInvalidDocument }
		visited := map[string]bool{}
		var visit func(string, *string) error
		visit = func(id string, parentID *string) error {
			node, exists := page.Nodes[id]; if !exists || visited[id] { return ErrInvalidDocument }; visited[id] = true
			if (node.ParentID == nil) != (parentID == nil) || node.ParentID != nil && *node.ParentID != *parentID { return ErrInvalidDocument }
			children := map[string]bool{}
			for _, childID := range node.ChildIDs { if children[childID] { return ErrInvalidDocument }; children[childID] = true; parent := node.ID; if err := visit(childID, &parent); err != nil { return err } }
			return nil
		}
		if err := visit(root.ID, nil); err != nil || len(visited) != len(page.Nodes) { return ErrInvalidDocument }
	}
	return nil
}
