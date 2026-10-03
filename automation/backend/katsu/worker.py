import fcntl
import queue
import threading
from .pipeline import Pipeline
from .budget import Budget


class Worker:
    def __init__(self, store, keys, providers=None):
        self.store = store
        self.pipeline = Pipeline(store, keys, providers)
        self.queue = queue.Queue()
        self.pending = set()
        self.lock = threading.Lock()
        self.stopping = threading.Event()
        self.thread = None
        self.owner = None

    def start(self):
        self.owner = (self.store.root / 'worker.lock').open('a')
        try:
            fcntl.flock(self.owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another Katsu Studio process already owns this data folder.') from None
        Budget(self.store).recover_interrupted()
        for p in self.store.list_projects():
            if p.status == 'running':
                self.store.update_project(p.id, status='needs_attention', error='Production was interrupted. Saved assets remain available. Resume to recover; uncertain paid requests will require inspection.')
        self.thread = threading.Thread(target=self._run, daemon=True, name='katsu-worker')
        self.thread.start()
        for p in self.store.list_projects():
            if p.status == 'queued':
                self.enqueue(p.id)

    def enqueue(self, id):
        with self.lock:
            if id not in self.pending and not self.stopping.is_set():
                self.pending.add(id)
                self.queue.put(id)

    def busy(self, id):
        with self.lock:
            return id in self.pending

    def stop(self):
        self.stopping.set()
        with self.lock:
            for id in self.pending:
                self.pipeline.cancel(id)
        self.queue.put(None)
        if self.thread:
            self.thread.join(timeout=5)
        # Keep ownership until any in-flight worker exits; the process must not admit a second owner.
        if self.owner and (not self.thread or not self.thread.is_alive()):
            self.owner.close()

    def _run(self):
        try:
            while not self.stopping.is_set():
                id = self.queue.get()
                if id is None:
                    return
                try:
                    self.pipeline.run(id)
                finally:
                    with self.lock:
                        self.pending.discard(id)
                    self.queue.task_done()
        finally:
            if self.owner:
                self.owner.close()
