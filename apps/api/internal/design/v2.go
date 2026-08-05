package design

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/santhosh-tekuri/jsonschema/v6"
)

const v2SchemaID = "https://ai-design-platform.dev/schema/v2/design-document.schema.json"

var (
	ErrSchemaUnavailable = errors.New("设计文档 Schema 不可用")
	ErrInvalidV2Document = errors.New("v2 设计文档无效")
)

type V2ValidationError struct {
	Code string
	Path string
	Err  error
}

type MigrationInput struct {
	OriginalVersion string
	Payload         []byte
}

func (e *V2ValidationError) Error() string {
	return e.Code + " at " + e.Path
}

func (e *V2ValidationError) Unwrap() error { return e.Err }

func v2SchemaPath() (string, error) {
	_, currentFile, _, ok := runtime.Caller(0)
	if !ok {
		return "", ErrSchemaUnavailable
	}
	return filepath.Join(filepath.Dir(currentFile), "..", "..", "..", "..", "packages", "design-contract", "schema", "v2", "design-document.schema.json"), nil
}

func loadV2Schema() (*jsonschema.Schema, error) {
	path, err := v2SchemaPath()
	if err != nil {
		return nil, err
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("读取设计文档 Schema: %w", err)
	}
	var document any
	if err := json.Unmarshal(raw, &document); err != nil {
		return nil, fmt.Errorf("解析设计文档 Schema: %w", err)
	}
	compiler := jsonschema.NewCompiler()
	if err := compiler.AddResource(v2SchemaID, document); err != nil {
		return nil, fmt.Errorf("注册设计文档 Schema: %w", err)
	}
	compiled, err := compiler.Compile(v2SchemaID)
	if err != nil {
		return nil, fmt.Errorf("编译设计文档 Schema: %w", err)
	}
	return compiled, nil
}

func validateV2Semantics(document map[string]any) error {
	root, ok := document["root"].(map[string]any)
	if !ok {
		return &V2ValidationError{Code: "invalid_root", Path: "/root", Err: ErrInvalidV2Document}
	}
	assets, _ := document["assets"].(map[string]any)
	designSystem, _ := document["designSystem"].(map[string]any)
	components, _ := designSystem["components"].(map[string]any)
	allowedTags := map[string]bool{}
	if tags, ok := designSystem["allowedTags"].([]any); ok {
		for _, tag := range tags {
			if value, ok := tag.(string); ok {
				allowedTags[value] = true
			}
		}
	}
	ids := map[string]bool{}
	var visit func(map[string]any, string) error
	visit = func(node map[string]any, path string) error {
		id, ok := node["id"].(string)
		if !ok || id == "" || ids[id] {
			return &V2ValidationError{Code: "duplicate_id", Path: path + "/id", Err: ErrInvalidV2Document}
		}
		ids[id] = true
		if node["kind"] == "image" {
			assetID, ok := node["assetId"].(string)
			if !ok {
				return &V2ValidationError{Code: "unknown_asset", Path: path + "/assetId", Err: ErrInvalidV2Document}
			}
			if _, exists := assets[assetID]; !exists {
				return &V2ValidationError{Code: "unknown_asset", Path: path + "/assetId", Err: ErrInvalidV2Document}
			}
		}
		if node["kind"] == "component" {
			tag, _ := node["tag"].(string)
			registered := false
			for key, raw := range components {
				component, _ := raw.(map[string]any)
				id, _ := component["id"].(string)
				if key == tag || id == tag {
					registered = true
					break
				}
			}
			if !registered {
				return &V2ValidationError{Code: "unknown_component", Path: path + "/tag", Err: ErrInvalidV2Document}
			}
			if len(allowedTags) > 0 && !allowedTags[tag] {
				return &V2ValidationError{Code: "tag_not_allowed", Path: path + "/tag", Err: ErrInvalidV2Document}
			}
		}
		if props, ok := node["props"].(map[string]any); ok && containsDesignNode(props) {
			return &V2ValidationError{Code: "nested_design_node", Path: path + "/props", Err: ErrInvalidV2Document}
		}
		children, _ := node["children"].([]any)
		for index, child := range children {
			childNode, ok := child.(map[string]any)
			if !ok {
				return &V2ValidationError{Code: "invalid_child", Path: fmt.Sprintf("%s/children/%d", path, index), Err: ErrInvalidV2Document}
			}
			if err := visit(childNode, fmt.Sprintf("%s/children/%d", path, index)); err != nil {
				return err
			}
		}
		return nil
	}
	return visit(root, "/root")
}

func containsDesignNode(value any) bool {
	switch typed := value.(type) {
	case []any:
		for _, item := range typed {
			if containsDesignNode(item) {
				return true
			}
		}
	case map[string]any:
		_, hasID := typed["id"].(string)
		_, hasKind := typed["kind"].(string)
		_, hasChildren := typed["children"].([]any)
		if hasID && hasKind && hasChildren {
			return true
		}
		for _, item := range typed {
			if containsDesignNode(item) {
				return true
			}
		}
	}
	return false
}

func schemaValidationError(err error) error {
	validation, ok := err.(*jsonschema.ValidationError)
	if !ok {
		return errors.Join(ErrInvalidV2Document, err)
	}
	path := "/" + strings.Join(validation.InstanceLocation, "/")
	if path == "/" && len(validation.Causes) > 0 {
		path = "/" + strings.Join(validation.Causes[0].InstanceLocation, "/")
	}
	return &V2ValidationError{Code: "schema_validation", Path: path, Err: ErrInvalidV2Document}
}

// PrepareV2 validates and normalizes a canonical DesignDocument 2.0 payload.
// The schema is loaded from the repository's canonical JSON file; a missing
// schema fails closed instead of accepting an unchecked payload.
func PrepareV2(payload []byte, allowed bool) (PreparedDocument, error) {
	if !allowed {
		return PreparedDocument{}, ErrForbidden
	}
	if len(payload) == 0 {
		return PreparedDocument{}, ErrInvalidV2Document
	}
	if len(payload) > MaxDocumentBytes {
		return PreparedDocument{}, ErrDocumentTooLarge
	}
	var document map[string]any
	if err := json.Unmarshal(payload, &document); err != nil {
		return PreparedDocument{}, ErrInvalidV2Document
	}
	version, _ := document["version"].(string)
	if version != "2.0.0" {
		return PreparedDocument{}, ErrUnsupportedVersion
	}
	schema, err := loadV2Schema()
	if err != nil {
		return PreparedDocument{}, errors.Join(ErrSchemaUnavailable, err)
	}
	if err := schema.Validate(document); err != nil {
		return PreparedDocument{}, schemaValidationError(err)
	}
	if err := validateV2Semantics(document); err != nil {
		return PreparedDocument{}, err
	}
	normalized, err := json.Marshal(document)
	if err != nil {
		return PreparedDocument{}, fmt.Errorf("编码 v2 设计文档: %w", err)
	}
	return PreparedDocument{OriginalVersion: version, Document: normalized, Warnings: []Warning{}}, nil
}

// PrepareCanonical is the ordinary v2 write boundary. Legacy v1 payloads
// must go through an explicit migration flow and are never accepted here.
func PrepareCanonical(payload []byte, allowed bool) (PreparedDocument, error) {
	if !allowed {
		return PreparedDocument{}, ErrForbidden
	}
	var envelope struct {
		Version string `json:"version"`
	}
	if err := json.Unmarshal(payload, &envelope); err != nil || envelope.Version != "2.0.0" {
		return PreparedDocument{}, ErrUnsupportedVersion
	}
	return PrepareV2(payload, true)
}

// PrepareV1MigrationInput is the only Go entry point for legacy payloads. It
// preserves the original bytes for the migration worker and never persists
// them as the current design document.
func PrepareV1MigrationInput(payload []byte, allowed bool) (MigrationInput, error) {
	if !allowed {
		return MigrationInput{}, ErrForbidden
	}
	if len(payload) == 0 || len(payload) > MaxDocumentBytes {
		return MigrationInput{}, ErrInvalidDocument
	}
	var envelope struct {
		Version string `json:"version"`
	}
	if err := json.Unmarshal(payload, &envelope); err != nil || envelope.Version != "1.0.0" {
		return MigrationInput{}, ErrUnsupportedVersion
	}
	return MigrationInput{OriginalVersion: envelope.Version, Payload: append([]byte(nil), payload...)}, nil
}
