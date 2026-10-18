import csv
import importlib.metadata
import io
import json
import time
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from redis.exceptions import RedisError
from backend.graph.store import GraphStore
from backend.graph.seed import seed
from backend.erp.store import ERP
from backend.agents.service import Service, SCENARIOS
from backend.api.models import NoticeInput, InvestigationInput, DecisionInput, EvidenceInput, ResetInput, HealthOutput, InvestigationOutput, GraphOutput

g = GraphStore()
erp = ERP()
service = Service(g, erp)


@asynccontextmanager
async def lifespan(app):
    for attempt in range(30):
        try:
            g.query('RETURN 1')
            seed(g)
            erp.initialize([b['id'] for b in g.list('ProductionBatch')])
            # Interrupted jobs remain visible and must be deliberately rerun.
            g.query("MATCH (i:Investigation) WHERE i.status='running' SET i.status='failed', i.error='Backend restarted during execution; rerun investigation.'")
            break
        except RedisError:
            if attempt == 29:
                raise
            time.sleep(1)
    yield


app = FastAPI(title='SpecCascade', version='1.0.0', description='Synthetic manufacturing change intelligence. Demo authorization simulation.', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'], allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])


@app.exception_handler(RedisError)
async def graph_failure(request, exc):
    return JSONResponse(status_code=503, content={'detail': 'FalkorDB unavailable. Graph-dependent operations are paused; no substitute results are used.'})


@app.exception_handler(ValueError)
async def invalid(request, exc):
    return JSONResponse(status_code=409, content={'detail': str(exc)})


@app.exception_handler(PermissionError)
async def unauthorized(request, exc):
    return JSONResponse(status_code=403, content={'detail': str(exc)})


@app.get('/api/health', response_model=HealthOutput)
def health():
    g.query('RETURN 1')
    erp.snapshot()
    return dict(status='ready', graph=g.name, falkordb='connected', client_version=importlib.metadata.version('falkordb'), mode=service.mode)


def investigations():
    return sorted([i for i in g.list('Investigation') if i.get('notice')], key=lambda i: i['created_at'], reverse=True)


@app.get('/api/dashboard')
def dashboard(investigation: str | None = None):
    invs = investigations()
    selected = next((i for i in invs if i['id'] == investigation), None) if investigation else invs[0] if invs else None
    findings = service.findings(selected['id']) if selected else []
    snapshot = erp.snapshot()
    notices = g.list('ChangeNotice')
    total = len(g.list('ProductionBatch'))
    counts = {c: sum(b['classification'] == c for b in findings) for c in ['confirmed', 'uncertain', 'unaffected']}
    return {'total': total, **counts, 'unclassified': total-len(findings),
        'held': sum(v == 'QA_HOLD' for v in snapshot['inventory'].values()),
        'impacted_shipments': len({s['id'] for b in findings if b['hold_required'] for s in b['shipments'] if s['status']=='pending'}),
        'investigations': invs, 'current': selected, 'notices': notices, 'mode': service.mode,
        'verification': json.loads(selected['verification']) if selected and selected.get('verification') else None,
        'tasks': [t for t in g.list('AgentTask') if not selected or t.get('investigation') == selected['id']],
        'events': sorted([e for e in g.list('AgentEvent') if selected and e['investigation'] == selected['id']], key=lambda e: e['at']),
        'synthetic': True}


@app.get('/api/graph/schema')
def schema():
    return {'nodes': g.query('MATCH (n:Entity) RETURN n.kind,count(n) ORDER BY n.kind'),
            'edges': g.query('MATCH ()-[r]->() RETURN type(r),count(r) ORDER BY type(r)')}


@app.get('/api/graph', response_model=GraphOutput)
def graph(focus: str = 'B-001', hops: int = 2):
    return g.subgraph(focus, hops)


@app.get('/api/nodes/{identifier}')
def node(identifier: str, investigation: str | None = None):
    return {'node': g.get(identifier), 'subgraph': g.subgraph(identifier, 1),
        'finding': next((b for b in service.findings(investigation) if b['id'] == identifier), None) if investigation else None}


@app.get('/api/notices')
def notices():
    return g.list('ChangeNotice')


@app.post('/api/notices')
def ingest(request: NoticeInput):
    with service.lock:
        return service.ingest(request)


@app.post('/api/notices/upload')
async def upload(file: UploadFile = File(...)):
    raw = await file.read(256001)
    if len(raw) > 256000:
        raise HTTPException(413, 'Synthetic notice upload exceeds 250 KB.')
    try:
        text = raw.decode('utf-8-sig')
        if file.filename and file.filename.lower().endswith('.csv'):
            rows = list(csv.DictReader(io.StringIO(text)))
            if len(rows) != 1:
                raise ValueError('CSV must contain exactly one notice row.')
            data = rows[0]
            data['lots'] = data['lots'].split('|')
        else:
            data = json.loads(text)
        request = NoticeInput.model_validate(data)
    except (ValueError, UnicodeError, ValidationError) as exc:
        raise HTTPException(422, f'Invalid notice: {exc}') from exc
    with service.lock:
        return service.ingest(request)


@app.post('/api/demo/inject/{scenario}')
def inject(scenario: str):
    if scenario not in SCENARIOS:
        raise HTTPException(404, 'Unknown demo scenario')
    return ingest(NoticeInput(**SCENARIOS[scenario]))


@app.post('/api/investigations', response_model=InvestigationOutput)
def create(request: InvestigationInput):
    return service.create(request.notice, request.mode)


@app.get('/api/investigations')
def list_investigations():
    return investigations()


@app.get('/api/investigations/{inv}')
def investigation(inv: str):
    return {'investigation': g.get(inv), 'findings': service.findings(inv),
        'events': sorted([e for e in g.list('AgentEvent') if e['investigation'] == inv], key=lambda e: e['at']),
        'queries': [q for q in g.list('QueryExecution') if q['investigation'] == inv]}


@app.get('/api/batches')
def batches(investigation: str | None = None):
    snapshot = erp.snapshot()
    invs = investigations()
    inv = investigation or (invs[0]['id'] if invs else None)
    findings = {b['id']: b for b in service.findings(inv)} if inv else {}
    result = []
    for b in g.list('ProductionBatch'):
        result.append({**b, **findings.get(b['id'], {'classification': 'unclassified'}), 'erp_status': snapshot['inventory'].get(b['id'], 'UNKNOWN'),
            'owner': 'Dr. Maya Chen' if findings.get(b['id'], {}).get('hold_required') else 'Warehouse Operations'})
    return result


@app.get('/api/actions')
def actions(investigation: str | None = None):
    return [a for a in g.list('ProposedAction') if not investigation or a.get('investigation') == investigation]


@app.post('/api/investigations/{inv}/contain')
def contain(inv: str):
    if g.get(inv).get('mode') == 'llm':
        from backend.agents.llm import run_operation
        return run_operation(service, inv, 'contain')
    return service.contain(inv)


@app.post('/api/investigations/{inv}/verify')
def verify(inv: str):
    if g.get(inv).get('mode') == 'llm':
        from backend.agents.llm import run_operation
        return run_operation(service, inv, 'verify')
    return service.verify(inv)


@app.get('/api/erp')
def erp_state():
    g.query('RETURN 1')
    return erp.snapshot()


@app.post('/api/erp/dispatch/{shipment}')
def dispatch(shipment: str):
    return service.dispatch(shipment)


@app.get('/api/approvals')
def approvals(investigation: str | None = None):
    return [a for a in g.list('ApprovalDecision') if not investigation or a['investigation'] == investigation]


@app.get('/api/evidence/{inv}/{batch}')
def evidence(inv: str, batch: str):
    return service.evidence(inv, batch)


@app.post('/api/approvals/evidence')
def attest(request: EvidenceInput):
    return service.attest(request)


@app.post('/api/approvals/decide')
def decide(request: DecisionInput):
    return service.decide(request)


@app.get('/api/memory')
def memory():
    return sorted(g.list('MemoryEpisode'), key=lambda m: m['at'], reverse=True)


@app.get('/api/evaluation')
def evaluation(investigation: str | None = None):
    invs = investigations()
    current = next((i for i in invs if i['id'] == investigation), None) if investigation else invs[0] if invs else None
    if not current:
        return {'measured': False, 'reason': 'Run an investigation first.'}
    findings = service.findings(current['id'])
    queries = [q for q in g.list('QueryExecution') if q['investigation'] == current['id']]
    required = {b['id'] for b in findings if b['hold_required']}
    held = {h['batch'] for h in erp.snapshot()['holds'] if h['investigation'] == current['id'] and h['active']}
    # Golden labels are used only for evaluation, never by the engine.
    golden = json.loads((Path(__file__).parents[1]/'fixtures/expected_primary.json').read_text(encoding='utf-8-sig'))
    expected = set(golden['confirmed']) if current['notice'] == 'NOTICE-001' else None
    detected = {b['id'] for b in findings if b['classification'] == 'confirmed'}
    unaffected = {b['id'] for b in findings if b['classification'] == 'unaffected'}
    return {'measured': True, 'investigation': current['id'], 'mode': current['mode'], 'graph_queries': len(queries),
        'query_duration_ms': round(sum(q['duration_ms'] for q in queries), 2), 'duration_ms': current.get('duration_ms'),
        'confirmed_recall': len(expected & detected)/len(expected) if expected and findings else None,
        'false_positive_containment': len(held & unaffected)/len(unaffected) if unaffected else None,
        'containment_completeness': json.loads(current['verification'])['coverage'] if current.get('verification') else len(held & required)/len(required) if required else None,
        'unresolved_exposure': sum(b['classification'] == 'uncertain' for b in findings),
        'memory_retrieved': len(json.loads(current.get('retrieved_memory', '[]'))),
        'verification': json.loads(current['verification']) if current.get('verification') else None,
        'runs': [{'id': i['id'], 'notice': i['notice'], 'mode': i['mode'], 'duration_ms': i.get('duration_ms'),
                  'memory_retrieved': len(json.loads(i.get('retrieved_memory','[]'))), 'status': i['status']} for i in invs],
        'queries': queries,
        'restricted_context': 'Direct notice only. No exposure determination or ERP mutation is permitted without connected graph context.'}


@app.post('/api/demo/reset')
def reset(request: ResetInput):
    with service.lock:
        if any(i['status'] == 'running' for i in investigations()):
            raise ValueError('Wait for active tools to finish before resetting.')
        # Reset only this dedicated graph and ERP; never other user data or configuration.
        g.graph.delete()
        seed(g)
        erp.reset()
        erp.initialize([b['id'] for b in g.list('ProductionBatch')])
        return {'status': 'reset', 'synthetic': True, 'batches': len(g.list('ProductionBatch'))}
