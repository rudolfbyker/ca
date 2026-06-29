#!/usr/bin/env python3
"""
Create CA-signed certs
From https://stackoverflow.com/questions/7580508/getting-chrome-to-accept-self-signed-localhost-certificate
"""

from pathlib import Path
from subprocess import run
from typing import Optional, Tuple

import click
from dotenv import load_dotenv


@click.command()
@click.argument("ca")
@click.argument("domains", nargs=-1)
@click.option(
    "--days",
    type=int,
    default=366,
    help="The number of days for which the new certificate will be valid. Defaults to 366 days (just over a year).",
)
@click.option(
    "--subject",
    envvar="CERTIFICATE_SUBJECT",
    help="The subject DN for the certificate request. "
    'Example: "/C=ZA/ST=Gauteng/L=Pretoria/O=Example/OU=IT/CN=mypc.example.com/emailAddress=admin@example.com." '
    "If not given, `openssl` will prompt for each part interactively. "
    "You can set this in `.env` to avoid having to pass it for every command.",
)
def main(
    ca: str,
    domains: Tuple[str, ...],
    days: int,
    subject: Optional[str],
) -> int:
    """
    CA: The name of the CA you passed to `create_certificate_authority.py`.

    DOMAINS: One or more domain names for which the certificate should be valid. Specify the highest level domain first.

    Example:
        ./create_certificate.py my-vm my-vm.my-vpn "*.my-vm.my-vpn"

    Note that wildcard DNS names must be quoted to prevent your shell from treating it as a filename glob.
    """
    if len(domains) < 1:
        print("No domains given. Nothing to do.")
        return 0

    # Use the first domain name as the folder name.
    out_dir = Path("out", ca, domains[0])
    out_dir.mkdir(parents=True, exist_ok=True)

    # Check if the certificate authority files exist.
    ca_path = Path(out_dir, "..", "root.pem").resolve()
    if not ca_path.exists():
        print(
            f"File {ca_path} does not exist. Did you run create_certificate_authority.py first?"
        )
        return 1
    ca_key_path = Path(out_dir, "..", "private.key").resolve()
    if not ca_key_path.exists():
        print(
            f"File {ca_key_path} does not exist. Did you run create_certificate_authority.py first?"
        )
        return 1

    # Generate private key if it does not exist yet.
    key_path = Path(out_dir, "private.key")
    if key_path.exists():
        print(f"Private key {key_path} already exists.")
    else:
        print("Creating private key for certificate…")
        run(args=["openssl", "genrsa", "-out", str(key_path), "2048"], check=True)

    # Create certificate-signing request if it does not exist.
    csr_path = Path(out_dir, "request.csr")
    if csr_path.exists():
        print(f"Certificate signing request {csr_path} already exists.")
    else:
        print("Creating certificate signing request…")
        command = [
            "openssl",
            "req",
            "-new",
            "-key",
            str(key_path),
            "-out",
            str(csr_path),
        ]
        if subject:
            command.extend(["-subj", subject])
        run(args=command, check=True)

    # Create a config file for the extensions.
    print("Creating config file for extensions…")
    ext_path = Path(out_dir, "config.ext")
    alt_names = "\n".join([f"DNS.{i + 1} = {d}" for i, d in enumerate(domains)])
    with ext_path.open(mode="w") as f:
        f.write(f"""\
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names
[alt_names]
{alt_names}
""")

    # Create the signed certificate.
    print("Creating signed certificate…")
    cert_path = Path(out_dir, "certificate.crt")
    command = [
        "openssl",
        "x509",
        "-req",
        "-in",
        str(csr_path),
        "-CA",
        str(ca_path),
        "-CAkey",
        str(ca_key_path),
        "-CAcreateserial",
        "-out",
        str(cert_path),
        "-days",
        str(days),
        "-sha256",
        "-extfile",
        str(ext_path),
    ]
    run(args=command, check=True)

    return 0


if __name__ == "__main__":
    load_dotenv()
    exit(main())
