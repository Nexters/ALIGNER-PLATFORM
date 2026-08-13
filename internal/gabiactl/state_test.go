package gabiactl

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestDecodeStateRejectsUnsupportedStateShapes(t *testing.T) {
	for name, state := range map[string]string{
		"nested servers":       `{"environment":"sandbox","servers":{},"resources":{"servers":{"k3s-01":{"id":"server-1"}}}}`,
		"routing table alias":  `{"environment":"sandbox","servers":{},"resources":{"routing_table":{"id":"router-1"}}}`,
		"security group alias": `{"environment":"sandbox","servers":{},"resources":{"security_group":{"id":"security-group-1"}}}`,
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := decodeState([]byte(state)); err == nil || !strings.Contains(err.Error(), "not supported") {
				t.Fatalf("unsupported state error = %v", err)
			}
		})
	}
}

func TestReadStateRejectsUnsupportedStateWithoutRewritingIt(t *testing.T) {
	chdir(t)
	if err := os.Mkdir(".runtime", 0750); err != nil {
		t.Fatal(err)
	}
	unsupported := []byte(`{"environment":"sandbox","servers":{},"resources":{"routing_table":{"id":"router-1"}}}`)
	if err := os.WriteFile(stateFile, unsupported, stateFileMode); err != nil {
		t.Fatal(err)
	}
	if _, err := readStateForServers("sandbox", []string{"k3s-01"}); err == nil || !strings.Contains(err.Error(), "not supported") {
		t.Fatalf("unsupported state error = %v", err)
	}
	after, err := os.ReadFile(stateFile)
	if err != nil || !bytes.Equal(after, unsupported) {
		t.Fatalf("unsupported state changed: %q, %v", after, err)
	}
}

func TestReadStateRejectsUnsafeFileAndSchema(t *testing.T) {
	chdir(t)
	if err := os.Mkdir(".runtime", 0750); err != nil {
		t.Fatal(err)
	}
	valid := `{"environment":"sandbox","servers":{"k3s-01":{"id":"server-1"}}}`
	if err := os.WriteFile(stateFile, []byte(valid), 0644); err != nil { // #nosec G306 -- intentionally unsafe fixture
		t.Fatal(err)
	}
	if _, err := readStateForServers("sandbox", []string{"k3s-01"}); err == nil || !strings.Contains(err.Error(), "mode 0600") {
		t.Fatalf("insecure mode error = %v", err)
	}
	if err := os.WriteFile(stateFile, []byte(`{"environment":"sandbox","servers":{"other":{"id":"server-1"}}}`), stateFileMode); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(stateFile, stateFileMode); err != nil {
		t.Fatal(err)
	}
	if _, err := readStateForServers("sandbox", []string{"k3s-01"}); err == nil || !strings.Contains(err.Error(), "server names") {
		t.Fatalf("server mismatch error = %v", err)
	}
	if err := os.WriteFile(stateFile, []byte(`{"environment":"sandbox","servers":{"k3s-01":{"id":"server-1","extra":true}}}`), stateFileMode); err != nil {
		t.Fatal(err)
	}
	if _, err := readStateForServers("sandbox", []string{"k3s-01"}); err == nil || !strings.Contains(err.Error(), "unknown field") {
		t.Fatalf("unknown field error = %v", err)
	}
	if err := os.Remove(stateFile); err != nil {
		t.Fatal(err)
	}
	target := filepath.Join(t.TempDir(), "state.json")
	if err := os.WriteFile(target, []byte(valid), stateFileMode); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(target, stateFile); err != nil {
		t.Fatal(err)
	}
	if _, err := readStateForServers("sandbox", []string{"k3s-01"}); err == nil || !strings.Contains(err.Error(), "non-symlink") {
		t.Fatalf("symlink error = %v", err)
	}
}

func TestWriteStateUsesPrivateAtomicFile(t *testing.T) {
	chdir(t)
	state := State{Environment: "sandbox", Servers: map[string]ServerState{"k3s-01": {ID: "server-1"}}}
	if err := writeState(state, "sandbox", []string{"k3s-01"}); err != nil {
		t.Fatal(err)
	}
	info, err := os.Lstat(filepath.Join(".runtime", "gabiactl-state.json"))
	if err != nil {
		t.Fatal(err)
	}
	if !info.Mode().IsRegular() || info.Mode().Perm() != stateFileMode {
		t.Fatalf("state mode = %o, regular = %t", info.Mode().Perm(), info.Mode().IsRegular())
	}
}

func TestReadStateRejectsWritableParent(t *testing.T) {
	chdir(t)
	if err := os.Mkdir(".runtime", 0777); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(".runtime", 0777); err != nil {
		t.Fatal(err)
	}
	if _, err := readStateForServers("sandbox", []string{"k3s-01"}); err == nil || !strings.Contains(err.Error(), "owner-controlled") {
		t.Fatalf("writable parent error = %v", err)
	}
}

func TestWriteStateRejectsWrongEnvironment(t *testing.T) {
	chdir(t)
	state := State{Environment: "production", Servers: map[string]ServerState{"k3s-01": {ID: "server-1"}}}
	if err := writeState(state, "sandbox", []string{"k3s-01"}); err == nil || !strings.Contains(err.Error(), "environment") {
		t.Fatalf("environment mismatch error = %v", err)
	}
}
