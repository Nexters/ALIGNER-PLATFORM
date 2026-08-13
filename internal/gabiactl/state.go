package gabiactl

import (
	"bytes"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"syscall"

	"golang.org/x/sys/unix"
)

const stateFileMode = 0600

// readStateForServers loads only a state file owned by this user and whose
// recorded server names exactly match the desired inventory.
func readStateForServers(environment string, names []string) (State, error) {
	b, err := readStateFile()
	if err != nil {
		return State{}, err
	}
	state, err := decodeState(b)
	if err != nil {
		return State{}, fmt.Errorf("read state: %w", err)
	}
	if err := validateState(state, environment, names); err != nil {
		return State{}, err
	}
	return state, nil
}

// writeState records a validated state using an atomic same-directory rename.
func writeState(state State, environment string, names []string) error {
	if err := validateState(state, environment, names); err != nil {
		return err
	}
	return withStateLock(func(dirFD int) error { return writeStateFileAt(dirFD, state) })
}

func withStateLock(fn func(int) error) error {
	if err := os.MkdirAll(filepath.Dir(stateFile), 0750); err != nil {
		return err
	}
	dirFD, err := openPrivateDirectory(filepath.Dir(stateFile))
	if err != nil {
		return err
	}
	defer unix.Close(dirFD)
	lockFD, err := unix.Openat(dirFD, filepath.Base(stateFile)+".lock", unix.O_CREAT|unix.O_RDWR|unix.O_NOFOLLOW, stateFileMode)
	if err != nil {
		return err
	}
	lock := os.NewFile(uintptr(lockFD), stateFile+".lock")
	defer func() { _ = lock.Close() }()
	if err := lock.Chmod(stateFileMode); err != nil {
		return err
	}
	if err := syscall.Flock(int(lock.Fd()), syscall.LOCK_EX); err != nil {
		return err
	}
	defer func() { _ = syscall.Flock(int(lock.Fd()), syscall.LOCK_UN) }()
	return fn(dirFD)
}

func readStateFile() ([]byte, error) {
	dirFD, err := openPrivateDirectory(filepath.Dir(stateFile))
	if err != nil {
		return nil, err
	}
	defer unix.Close(dirFD)
	return readStateFileAt(dirFD)
}

func readStateFileAt(dirFD int) ([]byte, error) {
	fd, err := unix.Openat(dirFD, filepath.Base(stateFile), unix.O_RDONLY|unix.O_NOFOLLOW, 0)
	if err != nil {
		if errors.Is(err, syscall.ELOOP) {
			return nil, errors.New("state file must be a non-symlink regular file with mode 0600")
		}
		return nil, err
	}
	file := os.NewFile(uintptr(fd), stateFile)
	defer func() { _ = file.Close() }()
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

func openPrivateDirectory(path string) (int, error) {
	fd, err := unix.Open(path, unix.O_RDONLY|unix.O_DIRECTORY|unix.O_NOFOLLOW, 0)
	if err != nil {
		return -1, err
	}
	var stat unix.Stat_t
	if err := unix.Fstat(fd, &stat); err != nil {
		unix.Close(fd)
		return -1, err
	}
	if stat.Mode&unix.S_IFMT != unix.S_IFDIR || int(stat.Uid) != os.Geteuid() || stat.Mode&0022 != 0 {
		unix.Close(fd)
		return -1, errors.New("state directory must be an owner-controlled non-symlink directory")
	}
	return fd, nil
}

func writeStateFileAt(dirFD int, state State) error {
	b, err := json.Marshal(state)
	if err != nil {
		return err
	}
	var nonce [16]byte
	if _, err := rand.Read(nonce[:]); err != nil {
		return err
	}
	tmpBase := ".gabiactl-state-" + hex.EncodeToString(nonce[:])
	tmpFD, err := unix.Openat(dirFD, tmpBase, unix.O_WRONLY|unix.O_CREAT|unix.O_EXCL|unix.O_NOFOLLOW, stateFileMode)
	if err != nil {
		return err
	}
	tmp := os.NewFile(uintptr(tmpFD), tmpBase)
	defer func() { _ = unix.Unlinkat(dirFD, tmpBase, 0) }()
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
	if err := unix.Renameat(dirFD, tmpBase, dirFD, filepath.Base(stateFile)); err != nil {
		return err
	}
	return unix.Fsync(dirFD)
}

func writePrivateFile(path string, data []byte) error {
	dir, base := filepath.Dir(path), filepath.Base(path)
	if base == "." || base == string(filepath.Separator) {
		return errors.New("output must name a file")
	}
	if err := os.MkdirAll(dir, 0750); err != nil {
		return err
	}
	dirFD, err := openPrivateDirectory(dir)
	if err != nil {
		return err
	}
	defer unix.Close(dirFD)
	var existing unix.Stat_t
	if err := unix.Fstatat(dirFD, base, &existing, unix.AT_SYMLINK_NOFOLLOW); err == nil {
		if existing.Mode&unix.S_IFMT != unix.S_IFREG || int(existing.Uid) != os.Geteuid() || existing.Mode&0777 != stateFileMode {
			return errors.New("output must be an owner-controlled regular file with mode 0600")
		}
	} else if !errors.Is(err, unix.ENOENT) {
		return err
	}
	var nonce [16]byte
	if _, err := rand.Read(nonce[:]); err != nil {
		return err
	}
	tmpBase := ".gabiactl-output-" + hex.EncodeToString(nonce[:])
	tmpFD, err := unix.Openat(dirFD, tmpBase, unix.O_WRONLY|unix.O_CREAT|unix.O_EXCL|unix.O_NOFOLLOW, stateFileMode)
	if err != nil {
		return err
	}
	tmp := os.NewFile(uintptr(tmpFD), tmpBase)
	defer func() { _ = unix.Unlinkat(dirFD, tmpBase, 0) }()
	if _, err := tmp.Write(data); err != nil {
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
	if err := unix.Renameat(dirFD, tmpBase, dirFD, base); err != nil {
		return err
	}
	return unix.Fsync(dirFD)
}

func decodeState(b []byte) (State, error) {
	var raw map[string]json.RawMessage
	if err := decodeJSON(b, &raw); err != nil {
		return State{}, err
	}
	for key := range raw {
		if key != "environment" && key != "resources" && key != "servers" {
			return State{}, fmt.Errorf("state has unknown field %q", key)
		}
	}
	if raw["environment"] == nil || raw["servers"] == nil {
		return State{}, errors.New("state must contain environment and top-level servers")
	}
	var state State
	if err := decodeJSON(raw["environment"], &state.Environment); err != nil {
		return State{}, fmt.Errorf("state environment: %w", err)
	}
	state.Resources = make(map[string]ResourceState)
	if err := decodeJSON(raw["servers"], &state.Servers); err != nil {
		return State{}, fmt.Errorf("state servers: %w", err)
	}
	if resources := raw["resources"]; resources != nil {
		var entries map[string]json.RawMessage
		if err := decodeJSON(resources, &entries); err != nil {
			return State{}, fmt.Errorf("state resources: %w", err)
		}
		for name, value := range entries {
			if name == "servers" || name == "routing_table" || name == "security_group" {
				return State{}, fmt.Errorf("state resource %q is not supported by the current schema", name)
			}
			var resource ResourceState
			if err := decodeJSON(value, &resource); err != nil {
				return State{}, fmt.Errorf("state resource %q: %w", name, err)
			}
			state.Resources[name] = resource
		}
	}
	for name, server := range state.Servers {
		identity := "server/" + name
		if resource, ok := state.Resources[identity]; ok && resource != ResourceState(server) {
			return State{}, fmt.Errorf("state %s does not match top-level servers", identity)
		}
		if _, ok := state.Resources[identity]; !ok {
			state.Resources[identity] = ResourceState(server)
		}
	}
	return state, nil
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
