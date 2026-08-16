package gabiactl

import (
	"errors"
	"net/netip"
	"regexp"
	"strings"
)

var environmentName = regexp.MustCompile(`^[a-z][a-z0-9-]{0,62}$`)

// Validate checks that the desired infrastructure meets all architectural constraints.
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
		if !((l.Port == 80 && l.Protocol == "HTTP") || (l.Port == 443 && (l.Protocol == "HTTPS" || l.Protocol == "TCP"))) || l.TargetPort < 1 || l.TargetPort > 65535 {
			problems = append(problems, "load balancer listeners allow only HTTP/80 or HTTPS/TCP 443 with a valid target_port")
			break
		}
	}
	if len(problems) > 0 {
		return errors.New(strings.Join(problems, "; "))
	}
	return nil
}

func isRFC1918(p netip.Prefix) bool {
	for _, private := range []netip.Prefix{
		netip.MustParsePrefix("10.0.0.0/8"),
		netip.MustParsePrefix("172.16.0.0/12"),
		netip.MustParsePrefix("192.168.0.0/16"),
	} {
		if private.Contains(p.Addr()) && private.Contains(p.Masked().Addr()) && p.Bits() >= private.Bits() {
			return true
		}
	}
	return false
}
