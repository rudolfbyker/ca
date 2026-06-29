#!/usr/bin/env python3
"""
Become a Certificate Authority
Based on https://stackoverflow.com/questions/7580508/getting-chrome-to-accept-self-signed-localhost-certificate
"""

from pathlib import Path
from subprocess import run
from typing import Optional

import click
from dotenv import load_dotenv


@click.command()
@click.argument("name")
@click.option(
    "--days",
    type=int,
    default=366,
    help="The number of days for which the new CA will be valid. Defaults to 366 days (just over a year).",
)
@click.option(
    "--subject",
    envvar="CERTIFICATE_AUTHORITY_SUBJECT",
    help="The subject DN for the certificate authority. "
    'Example: "/C=ZA/ST=Gauteng/L=Pretoria/O=Example/OU=IT/CN=mypc.example.com/emailAddress=admin@example.com." '
    "If not given, `openssl` will prompt for each part interactively. "
    "You can set this in `.env` to avoid having to pass it for every command.",
)
def main(
    name: str,
    days: int,
    subject: Optional[str],
) -> int:
    """
    NAME: Any name you want to give to your new CA.
    """
    # Create folder for our CA and its certificates.
    out_dir = Path("out", name)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Generate private key for the CA.
    ca_key_path = Path(out_dir, "private.key")
    if ca_key_path.exists():
        print(f"Private key {ca_key_path} already exists.")
    else:
        print("Creating private for certificate authority…")
        run(
            args=["openssl", "genrsa", "-des3", "-out", str(ca_key_path), "2048"],
            check=True,
        )

    # Generate root certificate.
    ca_root_path = Path(out_dir, "root.pem")
    command = [
        "openssl",
        "req",
        "-x509",
        "-new",
        "-nodes",
        "-key",
        str(ca_key_path),
        "-sha256",
        "-days",
        str(days),
        "-out",
        str(ca_root_path),
    ]
    if subject:
        command.extend(["-subj", subject])
    run(args=command, check=True)

    return 0


if __name__ == "__main__":
    load_dotenv()
    exit(main())
