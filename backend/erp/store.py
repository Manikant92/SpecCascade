"""Persisted, transaction-protected enterprise simulation. No graph reasoning here."""
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from backend.graph.store import now, uid


class ERP:
    def __init__(self, path=None):
        self.path = path or os.getenv('ERP_PATH', 'erp.sqlite')
        self.lock = threading.RLock()
        with self.tx() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS inventory (batch TEXT PRIMARY KEY, status TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS holds (batch TEXT, investigation TEXT, active INTEGER, PRIMARY KEY(batch,investigation));
            CREATE TABLE IF NOT EXISTS dispositions (batch TEXT, investigation TEXT, decision TEXT, approval TEXT, PRIMARY KEY(batch,investigation));
            CREATE TABLE IF NOT EXISTS audit (id TEXT PRIMARY KEY, batch TEXT, investigation TEXT, action TEXT, at TEXT, detail TEXT);
            CREATE TABLE IF NOT EXISTS dispatch (shipment TEXT PRIMARY KEY, status TEXT, at TEXT);
            ''')

    @contextmanager
    def tx(self):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=20)
            db.row_factory = sqlite3.Row
            try:
                with db:
                    yield db
            finally:
                db.close()

    def initialize(self, batches):
        with self.tx() as db:
            db.executemany("INSERT OR IGNORE INTO inventory VALUES (?, 'AVAILABLE')", [(x,) for x in batches])

    def audit(self, db, batch, inv, action, detail):
        db.execute('INSERT INTO audit VALUES (?,?,?,?,?,?)', (uid('audit'), batch, inv, action, now(), json.dumps(detail)))

    def hold(self, batch, inv):
        with self.tx() as db:
            if db.execute('SELECT 1 FROM dispositions WHERE batch=? AND investigation=?', (batch, inv)).fetchone():
                return
            previous = db.execute('SELECT active FROM holds WHERE batch=? AND investigation=?', (batch, inv)).fetchone()
            db.execute('INSERT INTO holds VALUES (?,?,1) ON CONFLICT(batch,investigation) DO UPDATE SET active=1', (batch, inv))
            db.execute("UPDATE inventory SET status='QA_HOLD' WHERE batch=? AND status!='DISPOSED'", (batch,))
            if not previous or not previous['active']:
                self.audit(db, batch, inv, 'QA_HOLD', {'policy': 'QA-17'})

    def disposition(self, batch, inv, decision, approval):
        with self.tx() as db:
            existing = db.execute('SELECT * FROM dispositions WHERE batch=? AND investigation=?', (batch, inv)).fetchone()
            if existing:
                if existing['decision'] != decision:
                    raise ValueError('A terminal disposition already exists for this investigation and batch.')
                return
            state = db.execute('SELECT status FROM inventory WHERE batch=?', (batch,)).fetchone()
            if state and state['status'] == 'DISPOSED':
                raise ValueError('Disposed inventory is terminal and cannot be released by another investigation.')
            if not db.execute('SELECT 1 FROM holds WHERE batch=? AND investigation=? AND active=1', (batch, inv)).fetchone():
                raise ValueError('Disposition requires an active hold for this investigation.')
            db.execute('INSERT INTO dispositions VALUES (?,?,?,?)', (batch, inv, decision, approval))
            db.execute('UPDATE holds SET active=0 WHERE batch=? AND investigation=?', (batch, inv))
            other_holds = db.execute('SELECT count(*) FROM holds WHERE batch=? AND active=1', (batch,)).fetchone()[0]
            status = 'DISPOSED' if decision == 'dispose' else 'QA_HOLD' if other_holds else 'RELEASED'
            db.execute('UPDATE inventory SET status=? WHERE batch=?', (status, batch))
            self.audit(db, batch, inv, decision.upper(), {'approval': approval})

    def snapshot(self):
        with self.tx() as db:
            return {'inventory': {r['batch']: r['status'] for r in db.execute('SELECT * FROM inventory')},
                    'holds': [dict(r) for r in db.execute('SELECT * FROM holds')],
                    'dispositions': [dict(r) for r in db.execute('SELECT * FROM dispositions')],
                    'audit': [dict(r) for r in db.execute('SELECT * FROM audit ORDER BY at')],
                    'dispatch': [dict(r) for r in db.execute('SELECT * FROM dispatch')]}

    def dispatch(self, shipment, batches):
        with self.tx() as db:
            for b in batches:
                row = db.execute('SELECT status FROM inventory WHERE batch=?', (b,)).fetchone()
                if not row or row['status'] not in {'AVAILABLE', 'RELEASED'}:
                    raise ValueError(f'Dispatch blocked: {b} is {row[0] if row else "unknown"}')
            db.execute("INSERT OR IGNORE INTO dispatch VALUES (?, 'dispatched', ?)", (shipment, now()))
            self.audit(db, ','.join(batches), '', 'DISPATCH', {'shipment': shipment})

    def reset(self):
        with self.tx() as db:
            for table in ['inventory', 'holds', 'dispositions', 'audit', 'dispatch']:
                db.execute(f'DELETE FROM {table}')
