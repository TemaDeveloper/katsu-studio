from pathlib import Path
from types import SimpleNamespace
import json
import re
import subprocess
import hashlib
from io import BytesIO
from PIL import Image, ImageChops, ImageStat
from num2words import num2words
from .legacy import load
from .models import Artifact
from .store import atomic_json, fingerprint
from .audio import duration, command


def spoken_numbers(text):
    return re.sub(r'\b\d+(?:\.\d+)?\b', lambda m: num2words(m.group()), text)


def render_video(project_dir, scenes, words, audio, images=None, overlay_config=None):
    legacy = load('compose_video')
    images = images or {s.id: project_dir / f'scene-{s.id}.png' for s in scenes}
    shots = [{'shot': s.id, 'voiceover': spoken_numbers(s.voiceover), 'image': str(images[s.id])} for s in scenes]
    total = duration(audio)
    timed = legacy.validate_words({'words': [{'word': spoken_numbers(w.word), 'start': w.start, 'end': w.end} for w in words]}, total, legacy.digest(audio))
    timeline = legacy.timeline(shots, timed, total, 30)
    if timeline['issues'] or not timeline['renderable']:
        raise ValueError('Narration and images could not be matched safely: ' + '; '.join(timeline['issues']))
    build = project_dir / 'render-cache'
    build.mkdir(exist_ok=True)
    overlays = dict(overlay_config or {})
    font = '/System/Library/Fonts/Supplemental/Arial Bold.ttf'
    for scene in scenes:
        if scene.label:
            if len(scene.label) > 60:
                raise ValueError('A static label is too long.')
            overlays[str(scene.id)] = [{'text': scene.label, 'font': font, 'font_size': .04, 'x': .05, 'y': .035}]
    overlay_path = build / 'overlays.json'
    atomic_json(overlay_path, overlays)
    key = fingerprint({'images': [legacy.digest(images[s.id]) for s in scenes], 'audio': legacy.digest(audio), 'timeline': timeline, 'overlays': overlays})
    exports = project_dir / 'exports'
    exports.mkdir(exist_ok=True)
    pending = exports / f'{key}.pending.mp4'
    final = exports / f'{key}.mp4'
    args = SimpleNamespace(size='1920x1080', fps=30, jobs=2, overlays=overlay_path, audio=audio, output=pending)
    legacy.render(args, timeline, build, legacy.digest(audio))
    verification = verify_video(pending, timeline, audio, overlays)
    pending.replace(final)
    timeline_path, verification_path = exports / f'{key}.timeline.json', exports / f'{key}.verification.json'
    atomic_json(timeline_path, timeline)
    atomic_json(verification_path, verification)
    return Artifact(kind='video', path=str(final.relative_to(project_dir)), fingerprint=key,
                    metadata={'duration_seconds': total, 'timeline_path': str(timeline_path.relative_to(project_dir)), 'verification_path': str(verification_path.relative_to(project_dir))})


def verify_video(video, scene_manifest, audio, overlays=None):
    info = load('compose_video').probe(video)
    streams = info['streams']
    v = next((s for s in streams if s['codec_type'] == 'video'), None)
    a = next((s for s in streams if s['codec_type'] == 'audio'), None)
    if not v or not a or v['codec_name'] != 'h264' or a['codec_name'] != 'aac' or (v['width'], v['height']) != (1920, 1080):
        raise ValueError('Export has missing or incorrect audio/video streams.')
    actual = float(info['format']['duration'])
    if abs(actual - duration(audio)) > .15 or v['avg_frame_rate'] != '30/1' or int(v['nb_frames']) != scene_manifest['total_frames']:
        raise ValueError('Export duration, frame count or frame rate is incorrect.')
    command(['ffmpeg', '-v', 'error', '-i', video, '-f', 'null', '-'])
    checks = 0
    for row in scene_manifest['shots']:
        second = (row['start_frame'] + max(0, (row['frames']-1)//2)) / 30
        raw = command(['ffmpeg', '-v', 'error', '-ss', second, '-i', video, '-frames:v', 1, '-f', 'image2pipe', '-vcodec', 'png', '-'])
        with Image.open(BytesIO(raw)) as frame, Image.open(row['image']) as original:
            expected = Image.new('RGB', (1920, 1080), 'white')
            image = original.convert('RGB')
            image.thumbnail((1920, 1080))
            # Upscale as FFmpeg does, while preserving proportions.
            scale = min(1920/original.width, 1080/original.height)
            image = original.convert('RGB').resize((round(original.width*scale), round(original.height*scale)))
            expected.paste(image, ((1920-image.width)//2, (1080-image.height)//2))
            # Labels occupy the top strip; compare the image below it when present.
            box = (0, 160, 1920, 1080) if (overlays or {}).get(str(row['shot'])) else (0, 0, 1920, 1080)
            diff = ImageChops.difference(frame.convert('RGB').crop(box).resize((192, 108)), expected.crop(box).resize((192, 108)))
            error = sum(ImageStat.Stat(diff).mean)/3
            if error > 18:
                raise ValueError(f"Export image order check failed for scene {row['shot']}.")
        checks += 1
    return {'full_decode': True, 'resolution': [v['width'], v['height']], 'frames': int(v['nb_frames']), 'duration_seconds': actual, 'video_codec': v['codec_name'], 'audio_codec': a['codec_name'], 'image_order_checks': checks}
