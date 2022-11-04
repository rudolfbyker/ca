#!/usr/bin/env python3
"""
Become a Certificate Authority
Based on https://stackoverflow.com/questions/7580508/getting-chrome-to-accept-self-signed-localhost-certificate
"""

from pathlib import Path
from subprocess import Popen

import click


@click.command()
@click.argument("name")
@click.option(
    "--days",
    type=int,
    default=366,
    help="The number of days for which the new CA will be valid. Defaults to 366 days (just over a year).",
)
def main(
    name: str,
    days: int,
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
        Popen(f"openssl genrsa -des3 -out '{ca_key_path}' 2048", shell=True).wait()

    # Generate root certificate.
    ca_root_path = Path(out_dir, "root.pem")
    # TODO: maybe rotate the old file instead of overwriting?
    command = f"openssl req -x509 -new -nodes -key '{ca_key_path}' -sha256 -days {days} -out '{ca_root_path}'"
    Popen(command, shell=True).wait()

    return 0


if __name__ == "__main__":
    exit(main())
