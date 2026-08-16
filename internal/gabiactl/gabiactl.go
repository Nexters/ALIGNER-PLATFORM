// Package gabiactl implements the deliberately small, project-specific CLI.
package gabiactl

import (
	"bytes"
	"context"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/netip"
	"os"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

const stateFile = ".runtime/gabiactl-state.json"

// Run is the main entrypoint for executing gabiactl subcommands.
func Run(args []string, out io.Writer) error {
	if len(args) == 0 {
		return errors.New("usage: gabiactl <validate|plan|apply|status|inventory|access|destroy> -f <file>")
	}
	switch args[0] {
	case "validate":
		d, err := loadDesired(args[1:])
		if err != nil {
			return err
		}
		if err := Validate(d); err != nil {
			return err
		}
		_, err = fmt.Fprintln(out, "valid")
		return err
	case "apply":
		return apply(args[1:], out)
	case "plan":
		d, err := loadDesired(args[1:])
		if err != nil {
			return err
		}
		if err := Validate(d); err != nil {
			return err
		}
		state, err := readStateForServers(d.Environment, d.Servers.Names)
		if errors.Is(err, os.ErrNotExist) {
			state = State{}
		} else if err != nil {
			return err
		}
		return printPlan(d, state, out)
	case "status":
		d, err := loadDesired(args[1:])
		if err != nil {
			return err
		}
		if err := validateDesired(d, false); err != nil {
			return err
		}
		return status(d, out)
	case "inventory":
		return inventory(args[1:], out)
	case "destroy":
		return destroy(args[1:], out)
	case "access":
		return access(args[1:], out)
	default:
		return fmt.Errorf("unknown command %q", args[0])
	}
}

func apply(args []string, out io.Writer) error {
	fs := flag.NewFlagSet("apply", flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	file, approve := fs.String("f", "", "desired YAML"), fs.String("approve", "", "environment approval")
	fs.StringVar(file, "file", "", "desired YAML")
	if err := fs.Parse(args); err != nil {
		return err
	}
	d, err := loadDesired([]string{"-f", *file})
	if err != nil {
		return err
	}
	if err := Validate(d); err != nil {
		return err
	}
	state, err := readStateForServers(d.Environment, d.Servers.Names)
	if errors.Is(err, os.ErrNotExist) {
		state = State{}
	} else if err != nil {
		return err
	}
	if err := printPlan(d, state, out); err != nil {
		return err
	}
	if *approve != d.Environment {
		return fmt.Errorf("apply is dry-run only; write sandbox gate remains closed (use --approve %s only after the per-resource create contracts are verified)", d.Environment)
	}
	return apiGate("apply")
}

func printPlan(d Desired, state State, out io.Writer) error {
	steps, err := Plan(d, state)
	if err != nil {
		return err
	}
	for _, step := range steps {
		if _, err := fmt.Fprintf(out, "%s %s\n", step.Change, step.Resource.Identity); err != nil {
			return err
		}
	}
	return nil
}

func loadDesired(args []string) (Desired, error) {
	fs := flag.NewFlagSet("gabiactl", flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	file := fs.String("f", "", "desired infrastructure YAML")
	fs.StringVar(file, "file", "", "desired infrastructure YAML")
	if err := fs.Parse(args); err != nil {
		return Desired{}, err
	}
	if len(fs.Args()) != 0 {
		return Desired{}, fmt.Errorf("unexpected positional arguments: %s", strings.Join(fs.Args(), " "))
	}
	if *file == "" {
		return Desired{}, errors.New("-f is required")
	}
	b, err := os.ReadFile(*file)
	if err != nil {
		return Desired{}, fmt.Errorf("read desired infrastructure: %w", err)
	}
	decoder := yaml.NewDecoder(bytes.NewReader(b))
	decoder.KnownFields(true)
	var desired Desired
	if err := decoder.Decode(&desired); err != nil {
		return Desired{}, fmt.Errorf("decode desired infrastructure: %w", err)
	}
	if err := decoder.Decode(&struct{}{}); !errors.Is(err, io.EOF) {
		return Desired{}, errors.New("desired infrastructure must contain one YAML document")
	}
	return desired, nil
}

func apiGate(command string) error {
	return fmt.Errorf("%s blocked: Gabia write API sandbox gate is not complete; no API request or state mutation was made", command)
}

var newStatusClient = func(credentials Credentials) (*Client, error) {
	return NewClient(credentials, "", "", nil)
}

func status(d Desired, out io.Writer) error {
	state, err := readStateForServers(d.Environment, d.Servers.Names)
	if errors.Is(err, os.ErrNotExist) {
		_, err = fmt.Fprintln(out, "state: absent; remote status unavailable until sandbox read schema is verified")
		return err
	}
	if err != nil {
		return err
	}
	credentials, err := ReadCredentials(os.Stderr)
	if err != nil {
		return err
	}
	client, err := newStatusClient(credentials)
	if err != nil {
		return err
	}
	verified, unavailable := 0, 0
	for _, resource := range desiredResources(d) {
		recorded, ok := state.Resources[resource.Identity]
		if !ok || recorded.ID == "" {
			continue
		}
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		found, observeErr := client.ObserveRecorded(ctx, resource, recorded)
		cancel()
		if observeErr != nil {
			if strings.Contains(observeErr.Error(), "not contract-verified") {
				unavailable++
				continue
			}
			return fmt.Errorf("status %s: %w", resource.Identity, observeErr)
		}
		if !found {
			return fmt.Errorf("status drift: %s (%s) is absent remotely", resource.Identity, recorded.ID)
		}
		verified++
	}
	_, err = fmt.Fprintf(out, "remote status: %d recorded %s present; %d recorded %s remain read-contract-gated\n", verified, resourceNoun(verified), unavailable, resourceNoun(unavailable))
	return err
}

func resourceNoun(count int) string {
	if count == 1 {
		return "resource"
	}
	return "resources"
}

func inventory(args []string, out io.Writer) error {
	fs := flag.NewFlagSet("inventory", flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	file, output, via := fs.String("f", "", "desired YAML"), fs.String("o", "", "inventory output"), fs.String("connect-via", "", "public or private")
	fs.StringVar(file, "file", "", "desired YAML")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if *output == "" || (*via != "public" && *via != "private") {
		return errors.New("inventory requires -o and --connect-via public|private")
	}
	d, err := loadDesired([]string{"-f", *file})
	if err != nil {
		return err
	}
	if err := validateDesired(d, false); err != nil {
		return err
	}
	if d.Servers.Count != 3 || strings.Join(d.Servers.Names, ",") != "k3s-01,k3s-02,k3s-03" {
		return errors.New("inventory requires exactly k3s-01, k3s-02, and k3s-03")
	}
	state, err := readStateForServers(d.Environment, d.Servers.Names)
	if err != nil {
		return fmt.Errorf("inventory requires sandbox-verified state: %w", err)
	}
	hosts := make(map[string]map[string]string, len(state.Servers))
	for name, server := range state.Servers {
		address := server.PrivateIP
		if *via == "public" {
			address = server.PublicIP
		}
		if _, err := netip.ParseAddr(address); err != nil {
			return fmt.Errorf("inventory %s address for %s is unavailable", *via, name)
		}
		hosts[name] = map[string]string{"ansible_host": address, "private_ip": server.PrivateIP, "public_ip": server.PublicIP}
	}
	groupHosts := func(names []string) map[string]any {
		group := make(map[string]any, len(names))
		for _, name := range names {
			group[name] = map[string]any{}
		}
		return group
	}
	children := map[string]any{
		"k3s_servers":         map[string]any{"hosts": groupHosts(d.Servers.Names)},
		"k3s_first_server":    map[string]any{"hosts": groupHosts(d.Servers.Names[:1])},
		"management_gateways": map[string]any{"hosts": groupHosts(d.Servers.Names[:2])},
	}
	var inventoryBuf bytes.Buffer
	encoder := yaml.NewEncoder(&inventoryBuf)
	if err := encoder.Encode(map[string]any{"all": map[string]any{
		"hosts": hosts, "vars": map[string]string{"vpc_cidr": d.Network.VPCCIDR}, "children": children,
	}}); err != nil {
		return err
	}
	if err := encoder.Close(); err != nil {
		return err
	}
	if err := writePrivateFile(*output, inventoryBuf.Bytes()); err != nil {
		return err
	}
	_, err = fmt.Fprintln(out, *output)
	return err
}

func destroy(args []string, out io.Writer) error {
	fs := flag.NewFlagSet("destroy", flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	file, confirm := fs.String("f", "", "desired YAML"), fs.String("confirm", "", "environment confirmation")
	fs.StringVar(file, "file", "", "desired YAML")
	if err := fs.Parse(args); err != nil {
		return err
	}
	d, err := loadDesired([]string{"-f", *file})
	if err != nil {
		return err
	}
	if err := Validate(d); err != nil {
		return err
	}
	if *confirm != d.Environment {
		return fmt.Errorf("destroy requires --confirm %s", d.Environment)
	}
	resources := desiredResources(d)
	for i := len(resources) - 1; i >= 0; i-- {
		if _, err := fmt.Fprintf(out, "destroy %s\n", resources[i].Identity); err != nil {
			return err
		}
	}
	return apiGate("destroy")
}

func access(args []string, out io.Writer) error {
	if len(args) == 0 || (args[0] != "open" && args[0] != "close") {
		return errors.New("access requires open or close")
	}
	fs := flag.NewFlagSet("access", flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	file, cidr, targets := fs.String("f", "", "desired YAML"), fs.String("cidr", "", "temporary SSH /32"), fs.String("targets", "", "comma-separated server names")
	fs.StringVar(file, "file", "", "desired YAML")
	if err := fs.Parse(args[1:]); err != nil {
		return err
	}
	d, err := loadDesired([]string{"-f", *file})
	if err != nil {
		return err
	}
	if err := Validate(d); err != nil {
		return err
	}
	selected := strings.Split(*targets, ",")
	if *targets == "" {
		return errors.New("access requires --targets")
	}
	known := map[string]bool{}
	for _, n := range d.Servers.Names {
		known[n] = true
	}
	for _, n := range selected {
		if !known[n] {
			return fmt.Errorf("access target %q is not a declared server", n)
		}
	}
	if args[0] == "open" {
		p, err := netip.ParsePrefix(*cidr)
		if err != nil || !p.Addr().Is4() || p.Bits() != 32 {
			return errors.New("access open requires an IPv4 --cidr /32")
		}
	}
	return apiGate("access " + args[0])
}
