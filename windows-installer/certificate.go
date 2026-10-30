package main

import (
	"bytes"
	"crypto/x509"
	_ "embed"
	"encoding/pem"
	"fmt"
	"time"
)

//go:embed root.pem
var rootPEM []byte

// parseRoot accepts exactly one public, currently valid, self-signed CA certificate.
func parseRoot(data []byte, now time.Time) (*x509.Certificate, error) {
	block, rest := pem.Decode(data)
	if block == nil || block.Type != "CERTIFICATE" || len(bytes.TrimSpace(rest)) != 0 {
		return nil, fmt.Errorf("expected exactly one public PEM certificate")
	}
	cert, err := x509.ParseCertificate(block.Bytes)
	if err != nil {
		return nil, err
	}
	if !cert.IsCA || !cert.BasicConstraintsValid {
		return nil, fmt.Errorf("certificate is not a CA")
	}
	if now.Before(cert.NotBefore) || !now.Before(cert.NotAfter) {
		return nil, fmt.Errorf("certificate is not currently valid")
	}
	if !bytes.Equal(cert.RawSubject, cert.RawIssuer) {
		return nil, fmt.Errorf("certificate is not a root CA")
	}
	if err := cert.CheckSignatureFrom(cert); err != nil {
		return nil, fmt.Errorf("invalid root signature: %w", err)
	}
	return cert, nil
}
