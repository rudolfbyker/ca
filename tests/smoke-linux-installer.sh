#!/usr/bin/env bash
# Run as root inside a disposable Debian container with the repository at /input (read-only).
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends openssl ca-certificates libnss3-tools sudo >/dev/null
useradd --create-home --shell /bin/bash tester
printf 'tester ALL=(ALL) NOPASSWD: ALL\n' >/etc/sudoers.d/tester
openssl req -x509 -newkey rsa:2048 -nodes -days 2 -subj '/CN=Installer test CA' \
  -addext basicConstraints=critical,CA:TRUE -addext keyUsage=critical,keyCertSign,cRLSign \
  -keyout /tmp/test-ca.key -out /tmp/test-ca.pem 2>/dev/null
runuser -u tester -- bash <<'USER_TEST'
set -euo pipefail
roots=(
  "$HOME/.mozilla/firefox"
  "$HOME/.config/mozilla/firefox"
  "$HOME/snap/firefox/common/.mozilla/firefox"
  "$HOME/.var/app/org.mozilla.firefox/.mozilla/firefox"
  "$HOME/.var/app/org.mozilla.firefox/.config/mozilla/firefox"
)
for root in "${roots[@]}"; do
  mkdir -p "$root/profile with spaces" "$root/unused-backup"
  certutil -N --empty-password -d "sql:$root/profile with spaces"
  certutil -N --empty-password -d "sql:$root/unused-backup"
  printf '[Profile0]\nIsRelative=1\nPath=profile with spaces\n\n[Profile1]\nIsRelative=1\nPath=missing-profile\n' >"$root/profiles.ini"
done
mkdir -p "$HOME/external profile"
certutil -N --empty-password -d "sql:$HOME/external profile"
printf '\n[Profile2]\nIsRelative=0\nPath=%s\n\n[Profile3]\nIsRelative=1\nPath=profile with spaces\n' \
  "$HOME/external profile" >>"${roots[0]}/profiles.ini"
# Firefox may write CRLF configuration files.
sed -i 's/$/\r/' "${roots[2]}/profiles.ini"
for attempt in 1 2; do
  printf 'y\n' | bash /input/install-ca-linux.sh /tmp/test-ca.pem >"/tmp/install-$attempt.log" 2>&1 || {
    cat "/tmp/install-$attempt.log"; exit 1;
  }
  test "$(grep -c '^Updated Firefox profile:' "/tmp/install-$attempt.log")" = 6
done
fingerprint=$(openssl x509 -in /tmp/test-ca.pem -noout -fingerprint -sha256)
nickname="Custom CA ${fingerprint#*=}"
nickname=${nickname//:/}
for root in "${roots[@]}"; do
  certutil -L -d "sql:$root/profile with spaces" -n "$nickname" >/dev/null
  test ! -e "$root/missing-profile"
  if certutil -L -d "sql:$root/unused-backup" -n "$nickname" >/dev/null 2>&1; then
    echo 'Imported into an unregistered backup database' >&2; exit 1
  fi
done
certutil -L -d "sql:$HOME/external profile" -n "$nickname" >/dev/null
certutil -L -a -d "sql:$HOME/external profile" -n "$nickname" | openssl x509 -outform DER >/tmp/imported.der
openssl x509 -in /tmp/test-ca.pem -outform DER >/tmp/expected.der
cmp /tmp/imported.der /tmp/expected.der
USER_TEST
openssl verify /tmp/test-ca.pem
printf 'PASS: OS trust, Firefox native/XDG/Snap/Flatpak/external profiles, spaces, CRLF, deduplication, stale registrations, unregistered backups, repeat installation, exact certificate readback\n'
