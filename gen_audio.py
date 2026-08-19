#!/usr/bin/env python3
"""Render Pikotika to audio sprites.

Every clip is generated here, at build time, by Kokoro running locally, and
shipped as a static file -- the site does no text-to-speech at runtime.

Run it in the `pikotika` environment, which has Kokoro and ffmpeg:

    micromamba run -n pikotika python gen_audio.py
    micromamba run -n pikotika python gen_audio.py --limit 8   # smoke test

Two shapes come out, because two different things play the audio:

    web/audio/words/*.m4a      + words.json      one file per word
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
WORD_VOICES = ("af_sky", "bm_george")

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
    """Split the set evenly between the two voices, stably.

    Not hash parity: that is only even on average, and over 613 words it drifts
    a couple of standard deviations off -- 54/46 in practice, which is visibly
    not the even split asked for.  Instead the keys are ordered by their hash
    (an arbitrary but fixed order, so neither voice ends up with all the short
    words or all of one letter) and cut at the median, which is exact.

    Still stable as the lexicon grows: adding a coinage shifts the median by
    half a slot, so at most a word or two changes voice and needs re-rendering,
    rather than the half of the corpus that re-hashing would reassign.
    """
    ordered = sorted(keys, key=lambda k: hashlib.sha1(k.encode("utf-8")).digest())
    half = len(ordered) // 2
    return {key: (WORD_VOICES[0] if i < half else WORD_VOICES[1])
            for i, key in enumerate(ordered)}


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
    ap.add_argument("--limit", type=int, help="only the first N of each (smoke test)")
    ap.add_argument("--force", action="store_true", help="ignore the WAV cache")
    ap.add_argument("--no-encode", action="store_true",
                    help="leave the concatenated WAV, skip ffmpeg")
    args = ap.parse_args()

    ph.check_symbols()
    tables = pikotika.Tables(str(ROOT))
    both = not (args.words or args.sentences)

    if args.words or both:
        items = word_items(tables, args.limit)
        print(f"words: {len(items)}")
        report(items)
        build_files("words", items, args.force)

    if args.sentences or both:
        items = sentence_items(tables, args.limit)
        print(f"sentences: {len(items)}")
        report(items)
        build_files("sentences", items, args.force)


if __name__ == "__main__":
    main()
