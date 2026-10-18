"""Documented, executable query catalog; validate with scripts/verify_queries.py."""
from .store import IMPACT_QUERY

QUERIES = {
 '01_notice_lots': 'MATCH (n:ChangeNotice {id:$notice})-[a:APPLIES_TO_LOT]->(l:IngredientLot) RETURN l.id,a.certainty,a.valid_from,a.valid_to',
 '02_consuming_batches': 'MATCH (l:IngredientLot {id:$lot})<-[c:CONSUMED_LOT]-(b:ProductionBatch) RETURN b.id,c.certainty,c.source',
 '03_historical_packaging': 'MATCH (b:ProductionBatch {id:$batch})-[:PACKAGED_WITH]->(p:PackagingVersion)-[:HAS_DECLARATION]->(d:AllergenDeclaration) RETURN p.id,d.id,d.allergens',
 '04_inventory_reservations': 'MATCH (b:ProductionBatch {id:$batch})-[:STORED_AT]->(w:Warehouse) OPTIONAL MATCH (b)-[:ALLOCATED_TO]->(r:InventoryReservation) RETURN w.id,r.id,r.units',
 '05_customer_dependency': 'MATCH (b:ProductionBatch {id:$batch})-[:INCLUDED_IN_SHIPMENT]->(s:Shipment)-[:FULFILLS]->(o:CustomerOrder)-[:ORDERED_BY]->(c:Customer) RETURN s.id,s.status,o.id,c.name',
 '06_classification_facts': IMPACT_QUERY,
 '07_uncertain_provenance': "MATCH (n:ChangeNotice {id:$notice})-[a:APPLIES_TO_LOT]->(l)<-[c:CONSUMED_LOT]-(b) WHERE a.certainty='unresolved' OR c.certainty='unresolved' RETURN b.id,l.id,a.certainty,c.certainty",
 '08_action_downstream': 'MATCH (a:ProposedAction {id:$action})-[:AFFECTS]->(b) OPTIONAL MATCH (b)-[:INCLUDED_IN_SHIPMENT]->(s)-[:FULFILLS]->(o) RETURN a.id,b.id,s.id,o.id',
 '09_hold_evidence': 'MATCH (i:Investigation {id:$inv})-[:HAS_FINDING]->(f)-[:AFFECTS]->(b:ProductionBatch {id:$batch}) MATCH (f)-[:SUPPORTED_BY]->(p:Policy) RETURN f.rationale,f.payload,p.rule',
 '10_qa_prerequisites': 'MATCH (a:ProposedAction {id:$action})-[:REQUIRES_APPROVAL]->(p:Policy) OPTIONAL MATCH (a)-[:SUPPORTED_BY]->(e:EvidenceDocument) RETURN p.release_prerequisites,e.prerequisite,e.authority',
 '11_tasks_and_owners': "MATCH (t:AgentTask)-[:ASSIGNED_TO]->(e:Employee) WHERE t.investigation=$inv AND t.status='open' RETURN t.id,t.name,t.batch,e.name",
 '12_similar_memory': "MATCH (m:MemoryEpisode) WHERE m.verified=true AND m.outdated=false AND m.cause='undeclared_allergen' AND m.supplier=$supplier AND m.allergen=$allergen RETURN properties(m)",
 '13_agent_shared_state': 'MATCH (i:Investigation {id:$inv})-[:HAS_FINDING]->(f) OPTIONAL MATCH (i)-[:HAS_EVENT]->(e:AgentEvent) WHERE e.status=$status RETURN DISTINCT f.batch,f.classification,e.agent,e.tool LIMIT 200',
 '14_verification_coverage': 'MATCH (i:Investigation {id:$inv})-[:VERIFIED_BY]->(v:Verification) RETURN v.passed,v.payload,v.at',
}
