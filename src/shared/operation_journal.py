"""Durable operational metadata and work intents for the single-host deployment.

Payloads are private execution state; audit endpoints never return them. SQLite
lives on a named volume, independent of application container replacement.
"""
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


class OperationJournal:
    def __init__(self, path=None):
        self.path = str(path or os.getenv('OPERATION_JOURNAL_PATH', '/app/operational_data/operations.db'))
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript('''
              PRAGMA journal_mode=WAL;
              CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp REAL NOT NULL,
                actor TEXT, action TEXT, target TEXT, outcome TEXT, operation_id TEXT);
              CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS work (
                id TEXT PRIMARY KEY, lane TEXT NOT NULL, payload TEXT NOT NULL,
                status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                updated REAL NOT NULL, available REAL NOT NULL DEFAULT 0,
                owner TEXT, result TEXT);
              CREATE INDEX IF NOT EXISTS work_pending ON work(lane,status,available);
            ''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db: yield db
        finally:
            db.close()

    def event(self, action, target='', outcome='', actor='system', operation_id=''):
        with self.connection() as db:
            db.execute('INSERT INTO events(timestamp,actor,action,target,outcome,operation_id) VALUES (?,?,?,?,?,?)',
                       (time.time(), str(actor), action, str(target), outcome, operation_id))

    def events(self, before=None, limit=100):
        with self.connection() as db:
            return [dict(row) for row in db.execute('SELECT * FROM events WHERE id < ? ORDER BY id DESC LIMIT ?',
                                                   (before or 9223372036854775807, min(limit, 200)))]

    def get(self, key, default=None):
        with self.connection() as db:
            row = db.execute('SELECT value FROM state WHERE key=?', (key,)).fetchone()
        return json.loads(row['value']) if row else default

    def put(self, key, value):
        with self.connection() as db:
            db.execute('INSERT INTO state VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, json.dumps(value)))

    def enqueue(self, lane, payload, identifier=None):
        identifier = identifier or str(uuid4())
        with self.connection() as db:
            db.execute('INSERT OR IGNORE INTO work(id,lane,payload,status,updated) VALUES (?,?,?,?,?)',
                       (identifier, lane, json.dumps(payload), 'pending', time.time()))
        return identifier

    def work(self, identifier):
        with self.connection() as db:
            row = db.execute('SELECT * FROM work WHERE id=?', (identifier,)).fetchone()
        if not row: return None
        item = dict(row)
        item['payload'] = json.loads(item['payload'])
        item['result'] = json.loads(item['result']) if item['result'] else None
        return item

    def unfinished(self, lane):
        with self.connection() as db:
            return [row['id'] for row in db.execute("SELECT id FROM work WHERE lane=? AND status IN ('pending','running','recovering')", (lane,))]

    def claim(self, lane, owner, max_attempts=5, lease=90):
        now = time.time()
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            stale = db.execute("SELECT id FROM work WHERE lane=? AND status='running' AND updated < ?", (lane, now-lease)).fetchall()
            for row in stale:
                db.execute("UPDATE work SET status='recovering',owner=NULL,available=? WHERE id=?", (now, row['id']))
                db.execute('INSERT INTO events(timestamp,actor,action,target,outcome,operation_id) VALUES (?,?,?,?,?,?)',
                           (now, 'system', 'task.interrupted', lane, 'recovering', row['id']))
            db.execute("UPDATE work SET status='failed',updated=? WHERE lane=? AND status IN ('pending','recovering') AND attempts>=?", (now,lane,max_attempts))
            row = db.execute("SELECT id FROM work WHERE lane=? AND status IN ('pending','recovering') AND available<=? ORDER BY updated LIMIT 1", (lane,now)).fetchone()
            if not row: return None
            db.execute("UPDATE work SET status='running',attempts=attempts+1,owner=?,updated=? WHERE id=?", (owner,now,row['id']))
        return self.work(row['id'])

    def heartbeat(self, identifier, owner):
        with self.connection() as db:
            db.execute("UPDATE work SET updated=? WHERE id=? AND owner=? AND status='running'", (time.time(),identifier,owner))

    def finish(self, identifier, owner, result):
        with self.connection() as db:
            return db.execute("UPDATE work SET status='completed',updated=?,result=? WHERE id=? AND owner=? AND status='running'", (time.time(),json.dumps(result),identifier,owner)).rowcount

    def retry(self, identifier, owner, attempts):
        state = 'failed' if attempts >= 5 else 'recovering'
        with self.connection() as db:
            changed = db.execute("UPDATE work SET status=?,updated=?,available=?,owner=NULL WHERE id=? AND owner=? AND status='running'", (state,time.time(),time.time()+min(2**attempts,30),identifier,owner)).rowcount
        if not changed: return
        self.event('task.recovery_exhausted' if state == 'failed' else 'task.retry', self.work(identifier)['lane'], state, operation_id=identifier)

    def cancel(self, identifier):
        with self.connection() as db:
            db.execute("UPDATE work SET status='cancelled',updated=? WHERE id=? AND status IN ('pending','running','recovering')", (time.time(),identifier))


_journal = None

def journal():
    global _journal
    if _journal is None: _journal = OperationJournal()
    return _journal
