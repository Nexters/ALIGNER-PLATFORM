package gabiactl

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
