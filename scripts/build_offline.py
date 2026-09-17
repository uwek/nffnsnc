#!/usr/bin/env python3
"""Baut eine einzelne, selbständige HTML-Datei (Frontend + eingebettete .enc).

Die Datei funktioniert ohne Server direkt per Doppelklick (file://) in
Chrome, Firefox und Safari, da file:// als sicherer Kontext gilt und
WebCrypto verfügbar ist. Gedacht für USB-Stick, E-Mail-Anhang, Briefumschlag.
"""
import argparse
import base64


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--html", default="index.html")
    p.add_argument("--js", default="app.js")
    p.add_argument("--css", default="style.css")
    p.add_argument("--enc", default="nffnsnc.enc")
    p.add_argument("--out", default=".dist/nffnsnc-offline.html")
    args = p.parse_args()

    html = open(args.html, encoding="utf-8").read()
    js = open(args.js, encoding="utf-8").read()
    css = open(args.css, encoding="utf-8").read()
    enc_b64 = base64.b64encode(open(args.enc, "rb").read()).decode("ascii")

    for s in (js, css):
        if "</script" in s.lower() or "</style" in s.lower():
            raise SystemExit("Inline-Einbettung nicht möglich: schließendes Tag im Quelltext.")

    css_tag = '<link rel="stylesheet" href="style.css">'
    js_tag = '<script src="app.js"></script>'
    if css_tag not in html or js_tag not in html:
        raise SystemExit("index.html enthält nicht die erwarteten style.css/app.js-Tags.")

    html = html.replace(css_tag, f"<style>\n{css}\n</style>")
    html = html.replace(
        js_tag,
        f'<script>window.NFFNSNC_EMBEDDED = "{enc_b64}";</script>\n<script>\n{js}\n</script>',
    )
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Offline-Kopie geschrieben: {args.out} ({len(html)} Bytes)")


if __name__ == "__main__":
    main()
