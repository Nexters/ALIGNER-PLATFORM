package gabiactl

import (
	"context"
	"errors"
	"fmt"
)

// ResourceKind is deliberately limited to the resources described by Desired.
// It is not a Gabia API model: endpoint and payload details remain sandbox-gated.
type ResourceKind string

const (
	VPCResource           ResourceKind = "vpc"
	SubnetResource        ResourceKind = "subnet"
	RouterResource        ResourceKind = "router"
	SecurityGroupResource ResourceKind = "security-group"
	VolumeResource        ResourceKind = "volume"
	PublicIPResource      ResourceKind = "public-ip"
	ServerResource        ResourceKind = "server"
	LoadBalancerResource  ResourceKind = "load-balancer"
)

// Resource has a stable, local identity and only dependency information. A
// future Gabia adapter translates it after the sandbox verifies its API schema.
type Resource struct {
	Identity  string
	Kind      ResourceKind
	DependsOn []string
}

type Change string

const (
	Create Change = "create"
	Noop   Change = "no-op"
)

type Step struct {
	Resource Resource
	Change   Change
}

// Provider is intentionally smaller than a cloud SDK. Implementations must
// observe by stable identity before creating a resource.
type Provider interface {
	Observe(context.Context, Resource) (ResourceState, bool, error)
	Create(context.Context, Resource) (ResourceState, error)
}

// Plan returns creation steps in dependency order. Recorded state makes a step
// a no-op, so a successful prefix can be safely reused after a partial failure.
func Plan(d Desired, state State) ([]Step, error) {
	if err := Validate(d); err != nil {
		return nil, err
	}
	resources := desiredResources(d)
	steps := make([]Step, 0, len(resources))
	for _, resource := range resources {
		change := Create
		if recorded(state, resource.Identity) {
			change = Noop
		}
		steps = append(steps, Step{Resource: resource, Change: change})
	}
	return steps, nil
}

// Reconcile executes only the deterministic plan. It returns the state after
// every completed step, including on error, so callers can persist that prefix
// and resume it. The CLI does not call this until the write sandbox is verified.
func Reconcile(ctx context.Context, d Desired, state State, provider Provider) (State, error) {
	if provider == nil {
		return state, errors.New("reconcile requires a provider")
	}
	steps, err := Plan(d, state)
	if err != nil {
		return state, err
	}
	state.Environment = d.Environment
	for _, step := range steps {
		if step.Change == Noop {
			continue
		}
		observed, found, err := provider.Observe(ctx, step.Resource)
		if err != nil {
			return state, fmt.Errorf("observe %s: %w", step.Resource.Identity, err)
		}
		if !found {
			observed, err = provider.Create(ctx, step.Resource)
			if err != nil {
				return state, fmt.Errorf("create %s: %w", step.Resource.Identity, err)
			}
		}
		if observed.ID == "" {
			return state, fmt.Errorf("%s returned without an ID", step.Resource.Identity)
		}
		record(&state, step.Resource, observed)
	}
	return state, nil
}

func desiredResources(d Desired) []Resource {
	resources := []Resource{
		{Identity: "vpc", Kind: VPCResource},
		{Identity: "subnet", Kind: SubnetResource, DependsOn: []string{"vpc"}},
		{Identity: "router", Kind: RouterResource, DependsOn: []string{"vpc", "subnet"}},
		{Identity: "security-group", Kind: SecurityGroupResource, DependsOn: []string{"vpc"}},
	}
	for _, name := range d.Servers.Names {
		resources = append(resources,
			Resource{Identity: "volume/" + name + "/data-a", Kind: VolumeResource},
			Resource{Identity: "volume/" + name + "/data-b", Kind: VolumeResource},
			Resource{Identity: "public-ip/" + name, Kind: PublicIPResource, DependsOn: []string{"subnet", "router"}},
		)
	}
	for _, name := range d.Servers.Names {
		resources = append(resources, Resource{Identity: "server/" + name, Kind: ServerResource, DependsOn: []string{
			"subnet", "router", "security-group", "volume/" + name + "/data-a", "volume/" + name + "/data-b", "public-ip/" + name,
		}})
	}
	serverDependencies := make([]string, 0, len(d.Servers.Names)+3)
	serverDependencies = append(serverDependencies, "subnet", "router", "security-group")
	for _, name := range d.Servers.Names {
		serverDependencies = append(serverDependencies, "server/"+name)
	}
	return append(resources, Resource{Identity: "load-balancer", Kind: LoadBalancerResource, DependsOn: serverDependencies})
}

func recorded(state State, identity string) bool {
	resource, ok := state.Resources[identity]
	return ok && resource.ID != ""
}

func record(state *State, resource Resource, observed ResourceState) {
	if state.Resources == nil {
		state.Resources = make(map[string]ResourceState)
	}
	state.Resources[resource.Identity] = observed
	if resource.Kind == ServerResource {
		name := resource.Identity[len("server/"):]
		if state.Servers == nil {
			state.Servers = make(map[string]ServerState)
		}
		state.Servers[name] = ServerState{ID: observed.ID, PublicIP: observed.PublicIP, PrivateIP: observed.PrivateIP}
	}
}
