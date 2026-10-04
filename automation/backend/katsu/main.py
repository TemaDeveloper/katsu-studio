from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from .models import ProjectCreate, StudioSettings
from .store import Store
from .credentials import CredentialStore
from .config import AUTOMATION, channel_profile


class CredentialsInput(BaseModel):
    provider: str
    key: str = Field(min_length=10, max_length=1000)


def create_app(data_root: Path = AUTOMATION / 'data', worker_enabled=True, credentials=None, providers=None):
    store = Store(data_root)
    keys = credentials or CredentialStore()
    channel_profile(store.root)

    @asynccontextmanager
    async def lifespan(app):
        if worker_enabled:
            from .worker import Worker
            app.state.worker = Worker(store, keys, providers=providers)
            app.state.worker.start()
        yield
        if getattr(app.state, 'worker', None):
            app.state.worker.stop()

    app = FastAPI(title='Katsu Studio', lifespan=lifespan)
    app.state.store, app.state.keys, app.state.worker = store, keys, None

    @app.middleware('http')
    async def local_only(request: Request, call_next):
        host = request.url.hostname
        origin = request.headers.get('origin')
        if host not in ('localhost', '127.0.0.1', 'testserver'):
            return JSONResponse({'detail': 'Katsu Studio is a local application.'}, status_code=403)
        if origin and origin not in ('http://localhost:8850', 'http://127.0.0.1:8850', 'http://localhost:5173', 'http://127.0.0.1:5173', 'http://testserver'):
            return JSONResponse({'detail': 'This browser origin is not allowed.'}, status_code=403)
        return await call_next(request)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({'detail': str(exc).strip("'")}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=409)

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'version': '0.1.0'}

    @app.get('/api/settings')
    def settings():
        return {'settings': store.settings(), 'connections': keys.status(), 'channel': channel_profile(store.root)}

    @app.put('/api/settings')
    def save_settings(value: StudioSettings):
        store.save_settings(value)
        return {'settings': value, 'connections': keys.status()}

    @app.post('/api/credentials')
    def credentials_input(value: CredentialsInput):
        keys.set(value.provider, value.key)
        return {'connections': keys.status()}

    @app.get('/api/projects')
    def projects():
        return store.list_projects()

    @app.post('/api/projects', status_code=201)
    def create(value: ProjectCreate, request: Request):
        project = store.create_project(value, store.settings(), request.headers.get('Idempotency-Key', str(uuid4())))
        if app.state.worker and project.status == 'queued':
            app.state.worker.enqueue(project.id)
        return project

    @app.get('/api/projects/{id}')
    def project(id: str):
        return store.get_project(id)

    @app.get('/api/projects/{id}/artifacts/{kind}')
    def artifact(id: str, kind: str, download: bool = False):
        path = store.artifact_path(id, kind)
        return FileResponse(path, filename=path.name if download else None)

    @app.get('/api/brand/avatar')
    def avatar():
        path = store.root / 'channel/avatar.png'
        if not path.exists():
            raise HTTPException(404, 'Avatar not found.')
        return FileResponse(path)

    from .artwork_routes import attach_artwork_routes
    attach_artwork_routes(app, store, keys)
    from .topic_routes import attach_topic_routes
    attach_topic_routes(app, store)
    from .routes import attach_routes
    attach_routes(app, store, keys)
    return app
