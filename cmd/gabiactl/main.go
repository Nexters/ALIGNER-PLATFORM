package main

import (
	"fmt"
	"os"

	"github.com/Nexters/ALIGNER-PLATFORM/internal/gabiactl"
)

func main() {
	if err := gabiactl.Run(os.Args[1:], os.Stdout); err != nil {
		fmt.Fprintln(os.Stderr, gabiactl.Redact(err.Error()))
		os.Exit(1)
	}
}
