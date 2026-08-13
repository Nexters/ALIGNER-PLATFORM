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
	"regexp"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

const stateFile = ".runtime/gabiactl-state.json"

var environmentName = regexp.MustCompile(`^[a-z][a-z0-9-]{0,62}$`)

// Desired is the documented desired-infrastructure YAML shape. It intentionally
// omits cloud credentials and unverified API-specific request fields.
type Desired struct {
	Version      string       `yaml:"version"`
	Environment  string       `yaml:"environment"`
	Network      Network      `yaml:"network"`
	Servers      Servers      `yaml:"servers"`
	Volumes      Volumes      `yaml:"volumes"`
	LoadBalancer LoadBalancer `yaml:"load_balancer"`
}

type Network struct {
	VPCCIDR    string `yaml:"vpc_cidr"`
	SubnetCIDR string `yaml:"subnet_cidr"`
}

type Servers struct {
	OSImage *string  `yaml:"os_image"`
	Flavor  string   `yaml:"flavor"`
	Count   int      `yaml:"count"`
	Names   []string `yaml:"names"`
}

type Volumes struct {
	DataAGB int `yaml:"data_a_gb"`
	DataBGB int `yaml:"data_b_gb"`
}

type LoadBalancer struct {
	Listeners []Listener `yaml:"listeners"`
}

type Listener struct {
	Port       int    `yaml:"port"`
	Protocol   string `yaml:"protocol"`
	TargetPort int    `yaml:"target_port"`
}

// State has no credentials. Its server addresses are only populated after the
// sandbox captures establish the list/read response schema.
type State struct {
	Environment string                   `json:"environment"`
	Resources   map[string]ResourceState `json:"resources,omitempty"`
	Servers     map[string]ServerState   `json:"servers"`
}

// ResourceState contains only the stable cloud ID and addresses required for
// inventory. It deliberately excludes unverified provider response fields.
type ResourceState struct {
	ID        string `json:"id"`
	PublicIP  string `json:"public_ip,omitempty"`
	PrivateIP string `json:"private_ip,omitempty"`
}

type ServerState struct {
	ID        string `json:"id"`
	PublicIP  string `json:"public_ip,omitempty"`
	PrivateIP string `json:"private_ip,omitempty"`
}

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
	return desired, nil
}

func Validate(d Desired) error {
	return validateDesired(d, true)
}

func validateDesired(d Desired, requireImage bool) error {
	var problems []string
	if d.Version != "v1" {
		problems = append(problems, "version must be v1")
	}
	if !environmentName.MatchString(d.Environment) {
		problems = append(problems, "environment is required and must be a lowercase name")
	}
	vpc, vpcErr := netip.ParsePrefix(d.Network.VPCCIDR)
	if vpcErr != nil || !vpc.Addr().Is4() || vpc != vpc.Masked() || vpc.Bits() < 8 || vpc.Bits() > 24 || !isRFC1918(vpc) {
		problems = append(problems, "network.vpc_cidr must be an RFC1918 IPv4 network with prefix /8 through /24")
	}
	subnet, subnetErr := netip.ParsePrefix(d.Network.SubnetCIDR)
	if subnetErr != nil || !subnet.Addr().Is4() || subnet != subnet.Masked() || subnet.Bits() != 24 {
		problems = append(problems, "network.subnet_cidr must be an IPv4 /24 network")
	} else if vpcErr == nil && !vpc.Contains(subnet.Addr()) {
		problems = append(problems, "network.subnet_cidr must be contained by network.vpc_cidr")
	}
	if requireImage && (d.Servers.OSImage == nil || strings.TrimSpace(*d.Servers.OSImage) == "") {
		problems = append(problems, "servers.os_image must be a confirmed image ID (null closes the apply gate)")
	}
	if d.Servers.Flavor == "" {
		problems = append(problems, "servers.flavor is required")
	}
	if d.Servers.Count < 1 || len(d.Servers.Names) != d.Servers.Count {
		problems = append(problems, "servers.count must match a non-empty servers.names list")
	}
	seen := map[string]bool{}
	for _, name := range d.Servers.Names {
		if !environmentName.MatchString(name) || seen[name] {
			problems = append(problems, "servers.names must contain unique lowercase names")
			break
		}
		seen[name] = true
	}
	if d.Volumes.DataAGB < 1 || d.Volumes.DataBGB < 1 {
		problems = append(problems, "volume sizes must be positive")
	}
	if len(d.LoadBalancer.Listeners) == 0 {
		problems = append(problems, "load_balancer.listeners is required")
	}
	for _, l := range d.LoadBalancer.Listeners {
		if !((l.Port == 80 && l.Protocol == "HTTP") || (l.Port == 443 && l.Protocol == "HTTPS")) || l.TargetPort < 1 || l.TargetPort > 65535 {
			problems = append(problems, "load balancer listeners allow only HTTP/80 or HTTPS/443 with a valid target_port")
			break
		}
	}
	if len(problems) > 0 {
		return errors.New(strings.Join(problems, "; "))
	}
	return nil
}

func isRFC1918(p netip.Prefix) bool {
	for _, private := range []netip.Prefix{netip.MustParsePrefix("10.0.0.0/8"), netip.MustParsePrefix("172.16.0.0/12"), netip.MustParsePrefix("192.168.0.0/16")} {
		if private.Contains(p.Addr()) && private.Contains(p.Masked().Addr()) {
			return true
		}
	}
	return false
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
	_, err = fmt.Fprintf(out, "remote status: %d resources present; %d resource kinds remain read-contract-gated\n", verified, unavailable)
	return err
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
	if err := Validate(d); err != nil {
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
	var inventory bytes.Buffer
	encoder := yaml.NewEncoder(&inventory)
	if err := encoder.Encode(map[string]any{"all": map[string]any{
		"hosts": hosts, "vars": map[string]string{"vpc_cidr": d.Network.VPCCIDR}, "children": children,
	}}); err != nil {
		return err
	}
	if err := encoder.Close(); err != nil {
		return err
	}
	if err := writePrivateFile(*output, inventory.Bytes()); err != nil {
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

var authorizationValue = regexp.MustCompile(`(?im)(authorization\s*:\s*)[^\r\n]*`)
var secretValue = regexp.MustCompile(`(?i)((?:x-cloud-session|password|token)\s*[:=]\s*)([^\s,;]+)`)

// Redact keeps errors and future API diagnostics from exposing credential values.
func Redact(message string) string {
	return secretValue.ReplaceAllString(authorizationValue.ReplaceAllString(message, "$1[REDACTED]"), "$1[REDACTED]")
}
