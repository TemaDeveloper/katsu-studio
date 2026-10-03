from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from datetime import datetime, timezone
from uuid import UUID, uuid4
from .models import Artifact, Project, ProjectCreate, StudioSettings


def now():
    return datetime.now(timezone.utc).isoformat()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False))
    temp.replace(path)


class Store:
    def __init__(self, data_root: Path):
        self.root = Path(data_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.root / 'studio.sqlite', check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, key TEXT UNIQUE, request_hash TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, payload TEXT);
            CREATE TABLE IF NOT EXISTS requests (key TEXT PRIMARY KEY, project_id TEXT, estimate REAL, state TEXT, usage TEXT);
            CREATE TABLE IF NOT EXISTS artifact_versions (project_id TEXT, kind TEXT, fingerprint TEXT, payload TEXT, PRIMARY KEY(project_id,kind,fingerprint));
        ''')
        self.db.commit()

    def project_dir(self, id: str):
        try:
            canonical = str(UUID(id))
        except ValueError:
            raise KeyError('Project not found.') from None
        if canonical != id:
            raise KeyError('Project not found.')
        return self.root / 'projects' / canonical

    def settings(self):
        with self.lock:
            row = self.db.execute("SELECT payload FROM settings WHERE key='studio'").fetchone()
        return StudioSettings.model_validate_json(row[0]) if row else StudioSettings()

    def save_settings(self, value):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO settings VALUES ('studio', ?)", (value.model_dump_json(),))
            self.db.commit()

    def create_project(self, request: ProjectCreate, settings: StudioSettings, idempotency_key: str):
        request_hash = fingerprint(request.model_dump())
        with self.lock:
            row = self.db.execute('SELECT request_hash,payload FROM projects WHERE key=?', (idempotency_key,)).fetchone()
            if row:
                if row[0] != request_hash:
                    raise ValueError('This submission key was already used for a different topic.')
                return Project.model_validate_json(row[1])
            snapshot = settings.model_copy(deep=True)
            snapshot.target_seconds, snapshot.scene_count = request.target_seconds, request.scene_count
            if request.budget_usd is not None:
                snapshot.budget_usd = request.budget_usd
            project = Project(id=str(uuid4()), topic=request.topic, title=request.topic, settings=snapshot,
                              total_assets=request.scene_count, created_at=now(), updated_at=now())
            self.project_dir(project.id).mkdir(parents=True)
            self.db.execute('INSERT INTO projects VALUES (?,?,?,?)', (project.id, idempotency_key, request_hash, project.model_dump_json()))
            self.db.commit()
            return project

    def get_project(self, id):
        self.project_dir(id)
        with self.lock:
            row = self.db.execute('SELECT payload FROM projects WHERE id=?', (id,)).fetchone()
        if not row:
            raise KeyError('Project not found.')
        return Project.model_validate_json(row[0])

    def list_projects(self):
        with self.lock:
            rows = self.db.execute('SELECT payload FROM projects ORDER BY rowid DESC').fetchall()
        return [Project.model_validate_json(r[0]) for r in rows]

    def update_project(self, id, **fields):
        with self.lock:
            data = self.get_project(id).model_dump()
            data.update(fields, updated_at=now())
            project = Project.model_validate(data)
            self.db.execute('UPDATE projects SET payload=? WHERE id=?', (project.model_dump_json(), id))
            self.db.commit()
            return project

    def contained(self, id, path):
        root = self.project_dir(id).resolve()
        candidate = Path(path)
        if candidate.is_absolute():
            raise ValueError('Artifact paths must be project-relative.')
        target = (root / candidate).resolve()
        if not target.is_relative_to(root) or target == root:
            raise ValueError('Artifact path is outside the project.')
        return target

    def register_artifact(self, id, artifact):
        if not self.contained(id, artifact.path).is_file():
            raise ValueError('Artifact file is missing.')
        with self.lock:
            artifacts = self.get_project(id).artifacts
            artifacts[artifact.kind] = artifact
            self.db.execute('INSERT OR REPLACE INTO artifact_versions VALUES (?,?,?,?)', (id, artifact.kind, artifact.fingerprint, artifact.model_dump_json()))
            self.update_project(id, artifacts=artifacts)

    def find_artifact(self, id, kind, fingerprint):
        with self.lock:
            row = self.db.execute('SELECT payload FROM artifact_versions WHERE project_id=? AND kind=? AND fingerprint=?', (id, kind, fingerprint)).fetchone()
            if not row:
                return None
            artifact = Artifact.model_validate_json(row[0])
            if not self.contained(id, artifact.path).is_file():
                return None
            self.register_artifact(id, artifact)
            return self.artifact_path(id, kind)

    def remove_artifacts(self, id, kinds):
        kinds = list(kinds)
        if 'video' in kinds:
            kinds.extend(('images_package', 'narration_text'))
        with self.lock:
            artifacts = self.get_project(id).artifacts
            for kind in kinds:
                artifacts.pop(kind, None)
            self.update_project(id, artifacts=artifacts)

    def artifact_path(self, id, kind):
        artifact = self.get_project(id).artifacts.get(kind)
        if not artifact:
            raise KeyError('This file is not available yet.')
        path = self.contained(id, artifact.path)
        if not path.is_file():
            raise KeyError('The saved file is missing.')
        return path
