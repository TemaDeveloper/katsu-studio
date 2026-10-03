#!/usr/bin/env python3
"""Remove silent narration pauses using FFmpeg; preserve the source file.

Example:
    python3 remove_reader_pauses.py narration.mp3
    python3 remove_reader_pauses.py narration.mp3 --min-pause 0.15 --keep-pause 0.04

Requires ffmpeg and ffprobe on PATH. No third-party Python packages required.
Audible breaths and quiet speech are not guaranteed to be classified as silence.
"""

import argparse
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import wave


def run(command):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "FFmpeg command failed")
    return result


def detect_pauses(log, duration):
    pauses = []
    start = None
    for match in re.finditer(r"silence_(start|end):\s*([0-9.eE+\-]+)", log):
        value = float(match.group(2))
        if match.group(1) == "start":
            start = max(0.0, value)
        elif start is not None:
            pauses.append((start, min(value, duration)))
            start = None
    if start is not None:
        pauses.append((start, duration))
    return pauses


def retained_ranges(frames, rate, pauses, keep_pause):
    removals = []
    margin = keep_pause / 2
    for start, end in pauses:
        first = round((start + (0 if start <= 1 / rate else margin)) * rate)
        last = round((end - (0 if end >= (frames - 1) / rate else margin)) * rate)
        first, last = max(0, first), min(frames, last)
        if last > first:
            removals.append((first, last))
    ranges = []
    cursor = 0
    for first, last in sorted(removals):
        if first > cursor:
            ranges.append((cursor, first))
        cursor = max(cursor, last)
    if cursor < frames:
        ranges.append((cursor, frames))
    return ranges


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path, help="Output .mp3 or .wav; defaults to INPUT_no_pauses.mp3")
    parser.add_argument("--threshold-db", type=float, default=-45, help="Silence threshold in dB (default: -45)")
    parser.add_argument("--min-pause", type=float, default=0.20, help="Minimum detected pause in seconds (default: 0.20)")
    parser.add_argument("--keep-pause", type=float, default=0.08, help="Total buffer retained per internal pause (default: 0.08)")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing output, never the source")
    args = parser.parse_args()
    source = args.input.expanduser().resolve()
    output = (args.output or source.with_name(source.stem + "_no_pauses.mp3")).expanduser().resolve()
    if not source.is_file():
        parser.error(f"Input does not exist: {source}")
    if source == output:
        parser.error("Output must differ from the original file")
    if output.suffix.lower() not in {".mp3", ".wav"}:
        parser.error("Output must be .mp3 or .wav")
    if not all(math.isfinite(x) for x in (args.threshold_db, args.min_pause, args.keep_pause)):
        parser.error("Settings must be finite numbers")
    if args.threshold_db >= 0 or args.min_pause <= 0 or not 0 <= args.keep_pause < args.min_pause:
        parser.error("Use a negative threshold and 0 <= keep-pause < min-pause")
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            parser.error(f"Install {tool} first (macOS: brew install ffmpeg)")
    report_path = output.with_suffix(".pauses.json")
    for target in (output, report_path):
        if target.exists() and not args.overwrite:
            parser.error(f"Already exists: {target}; use --overwrite or another output")
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="narration-pauses-") as directory:
        decoded = Path(directory) / "source.wav"
        shortened = Path(directory) / "shortened.wav"
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(source),
             "-map", "0:a:0", "-vn", "-c:a", "pcm_s16le", str(decoded)])
        with wave.open(str(decoded), "rb") as audio:
            frames, rate = audio.getnframes(), audio.getframerate()
            duration = frames / rate
            params = audio.getparams()
        detection = run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(decoded),
                         "-af", f"silencedetect=noise={args.threshold_db}dB:d={args.min_pause}",
                         "-f", "null", "-"])
        pauses = detect_pauses(detection.stderr, duration)
        ranges = retained_ranges(frames, rate, pauses, args.keep_pause)
        if not ranges:
            raise RuntimeError("Entire input was detected as silence; lower the threshold")
        timeline = []
        written = 0
        with wave.open(str(decoded), "rb") as audio, wave.open(str(shortened), "wb") as target:
            target.setparams(params)
            for first, last in ranges:
                audio.setpos(first)
                remaining = last - first
                timeline.append({"source_start": first / rate, "source_end": last / rate,
                                 "output_start": written / rate, "output_end": (written + remaining) / rate})
                while remaining:
                    count = min(remaining, rate * 10)
                    target.writeframesraw(audio.readframes(count))
                    remaining -= count
                written += last - first
        encoding = ["-c:a", "libmp3lame", "-q:a", "2"] if output.suffix.lower() == ".mp3" else ["-c:a", "pcm_s16le"]
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
             "-y" if args.overwrite else "-n", "-i", str(shortened), *encoding, str(output)])

    measured = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=noprint_wrappers=1:nokey=1", str(output)]).stdout.strip())
    report = {"input": str(source), "output": str(output), "source_seconds": duration,
              "output_audio_seconds": written / rate, "output_file_seconds": measured,
              "removed_seconds": (frames - written) / rate, "detected_pauses": len(pauses),
              "threshold_db": args.threshold_db, "minimum_pause_seconds": args.min_pause,
              "retained_pause_seconds": args.keep_pause,
              "detected_silence_intervals": pauses, "retained_segments": timeline}
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Detected pauses: {len(pauses)}")
    print(f"Original: {duration:.2f}s | Shortened: {measured:.2f}s | Removed: {report['removed_seconds']:.2f}s")
    print(f"Audio: {output}\nReport: {report_path}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, wave.Error) as error:
        raise SystemExit(f"Error: {error}")
