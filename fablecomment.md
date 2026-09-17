# Review NFFNSNC – Verbesserungsvorschläge

## Umsetzungsstatus (2026-09-17)

Die Punkte 1–7 der Kurzfassung sind umgesetzt. Was noch **manuell** zu tun ist:

- [ ] Neue Passphrase aus `doc/secret.txt` in den Brief übernehmen (6 Diceware-Wörter).
- [ ] `./prep.sh` ausführen, damit das neue Dateiformat und die neue Passphrase online gehen. **Die aktuell deployte Version verwendet noch das alte Format und das alte Passwort.**
- [ ] Nach dem Deploy „PDF anzeigen“ und „Herunterladen“ im Browser testen, besonders auf einem iPhone (Popup-Handling, CSP).
- [ ] Alte Deploys in der Netlify-UI löschen (enthalten noch das alte Format und die alte Passphrase).
- [ ] `.dist/nffnsnc-offline.html` auf einen USB-Stick / an eine Vertrauensperson.
- [ ] Optional: zweiten Host (Cloudflare Pages / GitHub Pages) mit `.dist/` einrichten, URL in den Brief.

| Punkt | Umsetzung |
|---|---|
| 1 Passphrase | `nffformat.read_password_file` lehnt Passwörter unter 20 Zeichen ab; `doc/secret.txt` neu erzeugt (6 Diceware-Wörter). Generator und Wortliste wurden nachträglich aus dem Repo entfernt |
| 2 Testserver | `doc/testserver.sh` bindet an `127.0.0.1` und serviert nur `.dist` |
| 3 Netlify | `netlify.toml` im Root: `publish = ".dist"`, `skip_processing = true` |
| 4 KDF/Format | 1.000.000 Iterationen; Header `NFF1 | Version | Iterationen | Salt | Nonce` als AAD; `app.js` liest Parameter aus der Datei |
| 5 Normalisierung | NFKC + trim in `scripts/nffformat.py` und `app.js`; `utf-8-sig` beim Lesen der Passwortdatei |
| 6 Frontend/HTTP | CSP, HSTS, COOP, Permissions-Policy in `_headers`; keine Inline-Handler; `<form>` mit Enter; „Anzeigen“-Toggle; Secure-Context-Prüfung; Fenster wird synchron vor dem `await` geöffnet; Blob-URLs werden bei `pagehide` freigegeben |
| 7 Robustheit | `scripts/decrypt.py` als Fallback; `prep.sh` macht Round-Trip-Test (`cmp`) und prüft den `.dist`-Inhalt; `scripts/build_offline.py` erzeugt Single-File-Kopie; `--no-deploy`-Modus; README mit Format, Threat Model, Zweithost |

Verifiziert: Python-Verschlüsselung → Entschlüsselung mit Node-WebCrypto nach der Logik aus `app.js` liefert byteidentisches PDF; Header-Manipulation und falsche Passphrase werden erkannt; NFC/NFD und BOM werden normalisiert.

Korrektur zu Abschnitt 3.4/4.2 unten: `file://` gilt in Chrome, Firefox und Safari als sicherer Kontext, `crypto.subtle` ist dort verfügbar. Die Offline-Kopie funktioniert per Doppelklick ohne Server. Problematisch ist nur `http://` außerhalb von localhost.

---

Stand: 2026-09-17. Geprüft wurden `scripts/makeenc.py`, `app.js`, `index.html`, `prep.sh`, `.gitignore`, `.dist/`, `.netlify/netlify.toml`, `doc/testserver.sh` sowie die Struktur von `doc/` und `nffnsnc.enc`.

**Gesamteindruck:** Das Grundkonzept ist solide und angemessen minimal: AES-256-GCM (authentifiziert), zufälliger Salt und Nonce pro Lauf, PBKDF2 zur Schlüsselableitung, keine externen JS-Abhängigkeiten, Entschlüsselung ausschließlich clientseitig per WebCrypto. Python- und JS-Seite passen zueinander (Layout Salt 16 | Nonce 12 | Ciphertext+Tag). Die Punkte unten sind nach Dringlichkeit sortiert.

---

## 1. Kritisch

### 1.1 Passwortstärke ist die einzige Verteidigungslinie – und `doc/secret.txt` war nur ein kurzer Platzhalter
`nffnsnc.enc` ist öffentlich abrufbar. Es gibt keinen Server, der Fehlversuche limitieren könnte. Ein Angreifer kann die Datei herunterladen und **offline** mit GPUs raten. PBKDF2 mit 200.000 Iterationen bremst das nur linear: Größenordnung 10⁴–10⁵ Versuche pro Sekunde pro moderner GPU.

| Passwort | Suchraum | Offline-Dauer (1 GPU, grob) |
|---|---|---|
| 3 Zeichen (Platzhalter zum Zeitpunkt des Reviews) | ~10⁵ | Sekunden |
| 8 Zeichen zufällig alnum | ~2·10¹⁴ | Jahrzehnte |
| 6 Diceware-Wörter (~77 Bit) | ~10²³ | praktisch unmöglich |

Das war nur ein Testwert. Trotzdem: Das Produktivpasswort sollte eine **Passphrase aus ≥ 6 zufälligen Wörtern** (Diceware, deutsche Wortliste) sein. Das ist für Angehörige aus einem Brief abtippbar, was bei 20 zufälligen Sonderzeichen nicht gilt. Der README-Satz „anspruchsvoll verschlüsselt“ stimmt nur mit einem starken Passwort.

### 1.2 Testserver exponiert Klartext-Geheimnisse im lokalen Netz
`doc/testserver.sh` startet `python3 -m http.server` im Projektroot, standardmäßig auf `0.0.0.0:8000`. Damit sind `doc/secret.txt`, `doc/nffnsnc.pdf` und `doc/nffnsnc.md` für jeden im WLAN abrufbar.

```bash
#!/usr/bin/env bash
cd "$(dirname "$0")/.."
python3 -m http.server --bind 127.0.0.1 --directory .dist 8000
```

### 1.3 Netlify-Standard-Publish-Verzeichnis ist das gesamte Projekt
`.netlify/netlify.toml` enthält als `publish` den absoluten Pfad des Projektverzeichnisses. Wer einmal `netlify deploy --prod` ohne `--dir` tippt, lädt potenziell `doc/secret.txt` und das Klartext-PDF hoch (ob die CLI dabei `.gitignore` beachtet, sollte man nicht als Sicherheitsgarantie annehmen). Abhilfe: eine eigene `netlify.toml` im Projektroot anlegen, die den sicheren Default festschreibt und gleichzeitig Netlifys Asset-Optimierung abschaltet, damit `app.js` nie serverseitig umgeschrieben wird:

```toml
[build]
  publish = ".dist"

[build.processing]
  skip_processing = true
```

---

## 2. Wichtig (Krypto & Format)

### 2.1 KDF-Parameter erhöhen bzw. KDF wechseln
- OWASP empfiehlt für PBKDF2-HMAC-SHA256 aktuell **600.000** Iterationen; 200.000 ist unterhalb dessen. Auf einem Smartphone dauern 600k–1M Iterationen in WebCrypto ca. 1–3 s, das ist für diesen Anwendungsfall völlig akzeptabel.
- Besser wäre ein speicherhartes KDF (**Argon2id** oder scrypt), das GPU-Angriffe massiv verteuert. WebCrypto kann das nicht nativ; man bräuchte eine WASM-Bibliothek (z. B. `argon2-browser`, `libsodium-wrappers`). Abwägung: mehr Sicherheit gegen Brute-Force vs. eine zusätzliche Abhängigkeit in einem Frontend, das 20+ Jahre ohne Wartung laufen soll. **Empfehlung:** bei PBKDF2 bleiben, Iterationen auf ≥ 600.000 (besser 1.000.000) setzen, und die Sicherheit über die Passphrase-Länge holen (siehe 1.1).

### 2.2 Dateiformat mit Header und Versionsbyte versehen
Aktuell sind Iterationszahl, Hash und Algorithmus im JS hart kodiert. Sobald man Parameter ändert, sind alte `.enc`-Dateien (z. B. auf einem USB-Stick im Briefumschlag) nicht mehr lesbar. Vorschlag:

```
Magic "NFF1" (4 B) | Version (1 B) | Iterationen (4 B, big-endian) | Salt (16 B) | Nonce (12 B) | Ciphertext+Tag
```

Der Header sollte zusätzlich als **Associated Data (AAD)** in AES-GCM eingehen, damit niemand die Iterationszahl im Header manipulieren kann, ohne dass die Entschlüsselung fehlschlägt. Das JS liest die Parameter dann aus der Datei statt aus Konstanten.

### 2.3 Passwort-Normalisierung auf beiden Seiten
Angehörige tippen das Passwort auf unbekannten Geräten ab. Stolperfallen:
- **Unicode-Normalisierung:** „ü“ kann als NFC oder NFD kodiert sein (macOS-Dateien vs. iOS-Tastatur). Beide Seiten sollten `NFKC` anwenden: Python `unicodedata.normalize('NFKC', pw)`, JS `password.normalize('NFKC')`.
- **BOM:** Manche Editoren schreiben ein UTF-8-BOM. `open(..., encoding='utf-8')` behält es bei und es wird Teil des Passworts. `encoding='utf-8-sig'` verwenden.
- **Whitespace:** Python strippt nur `\r\n`, JS gar nicht. Konsistent auf beiden Seiten `strip()`/`trim()` anwenden (Leerzeichen am Rand sind im Brief ohnehin unsichtbar).
- Am einfachsten: Passphrase ohne Umlaute und Sonderzeichen wählen (Diceware-Liste entsprechend filtern).

### 2.4 Passwort nicht als Klartextdatei halten
`doc/secret.txt`, `doc/nffnsnc.md` und `doc/nffnsnc.pdf` liegen im Klartext auf der Platte (FileVault vorausgesetzt, aber Backups, Cloud-Sync, Time Machine etc. sind Wege nach draußen). Optionen:
- Passwort per `getpass.getpass()` interaktiv abfragen oder aus dem macOS-Schlüsselbund lesen (`security find-generic-password -s nffnsnc -w`).
- Das Zwischenprodukt `doc/nffnsnc.pdf` nach dem Verschlüsseln löschen bzw. in ein `tempfile` schreiben.
- Die Quelle `nffnsnc.md` bewusst versionieren: z. B. verschlüsselt per `age`/`git-crypt`, damit es eine Historie und ein Backup gibt. Aktuell ist die `.md` die einzige Kopie und wird durch `.gitignore` von jeder Versionierung ausgeschlossen.

### 2.5 Round-Trip-Test vor dem Deploy
`prep.sh` deployt direkt nach dem Verschlüsseln. Ein Bug (falscher Salt-Offset, geändertes Format) fiele erst im Ernstfall auf. Ein `decrypt.py` im Repo, das `prep.sh` vor Schritt 4 aufruft und das Ergebnis byteweise mit `doc/nffnsnc.pdf` vergleicht, kostet 20 Zeilen und schließt diese Lücke. Zusätzlich prüfen, dass `.dist` **nur** die fünf erwarteten Dateien enthält.

---

## 3. Wichtig (Web-Frontend & HTTP)

### 3.1 Content-Security-Policy und weitere Header
`_headers` ist ein guter Anfang. Ergänzen:

```
/*
  Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'
  Strict-Transport-Security: max-age=63072000; includeSubDomains
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  Cross-Origin-Opener-Policy: same-origin
  X-Content-Type-Options: nosniff
  Referrer-Policy: no-referrer
```

Voraussetzung: die Inline-Handler `onclick="viewPdf()"` in `index.html` durch `addEventListener` in `app.js` ersetzen, sonst blockiert die CSP sie. Das Inline-`<style>` kann bleiben (`'unsafe-inline'` bei `style-src` ist unkritisch) oder in eine `style.css` wandern.

### 3.2 `window.open` nach `await` wird von Popup-Blockern geblockt
In `viewPdf()` wird `window.open` erst nach der asynchronen Entschlüsselung aufgerufen. Safari (insbesondere iOS) wertet das nicht mehr als User-Geste und blockiert das Fenster. Genau die Angehörigen mit iPhone trifft das. Optionen:
- Fenster **synchron** im Click-Handler öffnen (`const w = window.open('', '_blank')`) und nach der Entschlüsselung `w.location = fileURL` setzen.
- Oder das PDF in einem `<iframe>`/`<embed>` auf derselben Seite anzeigen.
- Der Download-Pfad (`a.click()`) funktioniert robuster und sollte im Brief als primärer Weg genannt werden.

Nebenbei: die Blob-URL in `viewPdf()` wird nie mit `revokeObjectURL` freigegeben (nur kleines Leck, aber inkonsistent zu `downloadPdf()`).

### 3.3 Bedienbarkeit für Nicht-Techniker
- **Enter-Taste** löst aktuell nichts aus. Ein `<form>` mit `submit`-Handler beheben das.
- **„Passwort anzeigen“-Toggle** ist bei langen Passphrasen wichtig, die abgetippt werden. Beim Umschalten auf `type="text"` `autocapitalize="off" autocorrect="off" spellcheck="false"` setzen, sonst macht iOS aus dem ersten Buchstaben einen Großbuchstaben.
- `autocomplete="current-password"` auf dem Input, damit Passwortmanager es speichern können.
- Statusmeldung während der Schlüsselableitung („Das kann einige Sekunden dauern…“), sonst wirkt die Seite bei 1M Iterationen auf alten Handys eingefroren.
- Fehlertext konkreter machen: „Falsches Passwort“ ist bei GCM-Tag-Fehler die mit Abstand wahrscheinlichste Ursache. Hinweis auf Groß/Klein und Leerzeichen anzeigen.

### 3.4 `crypto.subtle` nur im Secure Context
`window.crypto.webkitSubtle` ist Legacy und kann entfallen. Wichtiger: wenn jemand `index.html` per `file://` öffnet oder über plain HTTP von einem Nicht-Localhost, ist `crypto.subtle` `undefined` und die Seite stirbt mit einem kryptischen TypeError. Am Anfang prüfen und eine verständliche Meldung anzeigen („Seite muss über https:// geöffnet werden“).

---

## 4. Empfehlenswert (Verfügbarkeit & Langzeit-Szenario)

Das Ziel des Projekts ist, dass es in 10–30 Jahren **ohne dich** noch funktioniert. Dafür sind die folgenden Punkte mindestens so wichtig wie die Krypto:

### 4.1 Alte Netlify-Deploys bleiben abrufbar
Jeder Deploy ist dauerhaft unter `https://<deploy-id>--<site>.netlify.app` erreichbar. Wenn du je den Inhalt bereinigst oder das Passwort wechselst, bleibt die alte `.enc` mit dem alten Passwort online. Alte Deploys regelmäßig in der Netlify-UI löschen, oder im Brief nur ein Passwort für die jeweils aktuelle Version kommunizieren und das im Kopf behalten.

### 4.2 Hosting-Abhängigkeit reduzieren
„Netlify wird lange existieren“ ist eine Annahme. Kostenlose Sites werden bei Inaktivität, Account-Problemen oder Preismodell-Änderungen gelöscht. Empfehlungen:
- **Zweiter Host** mit identischem Build (GitHub Pages, Cloudflare Pages). Beide URLs in den Brief.
- **Single-File-Build:** ein `index.html`, in dem `app.js` inline und `nffnsnc.enc` als Base64 eingebettet sind. Diese eine Datei kann auf einen USB-Stick in den Briefumschlag, als E-Mail-Anhang an Vertrauenspersonen usw. Sie funktioniert überall, wo ein Browser läuft (Achtung: dann `crypto.subtle` per `file://` – siehe 3.4; für die Offline-Kopie daher entweder einen minimalen JS-Fallback für AES-GCM einbetten oder in der Anleitung `python3 -m http.server` beschreiben).
- **Eigene Domain vermeiden** oder zumindest nicht als einzigen Zugang: Domains laufen aus, wenn niemand mehr zahlt. Die Netlify-Subdomain ist im Sterbefall-Szenario paradoxerweise robuster.

### 4.3 Standalone-Entschlüsselung dokumentieren
Ein `decrypt.py` (Gegenstück zu `makeenc.py`) ins Repo und ins Deploy legen, plus eine Beschreibung des Dateiformats im README. Dann kann auch eine technisch versierte Vertrauensperson ohne funktionierendes Frontend an die Daten. Die Krypto-Primitiven (PBKDF2-SHA256, AES-256-GCM) sind in jeder Sprache verfügbar, das Format ist trivial.

### 4.4 Mehrere Empfänger mit eigenen Passwörtern (optional)
Statt das Dokument direkt mit dem Passwort zu verschlüsseln: einen zufälligen Content-Key erzeugen, damit das PDF verschlüsseln, und den Content-Key **mehrfach** mit je einem Passwort pro Empfänger einwickeln (Key Wrapping). Vorteile: jede Person bekommt ein eigenes Passwort, ein Passwort kann zurückgezogen werden, ohne die anderen neu zu verteilen. Nachteil: mehr Komplexität im Format. Lohnt sich nur, wenn mehr als zwei Personen Zugang bekommen sollen.

### 4.5 Metadaten
Bewusst akzeptieren, aber wissen: Die Dateigröße von `nffnsnc.enc` verrät die ungefähre Dokumentlänge, Netlifys Deploy-Historie verrät Aktualisierungszeitpunkte, und die Startseite verrät jedem Besucher, dass hier ein „Notfall-Dokument“ liegt. Wenn das stört: Padding auf feste Größe (z. B. 64 KiB) und neutralerer Seitentitel.

---

## 5. Kleinere Punkte & Hygiene

- **Kein Git-Repo:** Das Verzeichnis ist nicht initialisiert. `git init` lohnt sich für `app.js`, `index.html`, `makeenc.py`, `prep.sh`; die `.gitignore` ist schon passend. `.DS_Store` und `.venv/` explizit in `.gitignore` aufnehmen (`.venv` schützt sich zwar selbst, aber explizit ist besser).
- **Abhängigkeiten pinnen:** `requirements.txt` mit `cryptography==50.0.1`, damit der Build reproduzierbar bleibt.
- **`prep.sh`:** `set -euo pipefail` statt nur `set -e`. Der Kommentar erwähnt `password.txt`, die Datei heißt `secret.txt`. Nach dem Deploy die deployte URL ausgeben und direkt einen `curl`-Check machen, dass `nffnsnc.enc` mit erwarteter Größe abrufbar ist.
- **Funktionsname:** `encrypt_pdf` ist auf PDF festgelegt, tut aber Generisches. `encrypt_file` und Pfade als CLI-Argumente (`argparse`) machen das Skript wiederverwendbar (z. B. für ein zweites Dokument).
- **Passwortfeld nach Erfolg leeren** und Referenzen auf den entschlüsselten Buffer nicht länger als nötig halten. Niedrige Priorität, aber kostenlos.
- **`Cache-Control`:** Netlify liefert bereits `max-age=0, must-revalidate`. Wenn du je auf einen anderen Host wechselst, sicherstellen, dass `nffnsnc.enc` nicht lange gecacht wird, sonst sehen Angehörige eine veraltete Version.
- **Threat Model ins README:** Zwei Sätze, was geschützt ist (Inhalt, solange Passphrase stark) und was nicht (Existenz, Größe, Update-Zeitpunkte, Verfügbarkeit hängt am Hoster). Das hilft auch dir in fünf Jahren beim Entscheiden, ob eine Änderung sicher ist.

---

## Kurzfassung der Prioritäten

1. Starke Passphrase (≥ 6 Diceware-Wörter), `secret.txt` ist aktuell nur ein Platzhalter.
2. `testserver.sh` auf `127.0.0.1` und `.dist` beschränken.
3. `netlify.toml` im Root mit `publish = ".dist"` anlegen.
4. PBKDF2-Iterationen auf ≥ 600.000, Dateiformat mit Header/Version/Iterationen und AAD.
5. Passwort-Normalisierung (NFKC, `utf-8-sig`, trim) auf beiden Seiten.
6. CSP + weitere Header, Inline-Handler entfernen, `window.open`-Problem auf iOS beheben, Enter-Taste und „Passwort anzeigen“.
7. Round-Trip-Test und `decrypt.py`, zweiter Host, Single-File-Offline-Kopie für den Briefumschlag.
