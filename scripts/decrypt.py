#!/usr/bin/env python3
"""Entschlüsselt nffnsnc.enc ohne Browser.

Standalone-Fallback für den Fall, dass das Web-Frontend nicht (mehr) läuft.
Benötigt nur Python 3 und das Paket `cryptography` (pip install cryptography).

    python3 scripts/decrypt.py nffnsnc.enc ausgabe.pdf            # fragt Passphrase ab
    python3 scripts/decrypt.py nffnsnc.enc ausgabe.pdf --password-file doc/secret.txt
"""
import argparse
import getpass
import sys

import nffformat


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input", nargs="?", default="nffnsnc.enc")
    p.add_argument("output", nargs="?", default="nffnsnc-entschluesselt.pdf")
    p.add_argument("--password-file", help="Passphrase aus Datei statt interaktiv")
    args = p.parse_args()

    if args.password_file:
        password = nffformat.read_password_file(args.password_file)
    else:
        password = nffformat.normalize_password(getpass.getpass("Passphrase: "))

    with open(args.input, "rb") as f:
        blob = f.read()
    try:
        data = nffformat.decrypt(blob, password)
    except nffformat.FormatError as e:
        sys.exit(f"Fehler: {e}")
    except Exception:
        sys.exit("Entschlüsselung fehlgeschlagen: Passphrase falsch oder Datei beschädigt.")
    with open(args.output, "wb") as f:
        f.write(data)
    print(f"Entschlüsselt nach {args.output} ({len(data)} Bytes)")


if __name__ == "__main__":
    main()
