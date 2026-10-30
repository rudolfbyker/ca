package main

import (
	"crypto/sha256"
	"fmt"
	"os"
	"syscall"
	"time"
	"unsafe"
)

var crypt32 = syscall.NewLazyDLL("crypt32.dll")
var messageBox = syscall.NewLazyDLL("user32.dll").NewProc("MessageBoxW")

// show displays a native dialog without a console window.
func show(text string, flags uintptr) uintptr {
	body, _ := syscall.UTF16PtrFromString(text)
	title, _ := syscall.UTF16PtrFromString("Root certificate setup")
	result, _, _ := messageBox.Call(0, uintptr(unsafe.Pointer(body)), uintptr(unsafe.Pointer(title)), flags)
	return result
}

// install adds the exact certificate to the current user's trusted roots.
func install(der []byte) error {
	name, _ := syscall.UTF16PtrFromString("ROOT")
	// CERT_STORE_PROV_SYSTEM_W, CERT_SYSTEM_STORE_CURRENT_USER.
	store, _, err := crypt32.NewProc("CertOpenStore").Call(10, 0, 0, 0x10000, uintptr(unsafe.Pointer(name)))
	if store == 0 {
		return fmt.Errorf("cannot open your certificate store: %w", err)
	}
	defer crypt32.NewProc("CertCloseStore").Call(store, 0)
	// X509_ASN_ENCODING, CERT_STORE_ADD_USE_EXISTING.
	ok, _, err := crypt32.NewProc("CertAddEncodedCertificateToStore").Call(store, 1,
		uintptr(unsafe.Pointer(&der[0])), uintptr(len(der)), 2, 0)
	if ok == 0 {
		return fmt.Errorf("cannot install the certificate: %w", err)
	}
	// Read back the exact certificate using CERT_FIND_EXISTING.
	expected, _, err := crypt32.NewProc("CertCreateCertificateContext").Call(1,
		uintptr(unsafe.Pointer(&der[0])), uintptr(len(der)))
	if expected == 0 {
		return fmt.Errorf("cannot verify installation: %w", err)
	}
	defer crypt32.NewProc("CertFreeCertificateContext").Call(expected)
	found, _, err := crypt32.NewProc("CertFindCertificateInStore").Call(store, 1, 0, 0x000D0000, expected, 0)
	if found == 0 {
		return fmt.Errorf("certificate was not found after installation: %w", err)
	}
	crypt32.NewProc("CertFreeCertificateContext").Call(found)
	return nil
}

func main() {
	cert, err := parseRoot(rootPEM, time.Now())
	if err != nil {
		show("This installer cannot be used: "+err.Error()+".\nPlease contact your administrator.", 0x10)
		os.Exit(1)
	}
	fingerprint := sha256.Sum256(cert.Raw)
	prompt := fmt.Sprintf("Install this root certificate for your Windows account?\n\nOnly continue if you trust the person or organization that supplied this installer.\n\nCertificate: %s\nExpires: %s\nSHA-256: %X", cert.Subject.CommonName, cert.NotAfter.Format("2 January 2006"), fingerprint)
	if show(prompt, 0x24|0x100) != 6 {
		return
	}
	if err := install(cert.Raw); err != nil {
		show("Setup failed: "+err.Error()+"\nPlease contact your administrator.", 0x10)
		os.Exit(1)
	}
	show("The root certificate was installed for your Windows account.\n\nClose and reopen your browsers, then try the website again.\nIf a warning remains, contact your administrator.", 0x40)
}
