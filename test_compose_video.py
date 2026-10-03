"""Offline alignment and real FFmpeg integration checks; never calls an API."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import compose_video as video


class AlignmentTests(unittest.TestCase):
    def test_repeated_phrase_and_extra_recognized_word(self):
        expected = video.tokens("You want it. You want it again.")
        heard = video.tokens("You want it. Um you want it again.")
        mapping = video.align(expected, heard)
        self.assertEqual([mapping[i][0] for i in range(len(expected))], [0, 1, 2, 4, 5, 6, 7])
        self.assertTrue(all(v[1] for v in mapping.values()))

    def test_numerals_and_contractions(self):
        self.assertEqual(video.tokens("In 2012, 481 people don't agree."),
                         video.tokens("In twenty twelve, four hundred and eighty-one people do not agree."))

    def test_weak_matches_flagged_and_missing_shots_blocked(self):
        shots = [{"shot": 1, "image": "x", "voiceover": "one two three four"}]
        words = [{"token": "one", "word": "one", "start": 0.1, "end": 0.2}]
        report = video.timeline(shots, words, 1, 30)
        self.assertTrue(report["issues"])
        missing = video.timeline(shots, [{**words[0], "token": "unrelated"}], 1, 30)
        self.assertFalse(missing["renderable"])

    def test_wrong_audio_and_invalid_timestamps_rejected(self):
        with self.assertRaises(ValueError):
            video.validate_words({"audio_sha256": "wrong"}, 1, "right")
        with self.assertRaises(ValueError):
            video.validate_words({"words": [{"word": "Hello", "start": 1.1, "end": 1.2}]}, 1, "x")

    def test_extra_audio_content_is_flagged(self):
        shots = [{"shot": 1, "image": "x", "voiceover": "hello"}]
        words = [{"token": token, "word": token, "start": i / 10, "end": (i + 1) / 10}
                 for i, token in enumerate(["hello", "completely", "different", "recording"])]
        report = video.timeline(shots, words, 1, 30)
        self.assertTrue(report["issues"])
        self.assertEqual(report["transcript_match_fraction"], 0.25)

    @unittest.skipUnless((video.ROOT / 'output/PRODUCTION_MANIFEST.json').exists(),
                         'Owner-only alignment check requires local episode files.')
    def test_full_project_against_actual_elevenlabs_text(self):
        shots = video.load_shots(video.ROOT / "output/PRODUCTION_MANIFEST.json")
        expected = [t for s in shots for t in video.tokens(s["voiceover"])]
        spoken = video.tokens((video.ROOT / "WHY_ARE_HUMANS_NEVER_SATISFIED_ELEVENLABS.txt").read_text())
        mapping = video.align(expected, spoken)
        self.assertEqual(len(mapping), len(expected))
        self.assertTrue(all(exact for _, exact in mapping.values()))


class RenderTests(unittest.TestCase):
    def test_real_video_boundaries_and_audio(self):
        with tempfile.TemporaryDirectory(prefix="video-test-") as name:
            root = Path(name)
            shots = []
            for i, color in enumerate(("red", "green", "blue"), 1):
                image = root / f"{i}.png"
                video.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                           f"color={color}:s=160x90", "-frames:v", "1", image])
                shots.append({"shot": i, "image": str(image), "voiceover": color})
            audio, manifest, transcript, output = [root / n for n in
                ("audio.wav", "shots.json", "words.json", "video.mp4")]
            video.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                       "sine=frequency=440:duration=3", audio])
            video.save(manifest, {"shots": shots})
            video.save(transcript, {"words": [
                {"word": color, "start": start, "end": start + 0.2}
                for color, start in (("red", 0.1), ("green", 1.0), ("blue", 2.0))]})
            argv = ["--manifest", str(manifest), "--audio", str(audio), "--transcript", str(transcript),
                    "--output", str(output), "--build-dir", str(root / "build"), "--size", "160x90"]
            self.assertEqual(video.main(argv), 0)
            info = video.probe(output)
            stream = next(s for s in info["streams"] if s["codec_type"] == "video")
            self.assertEqual(int(stream["nb_frames"]), 90)
            self.assertAlmostEqual(float(info["format"]["duration"]), 3.0, delta=0.08)
            self.assertTrue(any(s["codec_type"] == "audio" for s in info["streams"]))
            report = json.loads((root / "build/timeline.json").read_text())
            self.assertEqual([s["start_frame"] for s in report["shots"]], [0, 30, 60])
            # Inspect rendered pixels immediately before/after both cuts.
            for when, dominant in ((0.95, 0), (1.05, 1), (1.95, 1), (2.05, 2)):
                pixel = subprocess.check_output(["ffmpeg", "-v", "error", "-ss", str(when),
                    "-i", str(output), "-frames:v", "1", "-vf", "scale=1:1", "-pix_fmt", "rgb24",
                    "-f", "rawvideo", "-"])
                self.assertEqual(max(range(3), key=lambda j: pixel[j]), dominant)
            # Existing output is guarded; repeat render uses cached clips when authorized.
            self.assertEqual(video.main(argv), 1)
            self.assertEqual(video.main(argv + ["--overwrite"]), 0)


if __name__ == "__main__":
    unittest.main()
