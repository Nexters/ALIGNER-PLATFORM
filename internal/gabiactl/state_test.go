package gabiactl

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestReadStateMigratesNestedServersAtomically(t *testing.T) {
	chdir(t)
	if err := os.Mkdir(".runtime", 0750); err != nil {
		t.Fatal(err)
	}
	legacy := `{"environment":"sandbox","servers":{},"resources":{"routing_table":{"id":"router-1"},"security_group":{"id":"security-group-1"},"servers":{"k3s-01":{"id":"server-1","public_ip":"203.0.113.10","private_ip":"10.20.0.10"}}}}`
	if err := os.WriteFile(stateFile, []byte(legacy), stateFileMode); err != nil {
		t.Fatal(err)
	}
	state, err := readStateForServers("sandbox", []string{"k3s-01"})
	if err != nil {
		t.Fatal(err)
	}
	if state.Resources["router"].ID != "router-1" || state.Resources["security-group"].ID != "security-group-1" || state.Resources["server/k3s-01"].PrivateIP != "10.20.0.10" {
		t.Fatalf("legacy resources were not normalized")
	}
	b, err := os.ReadFile(stateFile)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(b), `"resources":{"servers"`) || !strings.Contains(string(b), `"servers"`) {
		t.Fatalf("legacy state was not rewritten to canonical schema")
	}
	info, err := os.Lstat(stateFile)
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm() != stateFileMode || !info.Mode().IsRegular() {
		t.Fatalf("state mode = %o, regular = %t", info.Mode().Perm(), info.Mode().IsRegular())
	}
}

func TestDecodeStateRejectsConflictingTopLevelAndLegacyServers(t *testing.T) {
	_, _, err := decodeState([]byte(`{"environment":"sandbox","servers":{"k3s-01":{"id":"server-1"}},"resources":{"servers":{"k3s-01":{"id":"server-2"}}}}`))
	if err == nil || !strings.Contains(err.Error(), "conflict") {
		t.Fatalf("conflicting servers error = %v", err)
	}
}

func TestDecodeStateAcceptsMatchingTopLevelAndLegacyServers(t *testing.T) {
	state, migrated, err := decodeState([]byte(`{"environment":"sandbox","servers":{"k3s-01":{"id":"server-1"}},"resources":{"servers":{"k3s-01":{"id":"server-1"}}}}`))
	if err != nil || !migrated || state.Servers["k3s-01"].ID != "server-1" {
		t.Fatalf("matching servers state = %#v, migrated = %t, err = %v", state, migrated, err)
	}
}

func TestReadStateRejectsUnsafeFileAndSchema(t *testing.T) {
	chdir(t)
	if err := os.Mkdir(".runtime", 0750); err != nil {
		t.Fatal(err)
	}
	valid := `{"environment":"sandbox","servers":{"k3s-01":{"id":"server-1"}}}`
	if err := os.WriteFile(stateFile, []byte(valid), 0644); err != nil {
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
	if err := writeState(state, []string{"k3s-01"}); err != nil {
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
