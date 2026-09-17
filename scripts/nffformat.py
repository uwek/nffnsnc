"""Gemeinsames Container-Format und Passwort-Behandlung für NFFNSNC.

Layout von nffnsnc.enc (Version 1):

    Magic "NFF1" (4 B) | Version (1 B) | PBKDF2-Iterationen (4 B, big-endian)
    | Salt (16 B) | Nonce (12 B) | AES-256-GCM-Ciphertext inkl. 16 B Auth-Tag

Der 37 Byte lange Header geht als Associated Data (AAD) in AES-GCM ein,
damit er nicht unbemerkt verändert werden kann. Das JavaScript in app.js
liest dieselben Felder.
"""
import os
import struct
import unicodedata

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MAGIC = b"NFF1"
VERSION = 1
DEFAULT_ITERATIONS = 1_000_000
MIN_ITERATIONS = 100_000
MAX_ITERATIONS = 50_000_000
SALT_LEN = 16
NONCE_LEN = 12
TAG_LEN = 16
HEADER_LEN = 4 + 1 + 4 + SALT_LEN + NONCE_LEN  # 37
MIN_PASSWORD_LEN = 20


class FormatError(ValueError):
    pass


def normalize_password(raw: str) -> str:
    """Einheitliche Normalisierung (identisch zu app.js): NFKC + trim."""
    return unicodedata.normalize("NFKC", raw).strip()


def read_password_file(path: str) -> str:
    # utf-8-sig entfernt ein evtl. von Editoren geschriebenes BOM.
    with open(path, "r", encoding="utf-8-sig") as f:
        password = normalize_password(f.read())
    if not password:
        raise ValueError(f"Die Passwort-Datei {path} ist leer.")
    if len(password) < MIN_PASSWORD_LEN and os.environ.get("NFF_ALLOW_WEAK") != "1":
        raise ValueError(
            f"Passwort ist nur {len(password)} Zeichen lang (Minimum {MIN_PASSWORD_LEN}). "
            "Die .enc-Datei ist öffentlich, nur die Passphrase schützt den Inhalt. "
            "Empfohlen: mindestens 6 zufällige Diceware-Wörter in doc/secret.txt. "
            "(Nur zum Testen: NFF_ALLOW_WEAK=1 setzen.)"
        )
    return password


def _derive_key(password: str, salt: bytes, iterations: int) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
    return kdf.derive(password.encode("utf-8"))


def encrypt(data: bytes, password: str, iterations: int = DEFAULT_ITERATIONS) -> bytes:
    if not MIN_ITERATIONS <= iterations <= MAX_ITERATIONS:
        raise ValueError(f"Iterationen außerhalb von {MIN_ITERATIONS}..{MAX_ITERATIONS}")
    salt = os.urandom(SALT_LEN)
    nonce = os.urandom(NONCE_LEN)
    header = MAGIC + bytes([VERSION]) + struct.pack(">I", iterations) + salt + nonce
    assert len(header) == HEADER_LEN
    key = _derive_key(password, salt, iterations)
    ciphertext = AESGCM(key).encrypt(nonce, data, header)
    return header + ciphertext


def parse_header(blob: bytes):
    if len(blob) < HEADER_LEN + TAG_LEN:
        raise FormatError("Datei zu kurz oder beschädigt.")
    if blob[:4] != MAGIC:
        raise FormatError("Unbekanntes Dateiformat (Magic fehlt).")
    version = blob[4]
    if version != VERSION:
        raise FormatError(f"Nicht unterstützte Formatversion {version}.")
    (iterations,) = struct.unpack(">I", blob[5:9])
    if not MIN_ITERATIONS <= iterations <= MAX_ITERATIONS:
        raise FormatError(f"Unplausible Iterationszahl {iterations} im Header.")
    salt = blob[9:9 + SALT_LEN]
    nonce = blob[9 + SALT_LEN:HEADER_LEN]
    return blob[:HEADER_LEN], iterations, salt, nonce, blob[HEADER_LEN:]


def decrypt(blob: bytes, password: str) -> bytes:
    header, iterations, salt, nonce, ciphertext = parse_header(blob)
    key = _derive_key(password, salt, iterations)
    return AESGCM(key).decrypt(nonce, ciphertext, header)
