# vendor/

Build inputs, kept here so the font build needs nothing installed.

`NotoSansCJKjp-{regular,bold}.subset.otf` are cuts of Noto Sans CJK JP holding
exactly the characters Pikotika uses, plus U+2212 and U+22A5, which
`gen_han_font.py` measures the hand-drawn turnstile against. Outlines are the
original CFF, untouched — building from these and building from the full
110 MB `NotoSansCJK.ttc` produce byte-identical output.

Re-cut them with `python3 gen_han_font.py --vendor` after adding a root whose
Han character these predate. That is the only time the full face is needed;
the script says so and tells you where to get it.

Noto Sans CJK is copyright the Noto Project Authors
(https://github.com/notofonts/noto-cjk), licensed under the SIL Open Font
License 1.1 — see `OFL.txt`. These subsets are derived works under that license.
