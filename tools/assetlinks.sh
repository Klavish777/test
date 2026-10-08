#!/usr/bin/env bash
# Считает отпечатки сертификата сборки, нужные для OAuth на Android:
#   SHA-1  → поле «SHA-1 release/development» в Google Cloud Console (OAuth-клиент типа Android)
#   SHA-256 (base64url, без «=») → certificate_sha256 в docs/.well-known/assetlinks.json (App Link)
#
# Использование:
#   tools/assetlinks.sh                                  # отладочный ключ ~/.android/debug.keystore
#   tools/assetlinks.sh path/to/release.keystore alias   # свой ключ
set -euo pipefail

KS="${1:-$HOME/.android/debug.keystore}"
ALIAS="${2:-androiddebugkey}"
PASS="${3:-android}"

[[ -f "$KS" ]] || { echo "нет кейстора $KS — соберите хотя бы один debug APK, Android Studio создаст ключ сам" >&2; exit 1; }

echo "кейстор: $KS"
echo "пакет (debug): work.day.app.debug"
echo
printf 'SHA-1 (для Google Cloud Console):\n  '
keytool -list -v -keystore "$KS" -alias "$ALIAS" -storepass "$PASS" 2>/dev/null \
  | awk -F': ' '/SHA1:/{gsub(/ /,"",$2); print $2}'

SHA=$(keytool -exportcert -keystore "$KS" -alias "$ALIAS" -storepass "$PASS" 2>/dev/null \
  | openssl dgst -sha256 -binary \
  | openssl enc -base64 | tr '+/' '-_' | tr -d '=')

printf '\nSHA-256 base64url (для assetlinks.json):\n  %s\n' "$SHA"
printf '\nПодставить в файл: '; cat <<EOT
python3 - <<'PY'
import json, pathlib
p = pathlib.Path("docs/.well-known/assetlinks.json")
data = json.loads(p.read_text())
data[0]["target"]["certificate_sha256"] = ["$SHA"]
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
PY
EOT
