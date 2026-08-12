package gabiactl

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"syscall"
)

const stateFileMode = 0600

// readStateForServers loads only a state file owned by this user and whose
// recorded server names exactly match the desired inventory.
func readStateForServers(environment string, names []string) (State, error) {
	b, err := readStateFile()
	if err != nil {
		return State{}, err
	}
	state, migrated, err := decodeState(b)
	if err != nil {
		return State{}, fmt.Errorf("read state: %w", err)
	}
	if err := validateState(state, environment, names); err != nil {
		return State{}, err
	}
	if migrated {
		if err := withStateLock(func() error {
			b, err := readStateFile()
			if err != nil {
				return err
			}
			state, migrated, err = decodeState(b)
			if err != nil {
				return fmt.Errorf("read state: %w", err)
			}
			if err := validateState(state, environment, names); err != nil {
				return err
			}
			if migrated {
				return writeStateFile(state)
			}
			return nil
		}); err != nil {
			return State{}, err
		}
	}
	return state, nil
}

// writeState records a validated state using an atomic same-directory rename.
func writeState(state State, names []string) error {
	if err := validateState(state, state.Environment, names); err != nil {
		return err
	}
	return withStateLock(func() error { return writeStateFile(state) })
}

func withStateLock(fn func() error) error {
	if err := os.MkdirAll(filepath.Dir(stateFile), 0750); err != nil {
		return err
	}
	if err := validateStateParent(); err != nil {
		return err
	}
	lock, err := os.OpenFile(stateFile+".lock", os.O_CREATE|os.O_RDWR, stateFileMode)
	if err != nil {
		return err
	}
	defer lock.Close()
	if err := lock.Chmod(stateFileMode); err != nil {
		return err
	}
	if err := syscall.Flock(int(lock.Fd()), syscall.LOCK_EX); err != nil {
		return err
	}
	defer syscall.Flock(int(lock.Fd()), syscall.LOCK_UN)
	return fn()
}

func readStateFile() ([]byte, error) {
	if err := validateStateParent(); err != nil {
		return nil, err
	}
	fd, err := syscall.Open(stateFile, syscall.O_RDONLY|syscall.O_NOFOLLOW, 0)
	if err != nil {
		if errors.Is(err, syscall.ELOOP) {
			return nil, errors.New("state file must be a non-symlink regular file with mode 0600")
		}
		return nil, err
	}
	file := os.NewFile(uintptr(fd), stateFile)
	defer file.Close()
	info, err := file.Stat()
	if err != nil {
		return nil, err
	}
	if !info.Mode().IsRegular() || info.Mode().Perm() != stateFileMode {
		return nil, errors.New("state file must be a non-symlink regular file with mode 0600")
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok || int(stat.Uid) != os.Geteuid() {
		return nil, errors.New("state file must be owned by the current user")
	}
	return io.ReadAll(file)
}

func validateStateParent() error {
	info, err := os.Lstat(filepath.Dir(stateFile))
	if err != nil {
		return err
	}
	if !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return errors.New("state directory must be a non-symlink directory")
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok || int(stat.Uid) != os.Geteuid() {
		return errors.New("state directory must be owned by the current user")
	}
	if info.Mode().Perm()&0022 != 0 {
		return errors.New("state directory must not be group or world writable")
	}
	return nil
}

func writeStateFile(state State) error {
	b, err := json.Marshal(state)
	if err != nil {
		return err
	}
	dir := filepath.Dir(stateFile)
	tmp, err := os.CreateTemp(dir, ".gabiactl-state-*")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)
	if err := tmp.Chmod(stateFileMode); err != nil {
		tmp.Close()
		return err
	}
	if _, err := tmp.Write(b); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Sync(); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	if err := os.Rename(tmpName, stateFile); err != nil {
		return err
	}
	d, err := os.Open(dir)
	if err != nil {
		return err
	}
	defer d.Close()
	return d.Sync()
}

func decodeState(b []byte) (State, bool, error) {
	var raw map[string]json.RawMessage
	if err := decodeJSON(b, &raw); err != nil {
		return State{}, false, err
	}
	for key := range raw {
		if key != "environment" && key != "resources" && key != "servers" {
			return State{}, false, fmt.Errorf("state has unknown field %q", key)
		}
	}
	if raw["environment"] == nil || raw["servers"] == nil && raw["resources"] == nil {
		return State{}, false, errors.New("state must contain environment and servers or resources")
	}
	var state State
	if err := decodeJSON(raw["environment"], &state.Environment); err != nil {
		return State{}, false, fmt.Errorf("state environment: %w", err)
	}
	state.Resources = make(map[string]ResourceState)
	var topLevelServers map[string]ServerState
	if servers := raw["servers"]; servers != nil {
		if err := decodeJSON(servers, &topLevelServers); err != nil {
			return State{}, false, fmt.Errorf("state servers: %w", err)
		}
	}
	var migrated bool
	var legacyServers map[string]ServerState
	if resources := raw["resources"]; resources != nil {
		var entries map[string]json.RawMessage
		if err := decodeJSON(resources, &entries); err != nil {
			return State{}, false, fmt.Errorf("state resources: %w", err)
		}
		for name, value := range entries {
			if name == "servers" {
				if err := decodeJSON(value, &legacyServers); err != nil {
					return State{}, false, errors.New("state resources.servers must be a name-keyed server map")
				}
				migrated = true
				continue
			}
			var resource ResourceState
			if err := decodeJSON(value, &resource); err != nil {
				return State{}, false, fmt.Errorf("state resource %q: %w", name, err)
			}
			if name == "routing_table" {
				name = "router"
			} else if name == "security_group" {
				name = "security-group"
			}
			state.Resources[name] = resource
		}
	}
	if legacyServers != nil {
		if len(topLevelServers) > 0 && !sameServers(topLevelServers, legacyServers) {
			return State{}, false, errors.New("state servers and resources.servers conflict")
		}
		state.Servers = legacyServers
	} else {
		state.Servers = topLevelServers
	}
	for name, server := range state.Servers {
		state.Resources["server/"+name] = ResourceState{ID: server.ID, PublicIP: server.PublicIP, PrivateIP: server.PrivateIP}
	}
	return state, migrated, nil
}

func sameServers(left, right map[string]ServerState) bool {
	if len(left) != len(right) {
		return false
	}
	for name, server := range left {
		if right[name] != server {
			return false
		}
	}
	return true
}

func decodeJSON(b []byte, target any) error {
	decoder := json.NewDecoder(bytes.NewReader(b))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(target); err != nil {
		return err
	}
	if err := decoder.Decode(&struct{}{}); !errors.Is(err, io.EOF) {
		return errors.New("state must contain one JSON value")
	}
	return nil
}

func validateState(state State, environment string, names []string) error {
	if state.Environment != environment {
		return errors.New("state environment does not match desired environment")
	}
	if !environmentName.MatchString(state.Environment) {
		return errors.New("state environment is invalid")
	}
	if state.Servers == nil {
		return errors.New("state servers are required")
	}
	want := make(map[string]struct{}, len(names))
	for _, name := range names {
		want[name] = struct{}{}
	}
	if len(state.Servers) != len(want) {
		return errors.New("state server names do not match desired servers")
	}
	for name, server := range state.Servers {
		if _, ok := want[name]; !ok || !environmentName.MatchString(name) || server.ID == "" {
			return errors.New("state server names do not match desired servers")
		}
	}
	for name, resource := range state.Resources {
		if name == "" || resource.ID == "" {
			return fmt.Errorf("state resource %q has no ID", name)
		}
	}
	return nil
}
