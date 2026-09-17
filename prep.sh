#!/usr/bin/env bash
#
# Baut und deployt NFFNSNC.
#
#   ./prep.sh              Build + Round-Trip-Test + Deploy auf Netlify
#   ./prep.sh --no-deploy  nur Build + Test (Ergebnis in .dist/)
#
## Einmalige Vorbereitung
# brew install typst pandoc
# python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
# npm install -g netlify-cli && netlify login && netlify link
# Passphrase erzeugen (z. B. 6 zufällige Diceware-Wörter), nach doc/secret.txt schreiben und in den Brief übernehmen

set -euo pipefail
cd "$(dirname "$0")"

DEPLOY=1
[[ "${1:-}" == "--no-deploy" ]] && DEPLOY=0

BUILD_DIR=".dist"
SRC_MD="doc/nffnsnc.md"
SRC_PDF="doc/nffnsnc.pdf"
SECRET="doc/secret.txt"
ENC="nffnsnc.enc"
EXPECTED_FILES="_headers app.js index.html nffnsnc-offline.html nffnsnc.enc robots.txt style.css"

# shellcheck disable=SC1091
source .venv/bin/activate

echo "=== 1. PDF aus Markdown erzeugen ==="
pandoc "$SRC_MD" -o "$SRC_PDF" --pdf-engine=typst

echo "=== 2. Verschlüsseln ==="
python3 scripts/makeenc.py "$SRC_PDF" "$ENC" --password-file "$SECRET"

echo "=== 3. Round-Trip-Test (scripts/decrypt.py muss das Original byteweise reproduzieren) ==="
TMP_PDF="$(mktemp -t nffnsnc-roundtrip).pdf"
trap 'rm -f "$TMP_PDF"' EXIT
python3 scripts/decrypt.py "$ENC" "$TMP_PDF" --password-file "$SECRET" > /dev/null
cmp "$SRC_PDF" "$TMP_PDF"
echo "Round-Trip OK"

echo "=== 4. Build-Verzeichnis füllen ==="
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
cp "$ENC" index.html app.js style.css "$BUILD_DIR/"
printf 'User-agent: *\nDisallow: /\n' > "$BUILD_DIR/robots.txt"
python3 scripts/build_offline.py --enc "$ENC" --out "$BUILD_DIR/nffnsnc-offline.html"

# Header für Netlify (und Cloudflare Pages, gleiches Format).
cat << 'HDR' > "$BUILD_DIR/_headers"
/*
  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; object-src 'self' blob:; frame-src 'self' blob:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'
  Strict-Transport-Security: max-age=63072000; includeSubDomains
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Referrer-Policy: no-referrer
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  Cross-Origin-Opener-Policy: same-origin
  Cache-Control: no-cache

/nffnsnc-offline.html
  Content-Disposition: attachment; filename="nffnsnc-offline.html"
HDR

echo "=== 5. Build-Verzeichnis prüfen (nur erwartete Dateien, keine Klartexte) ==="
ACTUAL_FILES="$(cd "$BUILD_DIR" && ls -A | sort | tr '\n' ' ' | sed 's/ $//')"
if [[ "$ACTUAL_FILES" != "$EXPECTED_FILES" ]]; then
  echo "FEHLER: Unerwarteter Inhalt in $BUILD_DIR:" >&2
  echo "  erwartet: $EXPECTED_FILES" >&2
  echo "  gefunden: $ACTUAL_FILES" >&2
  exit 1
fi
if grep -rqF "$(head -c 12 "$SRC_MD")" "$BUILD_DIR" 2>/dev/null; then
  echo "FEHLER: Klartext aus $SRC_MD im Build-Verzeichnis gefunden!" >&2
  exit 1
fi
echo "Build OK: $ACTUAL_FILES"

if [[ "$DEPLOY" -eq 0 ]]; then
  echo "=== --no-deploy: fertig, kein Upload. Lokal testen mit doc/testserver.sh ==="
  exit 0
fi

echo "=== 6. Deployment auf Netlify ==="
# --dir stellt sicher, dass NUR .dist hochgeladen wird (nie doc/secret.txt oder das Klartext-PDF).
DEPLOY_JSON="$(netlify deploy --prod --dir="$BUILD_DIR" --json)"
SITE_URL="$(printf '%s' "$DEPLOY_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("url",""))')"

if [[ -n "$SITE_URL" ]]; then
  echo "=== 7. Erreichbarkeit prüfen ==="
  LOCAL_SIZE="$(stat -f %z "$ENC" 2>/dev/null || stat -c %s "$ENC")"
  REMOTE_SIZE="$(curl -sSIL "$SITE_URL/$ENC" | tr -d '\r' | awk 'tolower($1)=="content-length:"{s=$2} END{print s}')"
  if [[ "$REMOTE_SIZE" == "$LOCAL_SIZE" ]]; then
    echo "OK: $SITE_URL/$ENC ($REMOTE_SIZE Bytes)"
  else
    echo "WARNUNG: Remote-Größe ($REMOTE_SIZE) weicht von lokal ($LOCAL_SIZE) ab. Bitte manuell prüfen." >&2
  fi
  echo "Bitte einmal 'PDF anzeigen' und 'Herunterladen' im Browser testen: $SITE_URL"
fi

echo "=== Erfolgreich auf Netlify deployed! ==="
echo "Hinweis: Alte Deploys bleiben unter ihrer Deploy-URL abrufbar. Bei Passphrase-Wechsel in der Netlify-UI löschen."
