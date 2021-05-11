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

