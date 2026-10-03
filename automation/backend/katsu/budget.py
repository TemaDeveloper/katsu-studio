import json
from .providers.errors import UnknownOutcome


class BudgetExceeded(ValueError):
    pass


class Budget:
    def __init__(self, store):
        self.store = store

    def reserve(self, project_id, request_key, estimated_usd):
        if estimated_usd <= 0:
            raise ValueError('A positive estimate is required.')
        s = self.store
        with s.lock:
            existing = s.db.execute('SELECT state FROM requests WHERE key=?', (request_key,)).fetchone()
            if existing and existing[0] != 'failed':
                raise UnknownOutcome('This paid request already started. Its saved result or billing outcome must be checked before retrying.')
            committed = s.db.execute("SELECT COALESCE(SUM(estimate),0) FROM requests WHERE project_id=? AND state!='failed'", (project_id,)).fetchone()[0]
            if committed + estimated_usd > s.get_project(project_id).settings.budget_usd + .000001:
                raise BudgetExceeded('The next request exceeds this project’s estimated spending limit. Increase the limit in Settings, then resume.')
            s.db.execute("INSERT OR REPLACE INTO requests VALUES (?,?,?,'reserved','{}')", (request_key, project_id, estimated_usd))
            s.db.commit()
            s.update_project(project_id, estimated_committed_usd=round(committed + estimated_usd, 4))

    def settle(self, request_key, usage):
        s = self.store
        with s.lock:
            s.db.execute('UPDATE requests SET state=?,usage=? WHERE key=?', ('failed' if usage.get('failed') else 'settled', json.dumps(usage), request_key))
            s.db.commit()
            self._refresh(request_key)

    def mark_unknown(self, request_key):
        with self.store.lock:
            self.store.db.execute("UPDATE requests SET state='unknown' WHERE key=?", (request_key,))
            self.store.db.commit()

    def saved_result(self, request_key):
        with self.store.lock:
            row = self.store.db.execute("SELECT usage FROM requests WHERE key=? AND state='settled'", (request_key,)).fetchone()
        return json.loads(row[0]).get('result') if row else None

    def recover_interrupted(self):
        with self.store.lock:
            self.store.db.execute("UPDATE requests SET state='unknown' WHERE state='reserved'")
            self.store.db.commit()

    def _refresh(self, key):
        s = self.store
        row = s.db.execute('SELECT project_id FROM requests WHERE key=?', (key,)).fetchone()
        if row:
            total = s.db.execute("SELECT COALESCE(SUM(estimate),0) FROM requests WHERE project_id=? AND state!='failed'", (row[0],)).fetchone()[0]
            s.update_project(row[0], estimated_committed_usd=round(total, 4))
