import json
from uuid import uuid4
from fastapi import HTTPException, Request
from .models import ArtworkApply, ArtworkEdit, ArtworkJob, ArtworkRestore
from .store import fingerprint
from .artwork import MAX_UPLOAD, validate_kind, save_draft, draft_descriptor, apply_artwork


def attach_artwork_routes(app, store, keys):
    def idle(id, allow_pending=False):
        p = store.get_project(id)
        if p.status in ('running', 'queued') or (app.state.worker and app.state.worker.busy(id)):
            raise ValueError('Wait for production to stop before editing an image.')
        if p.artwork_edit and not allow_pending:
            raise ValueError('Continue or discard the pending image edit first.')
        return p

    def uncertain(id):
        return store.db.execute("SELECT 1 FROM requests WHERE project_id=? AND state IN ('reserved','unknown') LIMIT 1", (id,)).fetchone()

    def base_image(id, kind, base):
        artifact = validate_kind(store, id, kind)
        if artifact.fingerprint != base:
            raise ValueError('This image changed since you opened it. Refresh and start a new preview.')
        return artifact

    def enqueue(p):
        if p.status == 'queued' and app.state.worker:
            app.state.worker.enqueue(p.id)
        return p

    @app.get('/api/projects/{id}/artwork/{kind}/draft')
    def draft(id: str, kind: str):
        validate_kind(store, id, kind)
        artifact = store.get_project(id).artifacts.get('artwork_draft_' + kind)
        return draft_descriptor(artifact) if artifact else None

    @app.post('/api/projects/{id}/artwork/{kind}/draft')
    def generate(id: str, kind: str, value: ArtworkEdit, request: Request):
        submission = request.headers.get('Idempotency-Key', '')
        if not 1 <= len(submission) <= 128:
            raise HTTPException(422, 'An image edit submission key is required.')
        request_key = fingerprint([kind, submission])
        content_hash = fingerprint([kind, value.model_dump()])
        with store.lock:
            p = store.get_project(id)
            row = store.db.execute('SELECT request_hash,payload FROM artwork_submissions WHERE project_id=? AND key=?', (id, request_key)).fetchone()
            if row:
                if row[0] != content_hash:
                    raise ValueError('This submission key was already used for a different image edit.')
                return json.loads(row[1])
            p = idle(id)
            base_image(id, kind, value.base_fingerprint)
            if uncertain(id):
                raise ValueError('Check the uncertain paid request and acknowledge its outcome before starting another edit.')
            if not keys.get('openai'):
                raise ValueError('Add your OpenAI API key in Settings to create an AI edit. Uploading an image is free.')
            current = store.settings()
            committed = store.db.execute("SELECT COALESCE(SUM(estimate),0) FROM requests WHERE project_id=? AND state!='failed'", (id,)).fetchone()[0]
            if committed + current.image_estimate_usd > current.budget_usd + .000001:
                raise ValueError('This edit exceeds the project spending limit. Increase the limit in Settings first.')
            job = ArtworkJob(kind=kind, draft_id=uuid4().hex, base_fingerprint=value.base_fingerprint,
                instructions=value.instructions, request_key=request_key, image_model=current.image_model,
                image_quality=current.image_quality, estimate=current.image_estimate_usd,
                previous_status=p.status, previous_stage=p.stage, previous_error=p.error, previous_render_only=p.render_only)
            receipt = {'state': 'queued', 'draft_id': job.draft_id, 'kind': kind}
            store.db.execute('INSERT INTO artwork_submissions VALUES (?,?,?,?)', (id, request_key, content_hash, json.dumps(receipt)))
            settings = p.settings.model_copy(update={'budget_usd': current.budget_usd})
            enqueue(store.update_project(id, artwork_edit=job, settings=settings, status='queued',
                stage='artwork_edit', render_only=False, cancel_requested=False, error=None))
            from fastapi.responses import JSONResponse
            return JSONResponse(receipt, status_code=202)

    @app.post('/api/projects/{id}/artwork/{kind}/draft/upload', status_code=201)
    async def upload(id: str, kind: str, request: Request):
        if request.headers.get('content-type', '').split(';')[0] not in ('image/png', 'image/jpeg', 'image/webp'):
            raise HTTPException(422, 'Choose a PNG, JPEG or WebP image.')
        base = request.headers.get('X-Base-Fingerprint', '')
        with store.lock:
            idle(id)
            base_image(id, kind, base)
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > MAX_UPLOAD:
                raise HTTPException(413, 'Choose an image under 12 MB.')
        with store.lock:
            idle(id)
            base_image(id, kind, base)
            try:
                return save_draft(store, id, kind, raw, base, 'upload')
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None

    @app.post('/api/projects/{id}/artwork/{kind}/apply')
    def apply(id: str, kind: str, value: ArtworkApply):
        with store.lock:
            idle(id)
            artifact = store.get_project(id).artifacts.get('artwork_draft_' + kind)
            if not artifact or artifact.metadata.get('draft_id') != value.draft_id:
                raise ValueError('This preview was replaced or discarded. Open the latest preview.')
            base_image(id, kind, artifact.metadata['base_fingerprint'])
            store.artifact_path(id, artifact.kind)
            return enqueue(apply_artwork(store, id, kind, artifact))

    @app.post('/api/projects/{id}/artwork/{kind}/draft/discard')
    def discard(id: str, kind: str):
        with store.lock:
            p = idle(id, allow_pending=True)
            validate_kind(store, id, kind)
            if p.artwork_edit and p.artwork_edit.kind == kind:
                if uncertain(id):
                    raise ValueError('Check and acknowledge the uncertain paid request before discarding this edit.')
                job = p.artwork_edit
                store.update_project(id, artwork_edit=None, status=job.previous_status, stage=job.previous_stage,
                    error=job.previous_error, render_only=job.previous_render_only, cancel_requested=False)
                store.db.execute('UPDATE artwork_submissions SET payload=? WHERE project_id=? AND key=?',
                    (json.dumps({'state': 'discarded', 'draft_id': job.draft_id, 'kind': kind}), id, job.request_key))
                store.db.commit()
            elif p.artwork_edit:
                raise ValueError('Continue or discard the pending image edit first.')
            store.remove_artifacts(id, ('artwork_draft_' + kind,))
            return {'discarded': True}

    @app.get('/api/projects/{id}/artwork/{kind}/versions')
    def versions(id: str, kind: str):
        current = validate_kind(store, id, kind)
        return [{'fingerprint': a.fingerprint, 'current': a.fingerprint == current.fingerprint,
            'origin': a.metadata.get('origin', 'original'),
            'created_at': a.metadata.get('saved_at', a.metadata.get('created_at'))}
            for a in store.artifact_versions(id, kind)]

    @app.post('/api/projects/{id}/artwork/{kind}/restore')
    def restore(id: str, kind: str, value: ArtworkRestore):
        with store.lock:
            idle(id)
            current = validate_kind(store, id, kind)
            if value.fingerprint == current.fingerprint:
                return store.get_project(id)
            artifact = next((a for a in store.artifact_versions(id, kind) if a.fingerprint == value.fingerprint), None)
            if artifact is None:
                raise KeyError('Saved image version not found.')
            return enqueue(apply_artwork(store, id, kind, artifact))
