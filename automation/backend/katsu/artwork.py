"""Editable artwork drafts, immutable files, and saved-asset exports."""
import hashlib
import json
import re
import warnings
from io import BytesIO
from uuid import uuid4
from PIL import Image, ImageOps, UnidentifiedImageError
from .models import Artifact, Scene, TimedWord
from .store import now
from .rendering import render_video
from .thumbnail import SIZE, MAX_BYTES


MAX_UPLOAD = 12 * 1024 * 1024
MAX_PIXELS = 40_000_000


def validate_kind(store, id, kind):
    if kind != 'thumbnail':
        if not re.fullmatch(r'scene_[1-9][0-9]{0,2}', kind):
            raise KeyError('Image not found.')
        rows = json.loads(store.artifact_path(id, 'scenes').read_text())
        if not any(f'scene_{row["id"]}' == kind for row in rows):
            raise KeyError('Scene not found.')
    store.artifact_path(id, kind)
    return store.get_project(id).artifacts[kind]


def normalize_image(raw, kind, destination):
    """Decode bounded, static raster input; keep the whole composed cover."""
    if len(raw) > MAX_UPLOAD:
        raise ValueError('Choose an image under 12 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                if source.format not in ('PNG', 'JPEG', 'WEBP'):
                    raise ValueError('Choose a PNG, JPEG or WebP image.')
                if getattr(source, 'n_frames', 1) != 1:
                    raise ValueError('Choose a still image, without animation.')
                if min(source.size) < 128 or source.width * source.height > MAX_PIXELS:
                    raise ValueError('Use an image at least 128 pixels on each side and no larger than 40 megapixels.')
                source.load()
                oriented = ImageOps.exif_transpose(source)
                rgba = oriented.convert('RGBA')
                image = Image.new('RGB', rgba.size, 'white')
                image.paste(rgba, mask=rgba.getchannel('A'))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError('This image could not be read safely. Choose a valid PNG, JPEG or WebP file.') from None
    destination.parent.mkdir(parents=True, exist_ok=True)
    out = BytesIO()
    if kind == 'thumbnail':
        canvas = Image.new('RGB', SIZE, 'white')
        fitted = ImageOps.contain(image, SIZE, Image.Resampling.LANCZOS)
        canvas.paste(fitted, ((SIZE[0]-fitted.width)//2, (SIZE[1]-fitted.height)//2))
        for quality in (92, 88, 84, 80, 74, 68, 60, 50):
            out = BytesIO()
            canvas.save(out, 'JPEG', quality=quality, optimize=True, progressive=True)
            if out.tell() < MAX_BYTES:
                break
        if out.tell() >= MAX_BYTES:
            raise ValueError('This cover cannot fit the 2 MB limit. Try a simpler image.')
        dimensions, format_name = SIZE, 'JPEG'
    else:
        # Keep aspect ratio and avoid oversized render assets or previews.
        image.thumbnail((3840, 3840), Image.Resampling.LANCZOS)
        image.save(out, 'PNG')
        dimensions, format_name = image.size, 'PNG'
    encoded = out.getvalue()
    temp = destination.with_name(destination.name + '.' + uuid4().hex + '.tmp')
    temp.write_bytes(encoded)
    temp.replace(destination)
    return {'dimensions': list(dimensions), 'format': format_name, 'bytes': len(encoded)}


def draft_descriptor(artifact):
    return {**artifact.metadata, 'fingerprint': artifact.fingerprint, 'artifact_kind': artifact.kind}


def save_draft(store, id, kind, raw, base, origin, draft_id=None, instructions=''):
    draft_id = draft_id or uuid4().hex
    root = store.project_dir(id)
    dest = root / 'artwork' / (draft_id + ('.jpg' if kind == 'thumbnail' else '.png'))
    metadata = normalize_image(raw, kind, dest)
    artifact = Artifact(kind='artwork_draft_' + kind, path=str(dest.relative_to(root)),
        fingerprint=hashlib.sha256(dest.read_bytes()).hexdigest(), metadata={**metadata,
            'draft_id': draft_id, 'base_fingerprint': base, 'origin': origin,
            'instructions': instructions, 'created_at': now()})
    store.register_artifact(id, artifact)
    return draft_descriptor(artifact)


def saved_render_available(store, id):
    try:
        for kind in ('scenes', 'audio', 'words', 'script'):
            store.artifact_path(id, kind)
        rows = json.loads(store.artifact_path(id, 'scenes').read_text())
        if not rows:
            return False
        for scene in rows:
            store.artifact_path(id, f'scene_{scene["id"]}')
        return True
    except KeyError:
        return False


def apply_artwork(store, id, kind, artifact):
    artifact = artifact.model_copy(deep=True)
    artifact.kind = kind
    artifact.metadata.update(manual=True, saved_at=now())
    fields = {}
    if kind != 'thumbnail':
        fields = ({'status': 'queued', 'stage': 'rendering', 'render_only': True,
            'thumbnail_only': False, 'cancel_requested': False, 'error': None}
            if saved_render_available(store, id) else {'status': 'needs_attention', 'render_only': False,
                'error': 'Image saved. Continue production to finish the remaining assets.'})
    store.register_artifact(id, artifact, remove_kinds=('artwork_draft_' + kind, 'images_package'), **fields)
    return store.get_project(id)


def render_saved(pipeline, id):
    """No provider calls: rebuild from registered images and saved word timing."""
    s = pipeline.store
    p = s.get_project(id)
    root = s.project_dir(id)
    pipeline.checkpoint(id, 'rendering')
    scenes = [Scene.model_validate(x) for x in json.loads(s.artifact_path(id, 'scenes').read_text())]
    words = [TimedWord.model_validate(x) for x in json.loads(s.artifact_path(id, 'words').read_text())]
    images = {x.id: s.artifact_path(id, f'scene_{x.id}') for x in scenes}
    overlays = json.loads(s.artifact_path(id, 'overlays').read_text()) if p.imported and 'overlays' in p.artifacts else {}
    artifact = render_video(root, scenes, words, s.artifact_path(id, 'audio'), images, overlays)
    pipeline.checkpoint(id, 'rendering')
    with s.lock:
        artifacts = [artifact] + [Artifact(kind=kind, path=artifact.metadata[kind+'_path'], fingerprint=artifact.fingerprint)
            for kind in ('timeline', 'verification')]
        # A saved export does not imply unfinished thumbnail work was completed.
        has_thumbnail = 'thumbnail' in s.get_project(id).artifacts
        s.register_artifacts(id, artifacts, remove_kinds=('images_package', 'narration_text'),
            render_only=False, actual_seconds=artifact.metadata['duration_seconds'],
            status='completed' if has_thumbnail else 'needs_attention',
            stage='complete' if has_thumbnail else 'thumbnail', thumbnail_only=not has_thumbnail,
            error=None if has_thumbnail else 'Video updated. Continue production to create its thumbnail.')


def run_edit(pipeline, id, ai):
    s = pipeline.store
    job = s.get_project(id).artwork_edit
    pipeline.checkpoint(id, 'artwork_edit')
    current = validate_kind(s, id, job.kind)
    if current.fingerprint != job.base_fingerprint:
        raise ValueError('The original image changed. Discard this edit and start a new preview.')
    root = s.project_dir(id)
    dest = root / 'artwork' / (job.draft_id + '-response.png')
    pipeline.paid(id, 'artwork_edit_' + job.kind, job.request_key, job.estimate,
        lambda: ai.edit_image(job.instructions, s.artifact_path(id, job.kind), dest))
    # The durable paid receipt lets resume recover without another purchase.
    response = s.contained(id, str(dest.relative_to(root)))
    if not response.is_file():
        raise ValueError('The paid edit response is missing. Inspect its saved request before another attempt.')
    with s.lock:
        draft = save_draft(s, id, job.kind, response.read_bytes(), job.base_fingerprint, 'ai', job.draft_id, job.instructions)
        s.db.execute('UPDATE artwork_submissions SET payload=? WHERE project_id=? AND key=?',
            (json.dumps({'state': 'ready', **draft}), id, job.request_key))
        s.db.commit()
    pipeline.checkpoint(id, 'artwork_edit')
    s.update_project(id, artwork_edit=None, status=job.previous_status,
        stage=job.previous_stage, error=job.previous_error, render_only=job.previous_render_only)
