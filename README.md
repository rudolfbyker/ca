# Self-signed certificates

Become a Certificate Authority and sign your own certificates.

Based on scripts found at 
https://stackoverflow.com/questions/7580508/getting-chrome-to-accept-self-signed-localhost-certificate

## Installing on ISPConfig

On the website's SSL tab, paste the contents of these files into the corresponding fields:

- `out/ca/domain/private.key` → SSL Key
- `out/ca/domain/request.csr` → SSL Request
- `out/ca/domain/certificate.crt` → SSL Certificate
- `out/ca/root.pem` → SSL Bundle

TODO: I'm not sure how or why this works.

Source: https://www.httpcs.com/en/help/certificats/tutorial/how-to-install-an-ssl-certificate-on-ispconfig

## Installing on Kubernetes *(nginx ingress controller)*

Navigate to `out/ca/domain`

### Create a new tls secret in the namespace of your ingress

Use the following command to add a secret:
*(replace `{{name}}` with whatever you want to  call the secret)*

`kubectl create secret tls {{name}} --key ./private.key --cert certificate.crt`

This command does the following
1. Create a new secret
2. Of type `tls`
3. Set the name of the secret to `{{name}}`
4. Set the private key to the contents of the file `private.key`
5. Set the certificate to the contents of the file `certificate.csr`

### Use the tls secret in the ingress controller

In your ingress yaml file:

Under `spec`, add the following:
*(make sure to replace anything in `{{ }}` with the relevant values)*
```yaml
tls:
  - hosts:
      - {{the domain you want secure, it has to be one of the dns entries in the cert}}
    secretName: {{name}}
```