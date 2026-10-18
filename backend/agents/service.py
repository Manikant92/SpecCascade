import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from backend.graph.store import IMPACT_QUERY, uid, now
from backend.policies.engine import classify, requires_hold, validate_disposition, RELEASE_PREREQUISITES
from backend.memory.service import retrieve

SCENARIOS = {
    'primary': dict(id='NOTICE-001', title='Undeclared milk · cocoa blend correction', lots=['LOT-A101', 'LOT-A102']),
    'second': dict(id='NOTICE-002', title='Follow-up correction · additional cocoa lot', lots=['LOT-A103']),
    'ambiguity': dict(id='NOTICE-003', title='Incomplete supplier identifiers · cocoa deliveries', lots=['LOT-A10'], scope='ambiguous'),
}


class Service:
    def __init__(self, g, erp):
        self.g, self.erp = g, erp
        self.lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=1)

    @property
    def mode(self):
        return 'llm' if os.getenv('OPENAI_API_KEY') and os.getenv('AI_PROVIDER', 'auto') != 'offline' else 'offline'

    def ingest(self, notice):
        data = notice.model_dump(mode='json')
        # All scope resolution is parameterized and constrained to the actual supplier and delivery window.
        lots = self.g.query('''MATCH (s:Supplier {id:$supplier})-[:DELIVERED]->(l:IngredientLot)
            WHERE l.delivered_at >= $start AND l.delivered_at <= $end
            RETURN l.id''', {'supplier': data['supplier'], 'start': data['effective_from'], 'end': data['effective_to']})
        matched = [r[0] for r in lots if any(r[0] == x if data['scope'] == 'exact' else r[0].startswith(x) for x in data['lots'])]
        if not matched:
            raise ValueError('No delivered lots match supplier, effective dates and identifiers; scope cannot be inferred.')
        if data['scope'] == 'exact' and set(matched) != set(data['lots']):
            raise ValueError('Some lot identifiers do not match the supplier and effective date range.')
        existing = self.g.query('MATCH (n:ChangeNotice {id:$id}) RETURN n.payload', {'id': data['id']})
        payload = json.dumps(data, sort_keys=True)
        if existing:
            if existing[0][0] != payload:
                raise ValueError('Notice id already exists with different immutable source facts; use a new id.')
            return self.g.get(data['id'])
        self.g.node('ChangeNotice', data['id'], {**{k: v for k, v in data.items() if k != 'lots'},
            'name': data['title'], 'payload': payload, 'received_at': now()})
        evidence = uid('source')
        self.g.node('EvidenceDocument', evidence, {'name': 'Supplier corrective declaration', 'content': data['evidence'], 'at': now(), 'provenance': 'User-submitted synthetic notice'})
        self.g.edge(data['id'], 'SUPPORTED_BY', evidence)
        self.g.edge(data['supplier'], 'ISSUED', data['id'])
        if data['supplier'] == 'SUP-1':
            self.g.edge(data['id'], 'CORRECTS', 'SPEC-A-v1')
            self.g.edge(data['id'], 'SUPPORTED_BY', 'SPEC-A-v2')
        for lot in matched:
            self.g.edge(data['id'], 'APPLIES_TO_LOT', lot, {'certainty': 'confirmed' if data['scope'] == 'exact' else 'unresolved',
                'valid_from': data['effective_from'], 'valid_to': data['effective_to'], 'source': evidence})
        return self.g.get(data['id'])

    def create(self, notice, mode='auto', background=True):
        with self.lock:
            self.g.get(notice)
            active = self.g.query("MATCH (i:Investigation) WHERE i.status='running' RETURN i.id")
            if active:
                raise ValueError('An investigation is already running; wait for its tools to finish.')
            mode = self.mode if mode == 'auto' else mode
            if mode == 'llm' and not os.getenv('OPENAI_API_KEY'):
                raise ValueError('LLM mode requires OPENAI_API_KEY. Select offline mode explicitly.')
            inv = uid('INV')
            self.g.node('Investigation', inv, {'name': f'Investigation · {notice}', 'notice': notice,
                'mode': mode, 'status': 'running', 'created_at': now()})
            self.g.edge(inv, 'INVESTIGATES', notice)
            if background:
                self.pool.submit(self.run, inv)
            else:
                self.run(inv)
            return self.g.get(inv)

    def tool(self, inv, agent, name, fn):
        start = time.perf_counter()
        self.g.event(inv, agent, name, 'Tool invocation started', status='running')
        try:
            result = fn()
            detail = json.dumps(result, default=str)
            self.g.event(inv, agent, name, detail[:14000], round((time.perf_counter()-start)*1000, 2))
            return result
        except Exception as exc:
            self.g.event(inv, agent, name, str(exc), round((time.perf_counter()-start)*1000, 2), 'failed')
            raise

    def impact(self, inv, record=False):
        investigation = self.g.get(inv)
        if investigation['mode'] == 'restricted':
            raise ValueError('Connected graph context is disabled. Impact classification and containment are unavailable.')
        notice = self.g.get(investigation['notice'])
        rows = self.g.query(IMPACT_QUERY, {'notice': notice['id']}, inv if record else None)
        batches = {}
        for b, product, facility, lot, consumption, pack, declared, recipe, scope, ship, shipstate, order, customer, reservation, manufactured in rows:
            entry = batches.setdefault(b, dict(id=b, product=product, facility=facility, lots=[], exposures=[],
                packaging=pack, declared=declared or [], recipe=recipe, shipments=[], reservations=[], manufactured_at=manufactured))
            if lot not in entry['lots']:
                entry['lots'].append(lot)
            if scope and {'lot': lot, 'consumption': consumption, 'notice': scope} not in entry['exposures']:
                entry['exposures'].append({'lot': lot, 'consumption': consumption, 'notice': scope})
            if ship and shipstate != 'canceled' and ship not in [s['id'] for s in entry['shipments']]:
                entry['shipments'].append({'id': ship, 'status': shipstate, 'order': order, 'customer': customer})
            if reservation and reservation not in entry['reservations']:
                entry['reservations'].append(reservation)
        # A batch with missing source facts must never disappear from coverage.
        all_batches = self.g.list('ProductionBatch')
        for b in all_batches:
            if b['id'] not in batches:
                batches[b['id']] = dict(id=b['id'], product='Source data incomplete', facility='Unknown', lots=[], exposures=[],
                    packaging=None, declared=[], recipe=None, shipments=[], reservations=[], source_incomplete=True)
        for entry in batches.values():
            classification, rationale = classify(entry['exposures'], entry['declared'], notice['allergen'])
            if entry.get('source_incomplete'):
                classification, rationale = 'uncertain', 'Required historical consumption or packaging record is missing.'
            entry.update(classification=classification, rationale=rationale, hold_required=requires_hold(classification),
                evidence=[notice['id'], *entry['lots'], entry['id'], entry['recipe'], entry['packaging'], 'QA-17'])
        return sorted(batches.values(), key=lambda b: b['id'])

    def investigate(self, inv):
        batches = self.impact(inv, record=True)
        for b in batches:
            fid = f'{inv}:{b["id"]}'
            self.g.node('Finding', fid, {'name': f'{b["id"]} · {b["classification"]}', 'investigation': inv,
                'batch': b['id'], 'classification': b['classification'], 'rationale': b['rationale'], 'payload': json.dumps(b), 'observed_at': now()})
            self.g.edge(inv, 'HAS_FINDING', fid)
            self.g.edge(fid, 'AFFECTS', b['id'])
            self.g.edge(fid, 'SUPPORTED_BY', 'QA-17')
        counts = {state: sum(b['classification'] == state for b in batches) for state in ['confirmed', 'uncertain', 'unaffected']}
        self.g.node('Investigation', inv, {'counts': json.dumps(counts), 'report_ready': True})
        return counts

    def recall(self, inv):
        n = self.g.get(self.g.get(inv)['notice'])
        memories = retrieve(self.g, n, inv)
        self.g.node('Investigation', inv, {'retrieved_memory': json.dumps(memories)})
        for memory in memories:
            self.g.edge(inv, 'RETRIEVED', memory['id'])
        return memories

    def plan(self, inv):
        findings = self.findings(inv)
        if not findings:
            raise ValueError('Investigator has not persisted findings yet.')
        total = 0
        procurement = f'{inv}:task:supplier'
        self.g.node('AgentTask', procurement, {'name': 'Reconcile supplier corrective evidence', 'investigation': inv, 'status': 'open', 'at': now()})
        self.g.edge(procurement, 'ASSIGNED_TO', 'EMP-1')
        self.g.edge(procurement, 'DEPENDS_ON', self.g.get(inv)['notice'])
        for b in findings:
            if not b['hold_required']:
                continue
            aid = f'{inv}:action:{b["id"]}'
            task = f'{inv}:task:{b["id"]}'
            self.g.node('ProposedAction', aid, {'name': f'Contain {b["id"]}', 'investigation': inv, 'batch': b['id'],
                'action': 'QA_HOLD', 'status': 'proposed', 'owner': 'Dr. Maya Chen',
                'recovery': 'Reconcile lot documentation' if b['classification'] == 'uncertain' else 'Review controlled relabeling/rework or authorized disposal',
                'prerequisites': sorted(RELEASE_PREREQUISITES)})
            self.g.edge(inv, 'PROPOSES', aid)
            self.g.edge(aid, 'AFFECTS', b['id'])
            self.g.edge(aid, 'REQUIRES_APPROVAL', 'QA-17')
            self.g.node('AgentTask', task, {'name': 'Resolve provenance' if b['classification'] == 'uncertain' else 'Review packaging and disposition',
                'investigation': inv, 'batch': b['id'], 'status': 'open', 'at': now()})
            self.g.edge(task, 'ASSIGNED_TO', 'EMP-0')
            self.g.edge(task, 'DEPENDS_ON', aid)
            for shipment in b['shipments']:
                for department, owner, name in [('warehouse', 'EMP-2', 'Confirm allocation restriction'), ('customer-service', 'EMP-3', 'Review affected order communication')]:
                    related = f'{inv}:task:{department}:{shipment["id"]}'
                    self.g.node('AgentTask', related, {'name': name, 'investigation': inv, 'batch': b['id'], 'shipment': shipment['id'], 'status': 'open', 'at': now()})
                    self.g.edge(related, 'ASSIGNED_TO', owner)
                    self.g.edge(related, 'DEPENDS_ON', aid)
            total += 1
        return {'proposals': total, 'human_approval_required_for': ['release', 'dispose'], 'policy': 'QA-17'}

    def findings(self, inv):
        rows = self.g.query('MATCH (i:Investigation {id:$inv})-[:HAS_FINDING]->(f:Finding) RETURN f.payload ORDER BY f.batch', {'inv': inv})
        return [json.loads(r[0]) for r in rows]

    def run(self, inv):
        started = time.perf_counter()
        try:
            mode = self.g.get(inv)['mode']
            if mode == 'restricted':
                self.g.event(inv, 'investigator', 'restricted_context', 'Only direct notice is available. No graph traversal, classification or ERP action is permitted.', status='blocked')
                self.g.node('Investigation', inv, {'status': 'blocked', 'duration_ms': round((time.perf_counter()-started)*1000, 2)})
                return
            if mode == 'llm':
                from backend.agents.llm import run_investigation
                run_investigation(self, inv)
            else:
                self.tool(inv, 'memory', 'retrieve_applicable_memory', lambda: self.recall(inv))
                self.tool(inv, 'investigator', 'traverse_historical_consumption', lambda: self.investigate(inv))
                self.tool(inv, 'planner', 'propose_recovery', lambda: self.plan(inv))
            if not self.g.get(inv).get('report_ready'):
                raise ValueError('Agent did not produce a graph-backed report.')
            self.g.node('Investigation', inv, {'status': 'awaiting_containment', 'duration_ms': round((time.perf_counter()-started)*1000, 2)})
        except Exception as exc:
            self.g.node('Investigation', inv, {'status': 'failed', 'error': str(exc), 'duration_ms': round((time.perf_counter()-started)*1000, 2)})

    def contain(self, inv):
        with self.lock:
            if self.g.get(inv)['status'] not in {'awaiting_containment', 'contained', 'verified', 'discrepancy'}:
                raise ValueError('A completed investigation is required before containment.')
            def apply():
                # Recompute from live graph instead of trusting stale agent proposals.
                batches = self.impact(inv, record=True)
                for b in batches:
                    if b['hold_required']:
                        self.erp.hold(b['id'], inv)
                        self.g.node('ProposedAction', f'{inv}:action:{b["id"]}', {'status': 'executed', 'executed_at': now()})
                return {'required': sum(b['hold_required'] for b in batches), 'erp': 'Persisted', 'policy': 'QA-17'}
            result = self.tool(inv, 'coordinator', 'apply_erp_containment', apply)
            self.g.node('Investigation', inv, {'status': 'contained'})
            return result

    def attest(self, request):
        with self.lock:
            if request.role != 'QA':
                raise PermissionError('QA authority required for evidence attestation.')
            b = next((b for b in self.findings(request.investigation) if b['id'] == request.batch), None)
            if not b or not b['hold_required']:
                raise ValueError('No disposition request exists for this batch.')
            identifier = uid('qa-evidence')
            self.g.node('EvidenceDocument', identifier, {'name': request.prerequisite.replace('_', ' '), 'investigation': request.investigation,
                'batch': request.batch, 'prerequisite': request.prerequisite, 'content': request.reason, 'authority': 'EMP-0', 'at': now(), 'provenance': 'Explicit human QA simulation attestation'})
            self.g.edge(f'{request.investigation}:action:{request.batch}', 'SUPPORTED_BY', identifier)
            self.g.edge(identifier, 'APPROVED_BY', 'EMP-0')
            return self.g.get(identifier)

    def evidence(self, inv, batch):
        return [r[0] for r in self.g.query('''MATCH (e:EvidenceDocument) WHERE e.investigation=$inv AND e.batch=$batch
            RETURN properties(e) ORDER BY e.at''', {'inv': inv, 'batch': batch})]

    def decide(self, req):
        with self.lock:
            b = next((b for b in self.impact(req.investigation, record=True) if b['id'] == req.batch), None)
            if not b or not b['hold_required']:
                raise ValueError('This batch has no hold requirement under the current notice.')
            evidence = self.evidence(req.investigation, req.batch)
            validate_disposition(req.role, req.decision, b['classification'], [e['prerequisite'] for e in evidence], req.reason)
            previous = [d for d in self.erp.snapshot()['dispositions'] if d['batch'] == req.batch and d['investigation'] == req.investigation]
            if previous and req.decision in {'release', 'dispose'}:
                if previous[0]['decision'] != req.decision:
                    raise ValueError('Terminal disposition cannot be changed.')
                return self.g.get(previous[0]['approval'])
            active = any(h['batch'] == req.batch and h['investigation'] == req.investigation and h['active'] for h in self.erp.snapshot()['holds'])
            if req.decision in {'release', 'dispose'} and not active:
                raise ValueError('Apply containment before approving a disposition.')
            aid = uid('decision')
            self.g.node('ApprovalDecision', aid, {'name': f'{req.decision.title()} {req.batch}', **req.model_dump(), 'at': now(),
                'authority': 'EMP-0', 'evidence_ids': [e['id'] for e in evidence], 'policy': 'QA-17'})
            self.g.edge(aid, 'AFFECTS', req.batch)
            self.g.edge(aid, 'APPROVED_BY', 'EMP-0')
            self.g.edge(req.investigation, 'HAS_DECISION', aid)
            if req.decision in {'release', 'dispose'}:
                self.erp.disposition(req.batch, req.investigation, req.decision, aid)
                self.g.node('AgentTask', f'{req.investigation}:task:{req.batch}', {'status': 'resolved', 'resolved_at': now()})
                self.g.edge(f'{req.investigation}:action:{req.batch}', 'RESOLVED_BY', aid)
            self.g.node('Investigation', req.investigation, {'verification_stale': True})
            prior = self.g.query('MATCH (m:MemoryEpisode {id:$id}) RETURN m.id', {'id': f'EP-{req.investigation}'})
            if prior:
                self.g.node('MemoryEpisode', f'EP-{req.investigation}', {'outdated': True})
            return self.g.get(aid)

    def verify(self, inv):
        with self.lock:
            return self.tool(inv, 'verifier', 'independently_verify_erp', lambda: self._verify(inv))

    def _verify(self, inv):
        live = self.impact(inv, record=True)
        snapshot = self.erp.snapshot()
        holds = {h['batch'] for h in snapshot['holds'] if h['investigation'] == inv and h['active']}
        dispositions = {d['batch']: d for d in snapshot['dispositions'] if d['investigation'] == inv}
        errors, covered = [], 0
        for b in live:
            batch = b['id']
            if b['hold_required']:
                disp = dispositions.get(batch)
                if disp:
                    try:
                        decision = self.g.get(disp['approval'])
                        docs = [self.g.get(e) for e in decision.get('evidence_ids', [])]
                        validate_disposition(decision['role'], decision['decision'], b['classification'], [e['prerequisite'] for e in docs], decision['reason'])
                        if decision['batch'] != batch or decision['investigation'] != inv or decision['decision'] != disp['decision']:
                            raise ValueError('ERP disposition and graph approval disagree')
                        expected = 'DISPOSED' if disp['decision'] == 'dispose' else 'QA_HOLD' if any(h['batch'] == batch and h['active'] for h in snapshot['holds']) else 'RELEASED'
                        if snapshot['inventory'].get(batch) != expected:
                            raise ValueError('ERP terminal inventory state disagrees with approval')
                        covered += 1
                    except (ValueError, PermissionError) as exc:
                        errors.append({'batch': batch, 'problem': f'Invalid disposition: {exc}'})
                elif batch not in holds or snapshot['inventory'].get(batch) not in {'QA_HOLD', 'DISPOSED'}:
                    errors.append({'batch': batch, 'problem': 'Required hold missing from ERP'})
                else:
                    covered += 1
            elif batch in holds:
                errors.append({'batch': batch, 'problem': 'Unnecessary hold caused by this notice'})
            if b['hold_required'] and batch not in dispositions:
                for shipment in b['shipments']:
                    if any(s['shipment'] == shipment['id'] and s['status'] == 'dispatched' for s in snapshot['dispatch']):
                        errors.append({'batch': batch, 'problem': 'Held batch was dispatched'})
        required = sum(b['hold_required'] for b in live)
        result = {'passed': not errors, 'required': required, 'covered': covered, 'coverage': covered/required if required else 1,
            'unresolved': sum(b['classification'] == 'uncertain' for b in live), 'discrepancies': errors,
            'resolution': 'Containment verified; QA resolution still pending' if any(b['hold_required'] and b['id'] not in dispositions for b in live) else 'All dispositions verified', 'at': now()}
        ver = uid('verification')
        self.g.node('Verification', ver, {'name': 'Independent containment verification', 'investigation': inv, 'passed': result['passed'], 'payload': json.dumps(result), 'at': now()})
        self.g.edge(inv, 'VERIFIED_BY', ver)
        self.g.node('Investigation', inv, {'status': 'verified' if result['passed'] else 'discrepancy', 'verification_stale': False, 'verification': json.dumps(result)})
        if result['passed']:
            self.tool(inv, 'memory', 'persist_verified_episode', lambda: self.remember(inv, result))
        elif self.g.query('MATCH (m:MemoryEpisode {id:$id}) RETURN m.id', {'id': f'EP-{inv}'}):
            self.g.node('MemoryEpisode', f'EP-{inv}', {'outdated': True})
        return result

    def remember(self, inv, verification):
        investigation = self.g.get(inv)
        notice = self.g.get(investigation['notice'])
        ep = f'EP-{inv}'
        self.g.node('MemoryEpisode', ep, {'name': notice['title'], 'cause': 'undeclared_allergen', 'allergen': notice['allergen'],
            'supplier': notice['supplier'], 'verified': True, 'outdated': False, 'at': now(),
            'lesson': 'Historical lot traversal and packaging comparison determined containment. Independent ERP verification passed.',
            'scope': verification['resolution'], 'verification': json.dumps(verification), 'investigation': inv})
        self.g.edge(ep, 'LEARNED_FROM', inv)
        self.g.edge(ep, 'SUPPORTED_BY', notice['id'])
        self.g.edge(ep, 'ASSIGNED_TO', 'memory')
        procedure = f'PROC-{inv}'
        self.g.node('LearnedProcedure', procedure, {'name': 'Trace historical exposure before minimum containment',
            'active': True, 'allergen': notice['allergen'], 'cause': 'undeclared_allergen',
            'steps': ['Check supplier lot scope', 'Trace actual consumption', 'Compare historical declaration', 'Contain unknown exposure', 'Verify ERP execution independently'], 'at': now()})
        self.g.edge(procedure, 'LEARNED_FROM', ep)
        self.g.edge(procedure, 'SUPPORTED_BY', 'QA-17')
        return {'episode': ep, 'verified': True, 'resolution_complete': verification['resolution'] == 'All dispositions verified'}

    def dispatch(self, shipment):
        with self.lock:
            s = self.g.get(shipment)
            if s.get('status') != 'pending':
                raise ValueError('Only a pending shipment can be dispatched.')
            rows = self.g.query('MATCH (b:ProductionBatch)-[:INCLUDED_IN_SHIPMENT]->(s:Shipment {id:$id}) RETURN b.id', {'id': shipment})
            if not rows:
                raise ValueError('No known batch allocation; dispatch blocked.')
            inventory = self.erp.snapshot()['inventory']
            for row in rows:
                state = inventory.get(row[0], 'UNKNOWN')
                if state not in {'AVAILABLE', 'RELEASED'}:
                    raise ValueError(f'Dispatch blocked: {row[0]} is {state}.')
            # Require fresh graph-backed safety evaluation for every ingested notice.
            for n in self.g.list('ChangeNotice'):
                investigations = [i for i in self.g.list('Investigation') if i.get('notice') == n['id'] and i.get('report_ready')]
                if not investigations:
                    raise ValueError('An ingested notice has not been investigated; dispatch paused.')
                latest = sorted(investigations, key=lambda i: i['created_at'])[-1]
                risks = {b['id'] for b in self.impact(latest['id']) if b['hold_required']}
                for row in rows:
                    if row[0] in risks:
                        approved = [d for d in self.erp.snapshot()['dispositions'] if d['batch'] == row[0] and d['investigation'] == latest['id'] and d['decision'] == 'release']
                        if not approved:
                            raise ValueError(f'Dispatch blocked: {row[0]} has unresolved notified exposure.')
                        decision = self.g.get(approved[0]['approval'])
                        docs = [self.g.get(e) for e in decision.get('evidence_ids', [])]
                        live_batch = next(b for b in self.impact(latest['id']) if b['id'] == row[0])
                        validate_disposition(decision['role'], decision['decision'], live_batch['classification'], [e['prerequisite'] for e in docs], decision['reason'])
                        if decision['batch'] != row[0] or decision['investigation'] != latest['id'] or decision['decision'] != 'release':
                            raise ValueError('Dispatch blocked: ERP disposition does not match its graph approval.')
            self.erp.dispatch(shipment, [r[0] for r in rows])
            self.g.node('Shipment', shipment, {'status': 'dispatched'})
            return {'shipment': shipment, 'status': 'dispatched'}
