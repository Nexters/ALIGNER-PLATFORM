package gabiactl

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/netip"
	"net/url"
	"os"
	"strings"
	"sync"
	"time"

	"golang.org/x/term"
)

const (
	defaultIdentityEndpoint = "https://identity-api.gabiacloud.com/api/v1"
	defaultCloudEndpoint    = "https://cloud-api.gabiacloud.com/api/v1"
)

// Credentials are read only for the lifetime of one process.  They must never
// be copied into State or included in an error.
type Credentials struct{ Username, Password string }

func ReadCredentials(prompt io.Writer) (Credentials, error) {
	username, password := os.Getenv("GABIACLOUD_USERNAME"), os.Getenv("GABIACLOUD_PASSWORD")
	if username != "" && password != "" {
		return Credentials{Username: username, Password: password}, nil
	}
	if username == "" {
		return Credentials{}, errors.New("GABIACLOUD_USERNAME is required (password is read from GABIACLOUD_PASSWORD or a TTY)")
	}
	if password != "" {
		return Credentials{Username: username, Password: password}, nil
	}
	tty, err := os.OpenFile("/dev/tty", os.O_RDWR, 0)
	if err != nil {
		return Credentials{}, errors.New("GABIACLOUD_PASSWORD is required when no TTY is available")
	}
	defer func() { _ = tty.Close() }()
	_, _ = fmt.Fprint(prompt, "Gabia Cloud password: ")
	b, err := term.ReadPassword(int(tty.Fd()))
	_, _ = fmt.Fprintln(prompt)
	if err != nil || len(b) == 0 {
		return Credentials{}, errors.New("Gabia Cloud password was not read from TTY")
	}
	return Credentials{Username: username, Password: string(b)}, nil
}

// Client implements the verified session protocol and read-only resource
// observations. Creation remains deliberately closed until each payload and
// asynchronous completion contract has been sandbox-verified.
type Client struct {
	identity, cloud *url.URL
	httpClient      *http.Client
	credentials     Credentials
	mu              sync.Mutex
	session         string
}

func NewClient(credentials Credentials, identityEndpoint, cloudEndpoint string, httpClient *http.Client) (*Client, error) {
	if credentials.Username == "" || credentials.Password == "" {
		return nil, errors.New("Gabia Cloud credentials are required")
	}
	if identityEndpoint == "" {
		identityEndpoint = defaultIdentityEndpoint
	}
	if cloudEndpoint == "" {
		cloudEndpoint = defaultCloudEndpoint
	}
	identity, err := url.Parse(identityEndpoint)
	if err != nil || !safeEndpoint(identity, "identity-api.gabiacloud.com") {
		return nil, errors.New("invalid Gabia identity endpoint")
	}
	cloud, err := url.Parse(cloudEndpoint)
	if err != nil || !safeEndpoint(cloud, "cloud-api.gabiacloud.com") {
		return nil, errors.New("invalid Gabia cloud endpoint")
	}
	if httpClient == nil {
		httpClient = &http.Client{Timeout: 30 * time.Second}
	}
	return &Client{identity: identity, cloud: cloud, httpClient: httpClient, credentials: credentials}, nil
}

func safeEndpoint(endpoint *url.URL, productionHost string) bool {
	if endpoint.Host == "" || endpoint.User != nil || endpoint.RawQuery != "" || endpoint.Fragment != "" {
		return false
	}
	if endpoint.Scheme == "https" {
		return endpoint.Hostname() == productionHost && endpoint.Port() == ""
	}
	if endpoint.Scheme != "http" {
		return false
	}
	host := endpoint.Hostname()
	address, err := netip.ParseAddr(host)
	return host == "localhost" || err == nil && address.IsLoopback()
}

func (c *Client) Observe(ctx context.Context, resource Resource) (ResourceState, bool, error) {
	return ResourceState{}, false, fmt.Errorf("observe %s requires a recorded cloud ID; use status for remote reconciliation", resource.Identity)
}

func (c *Client) Create(context.Context, Resource) (ResourceState, error) {
	return ResourceState{}, errors.New("Gabia create sandbox gate is not complete: no write API request was made")
}

func (c *Client) authenticate(ctx context.Context) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.session != "" {
		return nil
	}
	u := *c.identity
	u.Path = strings.TrimRight(u.Path, "/") + "/sessions"
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, u.String(), bytes.NewReader([]byte("{}")))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.SetBasicAuth(c.credentials.Username, c.credentials.Password)
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("create Gabia session: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("create Gabia session: unexpected HTTP %d", resp.StatusCode)
	}
	var response struct {
		Session struct {
			ID string `json:"id"`
		} `json:"session"`
	}
	if err := json.NewDecoder(io.LimitReader(resp.Body, 1<<20)).Decode(&response); err != nil {
		return fmt.Errorf("decode Gabia session: %w", err)
	}
	if response.Session.ID == "" {
		return errors.New("Gabia session response has no session ID")
	}
	c.session = response.Session.ID
	return nil
}

func (c *Client) get(ctx context.Context, path string) (int, error) {
	for attempt := 0; attempt < 2; attempt++ {
		if err := c.authenticate(ctx); err != nil {
			return 0, err
		}
		c.mu.Lock()
		session := c.session
		c.mu.Unlock()
		u := *c.cloud
		u.Path = strings.TrimRight(u.Path, "/") + path
		req, err := http.NewRequestWithContext(ctx, http.MethodGet, u.String(), nil)
		if err != nil {
			return 0, err
		}
		req.Header.Set("X-Cloud-Session", session)
		resp, err := c.httpClient.Do(req)
		if err != nil {
			return 0, fmt.Errorf("Gabia read %s: %w", path, err)
		}
		_, _ = io.Copy(io.Discard, io.LimitReader(resp.Body, 1<<20))
		_ = resp.Body.Close()
		if attempt == 0 && (resp.StatusCode == http.StatusUnauthorized || resp.StatusCode == http.StatusForbidden) {
			c.mu.Lock()
			if c.session == session {
				c.session = ""
			}
			c.mu.Unlock()
			continue
		}
		return resp.StatusCode, nil
	}
	return 0, errors.New("Gabia session reauthentication failed")
}

func (c *Client) ObserveRecorded(ctx context.Context, resource Resource, recorded ResourceState) (bool, error) {
	if recorded.ID == "" {
		return false, nil
	}
	path, ok := readPath(resource.Kind, recorded.ID)
	if !ok {
		return false, fmt.Errorf("remote read for %s is not contract-verified", resource.Identity)
	}
	status, err := c.get(ctx, path)
	if err != nil {
		return false, err
	}
	if status == http.StatusNotFound {
		return false, nil
	}
	if status < 200 || status >= 300 {
		return false, fmt.Errorf("Gabia read %s: unexpected HTTP %d", resource.Identity, status)
	}
	return true, nil
}

func readPath(kind ResourceKind, id string) (string, bool) {
	switch kind {
	case SubnetResource:
		return "/subnets/" + url.PathEscape(id), true
	default:
		return "", false
	}
}
