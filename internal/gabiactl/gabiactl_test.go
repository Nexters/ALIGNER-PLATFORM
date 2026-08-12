package gabiactl

import (
	"bytes"
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const validYAML = `version: v1
environment: sandbox
network: {vpc_cidr: 10.20.0.0/16, subnet_cidr: 10.20.0.0/24}
servers: {os_image: image-verified, flavor: standard-2-8, count: 2, names: [k3s-01, k3s-02]}
volumes: {data_a_gb: 25, data_b_gb: 40}
load_balancer: {listeners: [{port: 80, protocol: HTTP, target_port: 30080}]}
`

func TestValidateRejectsNullImageAndInvalidCIDR(t *testing.T) {
	d := writeDesired(t, strings.Replace(validYAML, "os_image: image-verified", "os_image: null", 1))
	var out bytes.Buffer
	err := Run([]string{"validate", "-f", d}, &out)
	if err == nil || !strings.Contains(err.Error(), "os_image") {
		t.Fatalf("expected image gate error, got %v", err)
	}
	d = writeDesired(t, strings.Replace(validYAML, "10.20.0.0/24", "10.21.0.0/25", 1))
	err = Run([]string{"validate", "-f", d}, &out)
	if err == nil || !strings.Contains(err.Error(), "subnet_cidr") {
		t.Fatalf("expected CIDR error, got %v", err)
	}
}

func TestMutationsFailClosedWithoutCreatingState(t *testing.T) {
	chdir(t)
	d := writeDesired(t, validYAML)
	err := Run([]string{"apply", "-f", d}, &bytes.Buffer{})
	if err == nil || !strings.Contains(err.Error(), "sandbox gate") {
		t.Fatalf("expected API gate, got %v", err)
	}
	if _, statErr := os.Stat(stateFile); !os.IsNotExist(statErr) {
		t.Fatalf("apply wrote state: %v", statErr)
	}
}

func TestDestroyRequiresExactEnvironment(t *testing.T) {
	d := writeDesired(t, validYAML)
	err := Run([]string{"destroy", "-f", d, "--confirm", "prod"}, &bytes.Buffer{})
	if err == nil || !strings.Contains(err.Error(), "--confirm sandbox") {
		t.Fatalf("expected confirmation guard, got %v", err)
	}
}

func TestAccessOnlyAllowsDeclaredTargetsAnd32(t *testing.T) {
	chdir(t)
	d := writeDesired(t, validYAML)
	err := Run([]string{"access", "open", "-f", d, "--cidr", "10.0.0.0/24", "--targets", "k3s-01"}, &bytes.Buffer{})
	if err == nil || !strings.Contains(err.Error(), "/32") {
		t.Fatalf("expected /32 guard, got %v", err)
	}
	err = Run([]string{"access", "close", "-f", d, "--targets", "unknown"}, &bytes.Buffer{})
	if err == nil || !strings.Contains(err.Error(), "not a declared") {
		t.Fatalf("expected target guard, got %v", err)
	}
	err = Run([]string{"access", "close", "-f", d, "--targets", "k3s-01"}, &bytes.Buffer{})
	if err == nil || !strings.Contains(err.Error(), "sandbox gate") {
		t.Fatalf("expected close API gate, got %v", err)
	}
	if _, statErr := os.Stat(stateFile); !os.IsNotExist(statErr) {
		t.Fatalf("access close wrote state: %v", statErr)
	}
	err = Run([]string{"access", "open", "-f", d, "--cidr", "203.0.113.10/32", "--targets", "k3s-01"}, &bytes.Buffer{})
	if err == nil || !strings.Contains(err.Error(), "sandbox gate") {
		t.Fatalf("expected open API gate, got %v", err)
	}
	if _, statErr := os.Stat(stateFile); !os.IsNotExist(statErr) {
		t.Fatalf("access open wrote state: %v", statErr)
	}
}

func TestInventoryUsesStateWithoutCredentials(t *testing.T) {
	chdir(t)
	d := writeDesired(t, validYAML)
	if err := os.MkdirAll(".runtime", 0750); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(stateFile, []byte(`{"environment":"sandbox","servers":{"k3s-01":{"id":"server-1","private_ip":"10.20.0.10"},"k3s-02":{"id":"server-2","private_ip":"10.20.0.11"}}}`), 0600); err != nil {
		t.Fatal(err)
	}
	output := filepath.Join(t.TempDir(), "inventory.yaml")
	if err := Run([]string{"inventory", "-f", d, "--connect-via", "private", "-o", output}, &bytes.Buffer{}); err != nil {
		t.Fatal(err)
	}
	b, err := os.ReadFile(output)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(b), "ansible_host: 10.20.0.10") {
		t.Fatalf("unexpected inventory: %s", b)
	}
}

func TestRedact(t *testing.T) {
	got := Redact("Authorization: Basic secret x-cloud-session=abc token: xyz")
	if strings.Contains(got, "secret") || strings.Contains(got, "abc") || strings.Contains(got, "xyz") {
		t.Fatalf("secret leaked: %s", got)
	}
}

func TestPlanOrdersStableNodeResourcesAndRecordedStateIsNoop(t *testing.T) {
	threeNodeYAML := strings.Replace(validYAML, "count: 2, names: [k3s-01, k3s-02]", "count: 3, names: [k3s-01, k3s-02, k3s-03]", 1)
	d, err := loadDesired([]string{"-f", writeDesired(t, threeNodeYAML)})
	if err != nil {
		t.Fatal(err)
	}
	steps, err := Plan(d, State{})
	if err != nil {
		t.Fatal(err)
	}
	want := []string{
		"vpc", "subnet", "router", "security-group",
		"volume/k3s-01/data-a", "volume/k3s-01/data-b", "public-ip/k3s-01",
		"volume/k3s-02/data-a", "volume/k3s-02/data-b", "public-ip/k3s-02",
		"volume/k3s-03/data-a", "volume/k3s-03/data-b", "public-ip/k3s-03",
		"server/k3s-01", "server/k3s-02", "server/k3s-03", "load-balancer",
	}
	if len(steps) != len(want) {
		t.Fatalf("plan length = %d, want %d", len(steps), len(want))
	}
	for i, identity := range want {
		if steps[i].Resource.Identity != identity || steps[i].Change != Create {
			t.Fatalf("step %d = %#v, want create %s", i, steps[i], identity)
		}
	}
	if got := steps[13].Resource.DependsOn; !containsAll(got, "volume/k3s-01/data-a", "volume/k3s-01/data-b", "public-ip/k3s-01", "security-group") {
		t.Fatalf("server links = %v", got)
	}
	state, err := Reconcile(context.Background(), d, State{}, &fakeProvider{})
	if err != nil {
		t.Fatal(err)
	}
	steps, err = Plan(d, state)
	if err != nil {
		t.Fatal(err)
	}
	for _, step := range steps {
		if step.Change != Noop {
			t.Fatalf("second plan %s = %s, want no-op", step.Resource.Identity, step.Change)
		}
	}
	if state.Resources["volume/k3s-01/data-a"].ID == state.Resources["volume/k3s-02/data-a"].ID {
		t.Fatal("node volume identities must remain distinct")
	}
}

func containsAll(values []string, want ...string) bool {
	seen := make(map[string]bool, len(values))
	for _, value := range values {
		seen[value] = true
	}
	for _, value := range want {
		if !seen[value] {
			return false
		}
	}
	return true
}

func TestReconcileResumesCompletedPrefixAfterFailure(t *testing.T) {
	d, err := loadDesired([]string{"-f", writeDesired(t, validYAML)})
	if err != nil {
		t.Fatal(err)
	}
	provider := &fakeProvider{fail: "public-ip/k3s-02"}
	state, err := Reconcile(context.Background(), d, State{}, provider)
	if err == nil || !strings.Contains(err.Error(), "public-ip/k3s-02") {
		t.Fatalf("expected partial failure, got %v", err)
	}
	if _, ok := state.Resources["public-ip/k3s-01"]; !ok {
		t.Fatal("completed prefix was not returned")
	}
	provider.fail = ""
	state, err = Reconcile(context.Background(), d, state, provider)
	if err != nil {
		t.Fatal(err)
	}
	if len(state.Resources) != 13 { // 4 network + 4 volume + 2 public IP + 2 server + LB
		t.Fatalf("unexpected resource count: %d", len(state.Resources))
	}
}

func TestInventoryUsesPublicAndPrivateRecordedServerAddresses(t *testing.T) {
	chdir(t)
	d := writeDesired(t, validYAML)
	if err := os.MkdirAll(".runtime", 0750); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(stateFile, []byte(`{"environment":"sandbox","servers":{"k3s-01":{"id":"server-1","public_ip":"203.0.113.10","private_ip":"10.20.0.10"},"k3s-02":{"id":"server-2","public_ip":"203.0.113.11","private_ip":"10.20.0.11"}}}`), 0600); err != nil {
		t.Fatal(err)
	}
	for _, via := range []struct{ via, address string }{{"public", "203.0.113.10"}, {"private", "10.20.0.10"}} {
		output := filepath.Join(t.TempDir(), via.via+".yaml")
		if err := Run([]string{"inventory", "-f", d, "--connect-via", via.via, "-o", output}, &bytes.Buffer{}); err != nil {
			t.Fatal(err)
		}
		b, err := os.ReadFile(output)
		if err != nil || !strings.Contains(string(b), "ansible_host: "+via.address) {
			t.Fatalf("%s inventory = %s, %v", via.via, b, err)
		}
	}
}

func TestClientRejectsCredentialExfiltrationEndpoint(t *testing.T) {
	credentials := Credentials{Username: "user", Password: "password"}
	_, err := NewClient(credentials, "https://identity-api.gabiacloud.com.evil.example/api/v1", "", nil)
	if err == nil {
		t.Fatal("expected non-Gabia identity endpoint to be rejected")
	}
	_, err = NewClient(credentials, "", "https://example.com/api/v1", nil)
	if err == nil {
		t.Fatal("expected non-Gabia cloud endpoint to be rejected")
	}
}

func TestClientAuthenticatesAndOnlyReadsVerifiedEndpoint(t *testing.T) {
	var session, read bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/identity/sessions":
			username, password, ok := r.BasicAuth()
			if !ok || username != "user" || password != "password" || r.Method != http.MethodPost {
				t.Errorf("bad authentication request")
			}
			session = true
			w.WriteHeader(http.StatusCreated)
			_, _ = w.Write([]byte(`{"session":{"id":"session-secret"}}`))
		case "/cloud/subnets/subnet-1":
			if r.Header.Get("X-Cloud-Session") != "session-secret" {
				t.Errorf("missing session")
			}
			read = true
			w.WriteHeader(http.StatusOK)
		default:
			t.Errorf("unexpected request %s", r.URL.Path)
			w.WriteHeader(http.StatusNotFound)
		}
	}))
	defer server.Close()
	client, err := NewClient(Credentials{Username: "user", Password: "password"}, server.URL+"/identity", server.URL+"/cloud", server.Client())
	if err != nil {
		t.Fatal(err)
	}
	found, err := client.ObserveRecorded(context.Background(), Resource{Identity: "subnet", Kind: SubnetResource}, ResourceState{ID: "subnet-1"})
	if err != nil || !found || !session || !read {
		t.Fatalf("observe = %v, %v; session=%v read=%v", found, err, session, read)
	}
	if _, err := client.Create(context.Background(), Resource{}); err == nil || !strings.Contains(err.Error(), "sandbox gate") {
		t.Fatalf("create = %v", err)
	}
}

func TestRunStatusReconcilesRecordedSubnetWithoutMutatingState(t *testing.T) {
	for _, tc := range []struct {
		name       string
		subnetCode int
		want       string
	}{
		{name: "present", subnetCode: http.StatusOK, want: "remote status: 1 resources present; 3 resource kinds remain read-contract-gated"},
		{name: "missing", subnetCode: http.StatusNotFound, want: "status drift: subnet (subnet-1) is absent remotely"},
		{name: "service error", subnetCode: http.StatusBadGateway, want: "unexpected HTTP 502"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			chdir(t)
			if err := os.MkdirAll(".runtime", 0750); err != nil {
				t.Fatal(err)
			}
			state := `{"environment":"sandbox","resources":{"vpc":{"id":"vpc-1"},"subnet":{"id":"subnet-1"}},"servers":{"k3s-01":{"id":"server-1","private_ip":"10.20.0.10"},"k3s-02":{"id":"server-2","private_ip":"10.20.0.11"}}}`
			if err := os.WriteFile(stateFile, []byte(state), stateFileMode); err != nil {
				t.Fatal(err)
			}
			before, err := os.ReadFile(stateFile)
			if err != nil {
				t.Fatal(err)
			}
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				switch r.URL.Path {
				case "/identity/sessions":
					username, password, ok := r.BasicAuth()
					if !ok || username != "user" || password != "password" {
						t.Error("status did not use the configured Basic credentials")
					}
					w.WriteHeader(http.StatusCreated)
					_, _ = w.Write([]byte(`{"session":{"id":"session-secret"}}`))
				case "/cloud/subnets/subnet-1":
					if r.Header.Get("X-Cloud-Session") != "session-secret" {
						t.Error("status did not send the issued cloud session")
					}
					w.WriteHeader(tc.subnetCode)
				default:
					t.Errorf("unexpected status request %s", r.URL.Path)
					w.WriteHeader(http.StatusNotFound)
				}
			}))
			defer server.Close()
			t.Setenv("GABIACLOUD_USERNAME", "user")
			t.Setenv("GABIACLOUD_PASSWORD", "password")
			t.Setenv("GABIACLOUD_IDENTITY_ENDPOINT", server.URL+"/identity")
			t.Setenv("GABIACLOUD_CLOUD_ENDPOINT", server.URL+"/cloud")
			var out bytes.Buffer
			err = Run([]string{"status", "-f", writeDesired(t, validYAML)}, &out)
			if err != nil && !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("status error = %v, want %q", err, tc.want)
			}
			if err == nil && !strings.Contains(out.String(), tc.want) {
				t.Fatalf("status output = %q, want %q", out.String(), tc.want)
			}
			after, err := os.ReadFile(stateFile)
			if err != nil || !bytes.Equal(before, after) {
				t.Fatalf("status mutated state: %q, %v", after, err)
			}
			if bytes.Contains(after, []byte("password")) || bytes.Contains(after, []byte("session-secret")) {
				t.Fatal("status wrote credentials or a session to state")
			}
		})
	}
}

type fakeProvider struct {
	resources map[string]ResourceState
	fail      string
}

func (p *fakeProvider) Observe(_ context.Context, resource Resource) (ResourceState, bool, error) {
	state, ok := p.resources[resource.Identity]
	return state, ok, nil
}

func (p *fakeProvider) Create(_ context.Context, resource Resource) (ResourceState, error) {
	if resource.Identity == p.fail {
		return ResourceState{}, fmt.Errorf("injected failure")
	}
	if p.resources == nil {
		p.resources = make(map[string]ResourceState)
	}
	state := ResourceState{ID: "id-" + resource.Identity}
	if resource.Kind == ServerResource {
		state.PrivateIP = "10.20.0.10"
		state.PublicIP = "203.0.113.10"
	}
	p.resources[resource.Identity] = state
	return state, nil
}

func writeDesired(t *testing.T, content string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "desired.yaml")
	if err := os.WriteFile(path, []byte(content), 0600); err != nil {
		t.Fatal(err)
	}
	return path
}
func chdir(t *testing.T) {
	t.Helper()
	old, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	dir := t.TempDir()
	if err := os.Chdir(dir); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = os.Chdir(old) })
}
