#!/usr/bin/env bash
# Install a public root in OS trust and the invoking user's Firefox and Chromium stores.
set -euo pipefail
if [[ $# != 1 ]]; then
  echo "Usage: $0 ROOT.pem" >&2
  exit 2
fi
if [[ $EUID == 0 ]]; then
  echo "Run as your normal desktop user; the OS installation will request sudo." >&2
  exit 1
fi
for program in openssl certutil update-ca-certificates sudo; do
  command -v "$program" >/dev/null || {
    echo "Missing $program. Install openssl, libnss3-tools, ca-certificates, and sudo." >&2
    exit 1
  }
done
ca_file=$(realpath -- "$1")
# Refuse keys and certificate bundles; install only one public root certificate.
[[ $(grep -c -- '-----BEGIN CERTIFICATE-----' "$ca_file") == 1 ]] &&
  ! grep -q -- 'PRIVATE KEY' "$ca_file" || { echo 'Expected one public CA certificate.' >&2; exit 1; }
openssl x509 -in "$ca_file" -noout -checkend 0 >/dev/null
openssl x509 -in "$ca_file" -noout -ext basicConstraints | grep -q 'CA:TRUE'
subject=$(openssl x509 -in "$ca_file" -noout -subject -nameopt RFC2253)
issuer=$(openssl x509 -in "$ca_file" -noout -issuer -nameopt RFC2253)
[[ ${subject#subject=} == "${issuer#issuer=}" ]] || { echo 'Expected a self-signed root CA.' >&2; exit 1; }
openssl verify -check_ss_sig -CAfile "$ca_file" "$ca_file"
openssl x509 -in "$ca_file" -noout -subject -dates -fingerprint -sha256
read -r -p 'Trust this root certificate for this computer and your browsers? [y/N] ' answer
[[ $answer == y || $answer == Y ]] || exit 0
sudo install -m 0644 -- "$ca_file" /usr/local/share/ca-certificates/development-ca.crt
sudo update-ca-certificates
fingerprint=$(openssl x509 -in "$ca_file" -noout -fingerprint -sha256)
nickname="Custom CA ${fingerprint#*=}"
nickname=${nickname//:/}
update_nss() {
  local nss_dir=$1
  mkdir -p -- "$nss_dir"
  if [[ ! -f "$nss_dir/cert9.db" ]]; then
    certutil -N --empty-password -d "sql:$nss_dir"
  fi
  certutil -A -d "sql:$nss_dir" -n "$nickname" -t 'C,,' -i "$ca_file"
  certutil -L -d "sql:$nss_dir" -n "$nickname" >/dev/null
}
if [[ -d "$HOME/.pki/nssdb" ]]; then
  update_nss "$HOME/.pki/nssdb"
else
  update_nss "$HOME/.local/share/pki/nssdb"
fi
if command -v flatpak >/dev/null && flatpak info com.google.Chrome >/dev/null 2>&1; then
  update_nss "$HOME/.var/app/com.google.Chrome/data/pki/nssdb"
fi
# Read registered Firefox profiles, including paths outside the Firefox directory.
# Only update existing databases; do not create profiles for stale registrations.
declare -A firefox_profiles=()
update_firefox_profiles() {
  local profiles_ini=$1 relative profile_path profile_dir
  [[ -f "$profiles_ini" ]] || return 0
  while IFS= read -r -d '' relative && IFS= read -r -d '' profile_path; do
    if [[ "$relative" == 1 ]]; then
      profile_dir="$(dirname -- "$profiles_ini")/$profile_path"
    elif [[ "$relative" == 0 && "$profile_path" == /* ]]; then
      profile_dir=$profile_path
    else
      continue
    fi
    [[ -f "$profile_dir/cert9.db" ]] || continue
    profile_dir=$(realpath -- "$profile_dir")
    [[ ${firefox_profiles[$profile_dir]:-} == installed ]] && continue
    update_nss "$profile_dir"
    firefox_profiles[$profile_dir]=installed
    printf 'Updated Firefox profile: %s\n' "$profile_dir"
  done < <(awk '
    function emit() {
      if (section ~ /^Profile[0-9]+$/ && path != "") {
        printf "%s%c%s%c", relative, 0, path, 0
      }
    }
    { sub(/\r$/, "") }
    /^\[/ {
      emit()
      section = substr($0, 2, length($0) - 2)
      relative = 1
      path = ""
      next
    }
    /^IsRelative=/ { relative = substr($0, index($0, "=") + 1) }
    /^Path=/ { path = substr($0, index($0, "=") + 1) }
    END { emit() }
  ' "$profiles_ini")
}
for firefox_root in \
  "$HOME/.mozilla/firefox" \
  "${XDG_CONFIG_HOME:-$HOME/.config}/mozilla/firefox" \
  "$HOME/snap/firefox/common/.mozilla/firefox" \
  "$HOME/.var/app/org.mozilla.firefox/.mozilla/firefox" \
  "$HOME/.var/app/org.mozilla.firefox/.config/mozilla/firefox"; do
  update_firefox_profiles "$firefox_root/profiles.ini"
done
printf 'Installed. Restart your browsers. Contact your administrator if certificate warnings remain.\n'
