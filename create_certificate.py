#!/usr/bin/env python3
"""
Create CA-signed certs
From https://stackoverflow.com/questions/7580508/getting-chrome-to-accept-self-signed-localhost-certificate
"""

from pathlib import Path
from secrets import randbits
from subprocess import run
from typing import Optional, Tuple

import click
from dotenv import load_dotenv

from output_transaction import output_transaction


@click.command()
@click.argument("ca")
@click.argument("domains", nargs=-1)
@click.option(
    "--existing",
    type=click.Choice(["renew", "replace", "error"]),
    default="renew",
    show_default=True,
    help="How to handle existing files: renew reuses the key, replace recreates the key and certificate, "
    "and error stops if any output file exists.",
)
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
    *,
    ca: str,
    domains: Tuple[str, ...],
    days: int,
    existing: str,
    subject: Optional[str],
) -> int:
    """
    Create a certificate signed by a named CA.

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
    if existing == "error":
        existing_paths = [
            out_dir / name
            for name in ("private.key", "request.csr", "certificate.crt", "config.ext")
            if (out_dir / name).exists()
        ]
        if existing_paths:
            paths = ", ".join(str(path) for path in existing_paths)
            raise click.ClickException(
                f"Output files already exist: {paths}. Use --existing=renew to reuse the key "
                "or --existing=replace to create a new key and certificate."
            )
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

    with output_transaction(
        out_dir=out_dir,
        filenames=("private.key", "request.csr", "config.ext", "certificate.crt"),
    ) as staging:
        # Generate private key if it does not exist yet.
        key_path = Path(staging, "private.key")
        if key_path.exists() and existing != "replace":
            print(f"Private key {key_path} already exists.")
        else:
            print("Creating private key for certificate…")
            run(args=["openssl", "genrsa", "-out", str(key_path), "2048"], check=True)

        # Create certificate-signing request if it does not exist.
        csr_path = Path(staging, "request.csr")
        if csr_path.exists() and existing != "replace":
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
        ext_path = Path(staging, "config.ext")
        alt_names = "\n".join([f"DNS.{i + 1} = {d}" for i, d in enumerate(domains)])
        ext_path.write_text(f"""
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names
[alt_names]
{alt_names}
""")

        # Create the signed certificate.
        print("Creating signed certificate…")
        cert_path = Path(staging, "certificate.crt")
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
            "-set_serial",
            str(randbits(159) or 1),
            "-out",
            str(cert_path),
            "-days",
            str(days),
            "-sha256",
            "-extfile",
            str(ext_path),
        ]
        run(args=command, check=True)

        run(
            args=["openssl", "verify", "-CAfile", str(ca_path), str(cert_path)],
            check=True,
        )

    return 0


if __name__ == "__main__":
    load_dotenv()
    exit(main())
