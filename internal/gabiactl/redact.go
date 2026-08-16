package gabiactl

import (
	"regexp"
)

var (
	authorizationValue = regexp.MustCompile(`(?im)(authorization\s*:\s*)[^\r\n]*`)
	secretValue        = regexp.MustCompile(`(?i)((?:x-cloud-session|password|token)\s*[:=]\s*)([^\s,;]+)`)
)

// Redact keeps errors and future API diagnostics from exposing credential values.
func Redact(message string) string {
	return secretValue.ReplaceAllString(authorizationValue.ReplaceAllString(message, "$1[REDACTED]"), "$1[REDACTED]")
}
