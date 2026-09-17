#!/usr/bin/env python3
"""Verschlüsselt eine Datei in das NFFNSNC-Containerformat (siehe nffformat.py)."""
import argparse

import nffformat


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", nargs="?", default="doc/nffnsnc.pdf")
    p.add_argument("output", nargs="?", default="nffnsnc.enc")
    p.add_argument("--password-file", default="doc/secret.txt")
    p.add_argument("--iterations", type=int, default=nffformat.DEFAULT_ITERATIONS)
    args = p.parse_args()

    password = nffformat.read_password_file(args.password_file)
    with open(args.input, "rb") as f:
        data = f.read()
    blob = nffformat.encrypt(data, password, args.iterations)
    with open(args.output, "wb") as f:
        f.write(blob)
    print(f"Erfolgreich verschlüsselt: {args.output} "
          f"({len(blob)} Bytes, PBKDF2 {args.iterations} Iterationen)")


if __name__ == "__main__":
    main()
