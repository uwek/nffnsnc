# NFFNSNC

> NON FUI, FUI, NON SUM, NON CURO. 
> "I was not, I was, I am not, I do not care."

If I am ever out of action, whether through an accident, illness or something similarly unpleasant, the question arises of how to make important information available to my family.

The simplest answer would be a classic letter deposited in a suitable place. But it would need regular updating, and printing and stuffing envelopes is a bit of a chore.

Easier: maintain a text file on the computer and put only a link and a password in the letter.

NFFNSNC does exactly that: a Markdown file `doc/nffnsnc.md` is maintained, encrypted and deployed to Netlify together with a small decryption frontend. Decryption happens entirely in the family member's browser.

## Workflow

```bash
# once
brew install typst pandoc
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
npm install -g netlify-cli && netlify login && netlify link
# create a passphrase (e.g. 6 random Diceware words), write it to doc/secret.txt and into the letter

# whenever doc/nffnsnc.md changes
./prep.sh --no-deploy             # build + round-trip test, output in .dist/
doc/testserver.sh                 # optional: test locally at http://127.0.0.1:8000
./prep.sh                         # build + test + deploy
```

`prep.sh` aborts if the passphrase is shorter than 20 characters, if `scripts/decrypt.py` does not reproduce the original byte for byte, or if the build folder contains anything other than the seven expected files.

## Files

| File | Purpose |
|---|---|
| `doc/nffnsnc.md` | The actual content (not versioned, see `.gitignore`) |
| `doc/secret.txt` | The passphrase, one line (not versioned) |
| `scripts/nffformat.py` | Container format, password normalisation, encrypt/decrypt |
| `scripts/makeenc.py` / `scripts/decrypt.py` | CLI for encryption/decryption. `decrypt.py` is the fallback without a browser |
| `scripts/build_offline.py` | Builds `nffnsnc-offline.html`, a single file with everything inside |
| `index.html`, `style.css`, `app.js` | Frontend, no external dependencies |
| `prep.sh` | Build, test, deploy |
| `netlify.toml` | Publish folder `.dist`, asset processing off |

## File format `nffnsnc.enc`

```
Magic "NFF1" (4 B) | Version (1 B) | PBKDF2 iterations (4 B, big-endian)
| Salt (16 B) | Nonce (12 B) | AES-256-GCM ciphertext + 16 B tag
```

- Key: PBKDF2-HMAC-SHA256 over the passphrase (UTF-8, NFKC-normalised, trimmed), default 1,000,000 iterations. The iteration count is stored in the file and the frontend reads it from there.
- The 37 header bytes are the associated data of the GCM decryption. Tampering with the header makes decryption fail.
- Salt and nonce are freshly generated with `os.urandom` on every run.

Decrypting without this repo takes a few lines in any language with PBKDF2 and AES-GCM; `scripts/decrypt.py` is the reference.

## What is protected and what is not

**Protected:** The content of the document, as long as the passphrase is strong. `nffnsnc.enc` is publicly downloadable and there is no server-side limit on guessing attempts. An attacker can guess offline. Six random Diceware words (~77 bits) cannot be cracked even with large GPU farms; a short self-chosen password can.

**Not protected:** The existence of the site, the approximate document size, update times (Netlify deploy history) and availability. Old deploys remain reachable under their deploy URL until you delete them in the Netlify UI; keep that in mind when changing the passphrase.

## Availability when it matters

The site is meant to keep working for many years without maintenance. Therefore:

1. **Offline copy:** `.dist/nffnsnc-offline.html` is a single file containing the frontend and the encrypted content. It runs by double-click in any current browser, even without internet. It belongs on a USB stick in the envelope or as an attachment sent to a trusted person. The site offers the file for download.
2. **Second host:** The contents of `.dist/` are plain static hosting. Cloudflare Pages understands `_headers` in the same format; GitHub Pages works too but sets no custom headers. Put both URLs in the letter.
3. **No custom domain as the only access:** Domains expire when nobody pays. The host's subdomain is free and therefore more robust in the event of death.
4. **Mention `scripts/decrypt.py` in the letter:** A technically minded person can reach the data with it even without the frontend.

After every deploy, test "View PDF" and "Download" once in a browser, especially on an iPhone.

## License

Own code under the MIT License, see `LICENSE`.
