package main

import (
	"testing"
	"time"
)

func TestEmbeddedRoot(t *testing.T) {
	data := rootPEM
	cert, err := parseRoot(data, time.Now())
	if err != nil {
		t.Fatal(err)
	}
	if _, err := parseRoot(data, cert.NotAfter); err == nil {
		t.Fatal("accepted expired certificate")
	}
	if _, err := parseRoot(data, cert.NotBefore.Add(-time.Second)); err == nil {
		t.Fatal("accepted future certificate")
	}
	if _, err := parseRoot(append(data, data...), time.Now()); err == nil {
		t.Fatal("accepted multiple certificates")
	}
	if _, err := parseRoot([]byte("private key or invalid input"), time.Now()); err == nil {
		t.Fatal("accepted invalid input")
	}
}
