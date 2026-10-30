package main

import (
	"os"
	"testing"
	"time"
)

// TestInstallRoot exercises Windows store writes and exact-certificate readback.
// Run only in a disposable Windows account or VM: it installs the embedded root.
func TestInstallRoot(t *testing.T) {
	if os.Getenv("CA_INSTALLER_SMOKE_TEST") != "1" {
		t.Skip("requires a disposable Windows account")
	}
	cert, err := parseRoot(rootPEM, time.Now())
	if err != nil {
		t.Fatal(err)
	}
	for attempt := 0; attempt < 2; attempt++ {
		if err := install(cert.Raw); err != nil {
			t.Fatal(err)
		}
	}
}
