#!/usr/bin/env python3
"""Build the pikotika.org static site into site/.

Everything the site shows is either a hand-written fragment in web/pages/ or,
later, generated from the .tsv tables.  There is no framework and no bundler:
the output is plain files at real URLs, one directory per section.

    python3 build.py            build into site/
    python3 build.py --serve    build, then serve site/ on :8000
"""

import argparse
import http.server
import functools
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
OUT = ROOT / "site"

SITE_URL = "https://pikotika.org"

# label, url, source fragment, <title>, meta description
PAGES = [
    ("Overview", "/",         "index.html",
     "Pikotika — a tiny language for real conversation",
     "A constructed international language of about 200 roots, built for travel "
     "and small talk. Learnable in a weekend and forgiving of accents."),
    ("Vocab",    "/vocab/",   "vocab.html",
     "Vocab — Pikotika",
     "Every Pikotika root, compound, name, and loanword, searchable."),
    ("Grammar",  "/grammar/", "grammar.html",
     "Grammar — Pikotika",
     "Pikotika grammar in full: rigid word order, no conjugation, nothing irregular."),
    ("Topics",   "/topics/",  "topics.html",
     "Topics — Pikotika",
     "How to talk about colors, feelings, numbers, time, food, and travel in Pikotika."),
    ("Tools",    "/tools/",   "tools.html",
     "Tools — Pikotika",
     "Convert between English, gloss, Latin, and Han; adapt a name; read a number."),
    ("Learn",    "/learn/",   "learn.html",
     "Learn — Pikotika",
     "A free Pikotika course with no account and no login. Fifty short lessons."),
    ("Why",      "/why/",     "why.html",
     "Why Pikotika",
     "Why a two-hundred-root auxiliary language is worth building."),
]

STATIC_DIRS = ["css", "js", "images"]


def render(template: str, **fields) -> str:
    """Fill {{name}} placeholders.  Fails loudly on an unfilled one, since a
    literal {{title}} shipping to the site is the kind of thing nobody sees."""
    out = template
    for key, value in fields.items():
        out = out.replace("{{%s}}" % key, value)
    leftover = re.findall(r"\{\{(\w+)\}\}", out)
    if leftover:
        raise SystemExit(f"unfilled template fields: {sorted(set(leftover))}")
    return out


def nav_html(current_url: str) -> str:
    lines = []
    for label, url, *_ in PAGES:
        current = ' aria-current="page"' if url == current_url else ""
        lines.append(f'      <li><a href="{url}"{current}>{label}</a></li>')
    return "\n".join(lines)


def build() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    for name in STATIC_DIRS:
        src = WEB / name
        if src.is_dir():
            shutil.copytree(src, OUT / name,
                            ignore=shutil.ignore_patterns(".DS_Store", "*.swp"))

    template = (WEB / "templates" / "base.html").read_text(encoding="utf-8")

    for label, url, fragment, title_tag, description in PAGES:
        content = (WEB / "pages" / fragment).read_text(encoding="utf-8")
        html = render(
            template,
            title_tag=title_tag,
            description=description,
            site_url=SITE_URL,
            url=url,
            nav=nav_html(url),
            main_class="",
            content=content.rstrip("\n"),
        )
        target = OUT / url.lstrip("/") / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        print(f"  {url:<10} <- web/pages/{fragment}")

    print(f"built {len(PAGES)} pages into {OUT}/")


def serve(port: int = 8000) -> None:
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(OUT))
    print(f"serving {OUT}/ at http://localhost:{port}/  (ctrl-C to stop)")
    http.server.ThreadingHTTPServer(("", port), handler).serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--serve", action="store_true", help="serve site/ after building")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    build()
    if args.serve:
        try:
            serve(args.port)
        except KeyboardInterrupt:
            print()
