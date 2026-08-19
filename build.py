#!/usr/bin/env python3
"""Build the pikotika.org static site into site/.

Everything the site shows is either a hand-written fragment in web/pages/ or,
later, generated from the .tsv tables.  There is no framework and no bundler:
the output is plain files at real URLs, one directory per section.

    python3 build.py            build into docs/
    python3 build.py --serve    build, then serve docs/ on :8000
"""

import argparse
import html.parser
import http.server
import functools
import re
import shutil
import sys
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
# docs/ rather than site/ because GitHub Pages, publishing from a branch, will
# serve the repository root or docs/ and nothing else.  The directory is
# committed: deploying is `python3 build.py` and a push.
OUT = ROOT / "docs"

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

# Built, but deliberately not in the navigation: pages for us, not for readers.
# `fragment` is a callable here rather than a filename under web/pages/.
UNLISTED = [
    ("/specimen/", "gen_specimen", "Han specimen — Pikotika",
     "Every character in the Pikotika Han font, with a per-glyph check that it "
     "actually came from that font."),
]

STATIC_DIRS = ["css", "js", "images", "fonts", "data", "audio"]

# Loose files copied to the output root.  CNAME is what keeps the custom domain
# attached across a redeploy; .nojekyll turns off the Jekyll pass that branch
# published Pages otherwise runs, which would drop anything beginning with `_`.
STATIC_FILES = ["CNAME", ".nojekyll"]


def asset_version(*parts: str) -> str:
    """A short content hash for a ?v= query on css and js.

    Without it a browser is free to keep serving the copy it already has --
    including the dev server's, which sends no Cache-Control at all, so a fresh
    tab can still run yesterday's JavaScript.  Hashing the content means the URL
    changes exactly when the file does, and never otherwise."""
    digest = hashlib.sha256()
    for part in parts:
        digest.update((WEB / part).read_bytes())
    return digest.hexdigest()[:10]


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


class PkCollector(html.parser.HTMLParser):
    """Pull the text of every <span class="pk"> out of a page fragment.

    Chips are wrapped by JavaScript at page load, not here -- pages keep plain
    prose and the HTML stays readable.  What the build owes in exchange is that
    the *forms* are real, which is what this collects and check_forms verifies.
    A `.pk` that is not running Pikotika -- a word-order schema like S RI V A O
    -- opts out with data-check="off"."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found = []          # (text, line)
        self._depth = 0          # nesting depth inside the current .pk
        self._buf = []
        self._line = 0

    def handle_starttag(self, tag, attrs):
        if self._depth:
            self._depth += 1
            return
        attrs = dict(attrs)
        classes = (attrs.get("class") or "").split()
        if "pk" in classes and attrs.get("data-check") != "off":
            self._depth = 1
            self._buf = []
            self._line = self.getpos()[0]

    def handle_endtag(self, tag):
        if not self._depth:
            return
        self._depth -= 1
        if self._depth == 0:
            text = " ".join("".join(self._buf).split())
            if text:
                self.found.append((text, self._line))

    def handle_data(self, data):
        if self._depth:
            self._buf.append(data)


def pk_strings(fragment: str):
    parser = PkCollector()
    parser.feed(fragment)
    return parser.found


def page_sentences() -> list:
    """Every multi-word Pikotika string on the site, in page order.

    These need audio just as the corpus does -- an example on the Overview page
    is not necessarily a corpus line -- and gen_audio reads them from here so
    there is one definition of what the site says out loud."""
    out = []
    for _, _, fragment, _, _ in PAGES:
        text = (WEB / "pages" / fragment).read_text(encoding="utf-8")
        for string, _line in pk_strings(text):
            if len(string.split()) > 1 and string not in out:
                out.append(string)
    return out


def check_forms(tables, sources) -> list:
    """Parse every Pikotika string on the site; fail on a form that is not real.

    This is the build-time half of the word chips.  Returns the forms in use,
    which gen_lexicon folds into lexicon.json so that a word written only in
    page prose still has an entry for its chip to open."""
    import pikotika

    forms, problems = [], []
    for label, fragment in sources:
        for text, line in pk_strings(fragment):
            fail = {}
            words = pikotika.parse_latin(text, tables, fail)
            if words is None:
                token = fail.get("token", text)
                problems.append(f"{label}:{line}: no such word {token!r}  "
                                f"in {text!r}")
                continue
            for word in words:
                if not pikotika.is_punct(word):
                    forms.append(pikotika.render_latin([word], tables))
    if problems:
        raise SystemExit("Pikotika in the pages does not check out:\n  "
                         + "\n  ".join(problems)
                         + "\n(mark a non-Pikotika span data-check=\"off\")")
    return forms


def check_fonts() -> None:
    """Refuse to ship a Han face that is missing a character.  A tofu box turns
    up on the one page that uses that root, and nobody notices for months."""
    import gen_han_font
    from fontTools.ttLib import TTFont

    wanted = gen_han_font.wanted_chars()
    for _, slug, _, _ in gen_han_font.FACES:
        path = WEB / "fonts" / f"pikotika-han-{slug}.woff2"
        if not path.exists():
            raise SystemExit(f"{path} is missing -- run python3 gen_han_font.py")
        gen_han_font.verify(TTFont(str(path)), wanted, path.name)


def build() -> None:
    import gen_lexicon
    import pikotika

    check_fonts()

    tables = pikotika.Tables()
    fragments = {fragment: (WEB / "pages" / fragment).read_text(encoding="utf-8")
                 for _, _, fragment, _, _ in PAGES}
    forms = check_forms(tables, sorted(fragments.items()))
    lexicon, unresolved = gen_lexicon.build(tables, forms)
    if unresolved:
        raise SystemExit(f"cannot build a lexicon entry for: {unresolved}")
    path = gen_lexicon.write(lexicon)
    print(f"  {len(forms)} words checked; {len(lexicon['words'])} in "
          f"{path.relative_to(ROOT)}")

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    for name in STATIC_DIRS:
        src = WEB / name
        if src.is_dir():
            shutil.copytree(src, OUT / name,
                            ignore=shutil.ignore_patterns(".DS_Store", "*.swp"))

    for name in STATIC_FILES:
        src = WEB / name
        if src.is_file():
            shutil.copy2(src, OUT / name)

    template = (WEB / "templates" / "base.html").read_text(encoding="utf-8")
    css_version = asset_version("css/site.css")
    js_version = asset_version("js/site.js")

    import importlib

    pages = [(url, fragments[fragment], title_tag, description)
             for _, url, fragment, title_tag, description in PAGES]
    pages += [(url, importlib.import_module(module).fragment(),
               title_tag, description)
              for url, module, title_tag, description in UNLISTED]

    for url, content, title_tag, description in pages:
        html = render(
            template,
            title_tag=title_tag,
            description=description,
            site_url=SITE_URL,
            url=url,
            nav=nav_html(url),
            css_version=css_version,
            js_version=js_version,
            main_class="",
            content=content.rstrip("\n"),
        )
        target = OUT / url.lstrip("/") / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        print(f"  {url}")

    print(f"built {len(pages)} pages into {OUT}/")


def serve(port: int = 8000) -> None:
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(OUT))
    print(f"serving {OUT}/ at http://localhost:{port}/  (ctrl-C to stop)")
    http.server.ThreadingHTTPServer(("", port), handler).serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--serve", action="store_true", help="serve docs/ after building")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    build()
    if args.serve:
        try:
            serve(args.port)
        except KeyboardInterrupt:
            print()
