#!/usr/bin/env python3
"""Render Pikotika to audio sprites.

Every clip is generated here, at build time, by Kokoro running locally, and
shipped as a static file -- the site does no text-to-speech at runtime.

Run it in the `pikotika` environment, which has Kokoro and ffmpeg:

    micromamba run -n pikotika python gen_audio.py
    micromamba run -n pikotika python gen_audio.py --limit 8   # smoke test

Two shapes come out, because two different things play the audio:

    web/audio/words/*.m4a      + words.json      one file per word
    web/audio/numbers/*.m4a    + numbers.json    the number reader's vocabulary
    web/audio/sentences/*.m4a  + sentences.json  one file per sentence

A sprite is right when something will play many clips out of a known set -- a
lesson, where the alternative is forty fetches.  It is wrong for anything the
site plays one at a time: measured, fetching and decoding a 613-word sprite put
six to fourteen seconds in front of the first tap, against 7-44 ms for a single
file.  Both granularities therefore ship as files.  `build_sprite` is kept,
unused for now, for the course -- see GAME_DESIGN.md.

Sentences are generated whole rather than stitched from word clips: each word
carries its own penultimate stress and its own final fall, so a concatenation
comes out as a robotic list with audible joins instead of an utterance.

WAVs are cached under private/audio-cache/ keyed by voice and form, so adding a
coinage costs one clip rather than the whole corpus.  Delete the cache to force
a full regeneration.
"""

import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import gen_lexicon                      # noqa: E402
import phonemes as ph                   # noqa: E402
import pikotika                         # noqa: E402

CACHE = ROOT / "private" / "audio-cache"
OUT_DIR = ROOT / "web" / "audio"

# Kokoro's voices are English-trained models being handed raw phonemes, so they
# differ in how well they take the vowel set rather than merely in timbre.
# These two were chosen by ear over the full set; af_nicole is unusable.
# Word tiles alternate between them so the learner is not tuned to one speaker.
# Dialogs and stories will pick by character instead -- hence voice_for() rather
# than a constant.
#
# af_heart replaced af_sky throughout on 2026-08-20: af_sky puts a consonantal
# onset in front of some vowel-initial words, so **ora** came out "dora" -- and
# `ora` is every clock time on /topics/time/.  The artifact is the voice's, not
# any one set's, so the swap had to be everywhere rather than in NUMBER_VOICE
# alone: `ora` was on af_sky in the word set too, and half the sentence clips
# that say a time with it.  Fixing only the reader would have put a clean
# **ora** in the clock and a "dora" in the chip directly above it.
WORD_VOICES = ("af_heart", "bm_george")

# The number reader chains clips together, so its set is one voice throughout.
# Alternating would change speaker four times inside `tekas pits kiru, tets
# katon wats tekas kins`, which is one number.
#
# This is a separate constant so a chained reading has one speaker, not so the
# casting can differ; keep it whichever of WORD_VOICES is the female voice.
NUMBER_VOICE = "af_heart"

SPEED = 1.0

# Silence between clips in a sprite.  AAC carries encoder priming and padding,
# and a decoder does not always hand those back exactly, so a slice can bleed a
# few milliseconds into its neighbor.  A gap absorbs that; without it you hear
# the tail of the previous word.
PAD_SECONDS = 0.12

# Kokoro leaves silence at both ends of every clip -- measured over the corpus,
# 79 ms before the word and 139 ms after.  The trailing silence is only weight,
# but the leading silence is a lag on every tap, which for a tile you press to
# hear a word is the whole interaction.  Trimmed here at sprite-build time
# rather than when caching, so re-tuning these costs a re-encode and not a
# re-render of a thousand clips.
TRIM_KEEP = 0.02        # silence left at each end, seconds
TRIM_FLOOR = 0.002      # absolute amplitude floor, for a very quiet clip
TRIM_RATIO = 0.02       # ...or this fraction of the clip's peak, whichever is more

UNSAFE = re.compile(r"[^a-z0-9]+")


def assign_voices(keys) -> dict:
    """Give each utterance a voice, by its own hash.  Order-independent.

    A key's voice depends on nothing but the key, so **adding an utterance
    never moves an existing one**, and the assignment generalizes to any number
    of voices by widening WORD_VOICES.

    This replaced an exact median split on 2026-08-20.  That version sorted the
    keys by hash and cut the list in half, to guarantee a 50/50 share -- hash
    parity was rejected for coming out 54/46 over 613 words.  The flaw is that
    *the cut moves*: adding one corpus row shifts the median by half a slot and
    reassigns whatever sits next to it.  A reassigned clip already has an
    `.m4a`, `build_files` skips a file that exists, and so it keeps the old
    voice under an index that claims the new one -- silently, with no error and
    with check_audio still passing.  It happened on every corpus addition since
    the pipeline was built; adding one sentence left six clips stale.

    An approximate share is worth far more than an exact one here, and the
    approximation is not even bad: measured at the changeover, 312/305 over the
    words and 211/210 over the sentences.  The 54/46 that motivated the median
    cut was a smaller sample being read as a trend.
    """
    return {key: WORD_VOICES[int(hashlib.sha1(key.encode("utf-8")).hexdigest(), 16)
                             % len(WORD_VOICES)]
            for key in keys}


def cache_path(voice: str, text: str) -> Path:
    """A cache file per voice and utterance.

    Named by a readable prefix plus a hash of the exact text: the prefix so the
    directory can be browsed, the hash so that punctuation and case still key
    distinctly and no two utterances can collide on a sanitized name.
    """
    slug = UNSAFE.sub("_", text.lower()).strip("_")[:40] or "clip"
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return CACHE / voice / f"{slug}-{digest}.wav"


def write_wav(path: Path, audio, rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
    with open(path, "wb") as raw, wave.open(raw, "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(rate)
        fh.writeframes(samples.tobytes())


def trim(data, rate):
    """Strip Kokoro's leading and trailing silence, keeping a small margin."""
    if not len(data):
        return data
    amp = np.abs(data.astype(np.float32) / 32768.0)
    threshold = max(amp.max() * TRIM_RATIO, TRIM_FLOOR)
    loud = np.flatnonzero(amp > threshold)
    if not len(loud):
        return data                      # silent clip; leave it alone
    keep = int(TRIM_KEEP * rate)
    start = max(0, int(loud[0]) - keep)
    end = min(len(data), int(loud[-1]) + keep + 1)
    return data[start:end]


def read_wav(path: Path):
    with wave.open(str(path), "rb") as fh:
        rate = fh.getframerate()
        data = np.frombuffer(fh.readframes(fh.getnframes()), dtype="<i2")
    return data, rate


_engine = None


def engine():
    global _engine
    if _engine is None:
        try:
            from kokoro_onnx import Kokoro
        except ImportError:
            raise SystemExit(
                "kokoro-onnx is not importable.  Run this in the pikotika "
                "environment:\n"
                "  micromamba run -n pikotika python gen_audio.py")
        import os
        cache = Path.home() / ".cache" / "kokoro-onnx"
        model, voices = cache / "kokoro-v1.0.onnx", cache / "voices-v1.0.bin"
        if not (model.exists() and voices.exists()):
            raise SystemExit(
                f"Kokoro's model files are not in {cache}.  Run "
                "private/speak.py once to download them (~300 MB).")
        os.environ.setdefault("ONNX_PROVIDER", "CPUExecutionProvider")
        _engine = Kokoro(str(model), str(voices))
    return _engine


def render(text: str, voice: str, force: bool = False) -> Path:
    """One utterance to a cached WAV.  Returns the path."""
    path = cache_path(voice, text)
    if path.exists() and not force:
        return path
    sounds = ph.to_phonemes(text)
    if not sounds.strip():
        raise SystemExit(f"nothing to say for {text!r}")
    audio, rate = engine().create(sounds, voice=voice, speed=SPEED,
                                  is_phonemes=True)
    write_wav(path, audio, rate)
    return path


def build_sprite(name: str, items, force: bool, encode: bool = True) -> dict:
    """Render every item, concatenate, encode, and write the offset map.

    `items` is a sequence of (key, text, voice).  The map is
    {key: [offsetSeconds, durationSeconds, voice]}, which is what
    source.start(0, offset, duration) wants on the other end.
    """
    if not items:
        return {}
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    chunks, clips, rate = [], {}, None
    cursor = 0
    for index, (key, text, voice) in enumerate(items, 1):
        path = render(text, voice, force)
        data, this_rate = read_wav(path)
        data = trim(data, this_rate)
        if rate is None:
            rate = this_rate
        elif this_rate != rate:
            raise SystemExit(f"{key}: {this_rate} Hz among {rate} Hz clips")
        clips[key] = [round(cursor / rate, 4), round(len(data) / rate, 4), voice]
        chunks.append(data)
        cursor += len(data)
        pad = int(PAD_SECONDS * rate)
        chunks.append(np.zeros(pad, dtype="<i2"))
        cursor += pad
        if index % 25 == 0 or index == len(items):
            print(f"    {index}/{len(items)}", end="\r", flush=True)
    print()

    joined = OUT_DIR / f"{name}.wav"
    write_wav(joined, np.concatenate(chunks).astype(np.float32) / 32767.0, rate)

    target = OUT_DIR / f"{name}.m4a"
    if encode:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise SystemExit("ffmpeg is not on the path; run under the "
                             "pikotika environment")
        subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-i", str(joined),
             "-c:a", "aac", "-b:a", "48k", "-ac", "1", str(target)],
            check=True)
        joined.unlink()

    payload = {"file": f"{name}.m4a", "rate": rate, "pad": PAD_SECONDS,
               "clips": clips}
    (OUT_DIR / f"{name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")) + "\n", encoding="utf-8")

    size = target.stat().st_size if target.exists() else joined.stat().st_size
    print(f"  {name}: {len(clips)} clips, {size:,} bytes, "
          f"{cursor / rate:.1f}s")
    return clips


def build_files(name: str, items, force: bool) -> dict:
    """Render every item to its own .m4a, plus an index.

    For audio played one clip at a time: the browser fetches some kilobytes and
    decodes a second of sound, instead of pulling down the whole corpus to hear
    one word.
    """
    if not items:
        return {}
    out_dir = OUT_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is not on the path; run under the pikotika "
                         "environment")

    index, total = {}, 0
    for i, (key, text, voice) in enumerate(items, 1):
        wav = render(text, voice, force)
        data, rate = read_wav(wav)
        data = trim(data, rate)
        stem = cache_path(voice, text).stem
        target = out_dir / f"{stem}.m4a"
        if force or not target.exists():
            tmp = out_dir / f"{stem}.wav"
            write_wav(tmp, data.astype(np.float32) / 32767.0, rate)
            subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(tmp),
                            "-c:a", "aac", "-b:a", "48k", "-ac", "1",
                            str(target)], check=True)
            tmp.unlink()
        index[key] = [f"{name}/{target.name}", round(len(data) / rate, 4), voice]
        total += target.stat().st_size
        if i % 25 == 0 or i == len(items):
            print(f"    {i}/{len(items)}", end="\r", flush=True)
    print()

    (OUT_DIR / f"{name}.json").write_text(
        json.dumps({"kind": "files", "clips": index}, ensure_ascii=False,
                   sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8")
    print(f"  {name}: {len(index)} files, {total:,} bytes total")
    return index


def word_items(tables, limit=None):
    """The site's words, from build.audio_words() -- the lexicon plus anything
    written only in page prose, which is the same list check_audio verifies."""
    import build

    forms = build.audio_words()
    voices = assign_voices(forms)
    if limit:
        forms = forms[:limit]
    return [(form, form, voices[form]) for form in forms]


def number_items(tables, limit=None):
    """The words the /topics/numbers/ reader chains together.

    A reading is unbounded -- there is no clip for 12345 and never can be -- so
    this is the one place on the site where an utterance is stitched from word
    clips rather than spoken whole.  Rendered again here, in a single voice,
    rather than reusing the two-voice `words` set."""
    import build

    forms = build.audio_numbers()
    if limit:
        forms = forms[:limit]
    return [(form, form, NUMBER_VOICE) for form in forms]


def sentence_items(tables, limit=None):
    """The site's utterances, from build.audio_sentences() -- which the build
    also checks the shipped clips against, so the two cannot drift."""
    import build

    items = build.audio_sentences()
    voices = assign_voices(items)
    items = [(t, t, voices[t]) for t in items]
    return items[:limit] if limit else items


def report(items) -> None:
    counts = {}
    for _, _, voice in items:
        counts[voice] = counts.get(voice, 0) + 1
    total = sum(counts.values()) or 1
    parts = ", ".join(f"{v} {n} ({100 * n / total:.0f}%)"
                      for v, n in sorted(counts.items()))
    print(f"  voices: {parts}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--words", action="store_true", help="words only")
    ap.add_argument("--sentences", action="store_true", help="sentences only")
    ap.add_argument("--numbers", action="store_true",
                    help="the number reader's clips only")
    ap.add_argument("--limit", type=int, help="only the first N of each (smoke test)")
    ap.add_argument("--force", action="store_true", help="ignore the WAV cache")
    ap.add_argument("--no-encode", action="store_true",
                    help="leave the concatenated WAV, skip ffmpeg")
    args = ap.parse_args()

    ph.check_symbols()
    tables = pikotika.Tables(str(ROOT))
    both = not (args.words or args.sentences or args.numbers)

    if args.words or both:
        items = word_items(tables, args.limit)
        print(f"words: {len(items)}")
        report(items)
        build_files("words", items, args.force)

    if args.numbers or both:
        items = number_items(tables, args.limit)
        print(f"numbers: {len(items)}")
        report(items)
        build_files("numbers", items, args.force)

    if args.sentences or both:
        items = sentence_items(tables, args.limit)
        print(f"sentences: {len(items)}")
        report(items)
        build_files("sentences", items, args.force)


if __name__ == "__main__":
    main()
