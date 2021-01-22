#!/usr/bin/env python3
"""
Create CA-signed certs
From https://stackoverflow.com/questions/7580508/getting-chrome-to-accept-self-signed-localhost-certificate
"""
from pathlib import Path
from subprocess import Popen

import click


@click.command()
@click.argument('ca')
@click.argument('domains', nargs=-1)
def main(ca, domains) -> int:
    """
    :param ca: The name of the CA you passed to `create_certificate_authority.py`.
    :param domains: One or more domain names for which the certificate should be valid.
        Specify the highest level domain first.
    """
    if len(domains) < 1:
        print("No domains given. Nothing to do.")
        return 0

    # Use the first domain name as the folder name.
    out_dir = Path('out', ca, domains[0])
    out_dir.mkdir(parents=True, exist_ok=True)

    # Check if the certificate authority files exist.
    ca_path = Path(out_dir, '..', 'root.pem').resolve()
    if not ca_path.exists():
        print(f"File {ca_path} does not exist. Did you run create_certificate_authority.py first?")
        return 1
    ca_key_path = Path(out_dir, '..', 'private.key').resolve()
    if not ca_key_path.exists():
        print(f"File {ca_key_path} does not exist. Did you run create_certificate_authority.py first?")
        return 1

    # Generate private key if it does not exist yet.
    key_path = Path(out_dir, 'private.key')
    if key_path.exists():
        print(f"Private key {key_path} already exists.")
    else:
        print("Creating private key for certificate…")
        Popen(f"openssl genrsa -out '{key_path}' 2048", shell=True).wait()

    # Create certificate-signing request if it does not exist.
    csr_path = Path(out_dir, 'request.csr')
    if csr_path.exists():
        print(f"Certificate signing request {csr_path} already exists.")
    else:
        print("Creating certificate signing request…")
        Popen(f"openssl req -new -key '{key_path}' -out '{csr_path}'", shell=True).wait()

    # Create a config file for the extensions.
    print("Creating config file for extensions…")
    ext_path = Path(out_dir, 'config.ext')
    alt_names = "\n".join([f"DNS.{i + 1} = {d}" for i, d in enumerate(domains)])
    # TODO: maybe rotate the old file instead of overwriting?
    with ext_path.open(mode='w') as f:
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
    cert_path = Path(out_dir, 'certificate.crt')
    # TODO: maybe rotate the old file instead of overwriting?
    command = f"openssl x509 -req -in '{csr_path}' -CA '{ca_path}' -CAkey '{ca_key_path}' -CAcreateserial " \
              f"-out '{cert_path}' -days 1825 -sha256 -extfile '{ext_path}'"
    Popen(command, shell=True).wait()


if __name__ == '__main__':
    exit(main())
