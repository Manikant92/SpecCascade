# Executable Cypher catalog

Authoritative definitions: `backend/graph/queries.py` and `backend/graph/store.py::IMPACT_QUERY`. Standalone Cypher statements are available in `docs/cypher/` for inspection in FalkorDB Browser. The API exposes evidence paths but does not accept arbitrary Cypher.

| Query | Purpose |
| --- | --- |
| 01_notice_lots | Supplier notice → exact applicable lots, source certainty and validity dates |
| 02_consuming_batches | Ingredient lot → historical consuming batches and MES provenance |
| 03_historical_packaging | Batch → actual artwork version → allergen declaration |
| 04_inventory_reservations | Batch warehouse and inventory reservation context; actual ERP state is read separately |
| 05_customer_dependency | Batch → shipment → order → customer |
| 06_classification_facts | Joined multi-hop historical facts for containment policy evaluation |
| 07_uncertain_provenance | Unresolved supplier scope or historical consumption |
| 08_action_downstream | Proposed action → batch → shipment/order dependencies |
| 09_hold_evidence | Investigation finding → batch and policy rationale |
| 10_qa_prerequisites | Required policy prerequisites and explicit human evidence |
| 11_tasks_and_owners | Outstanding tasks and responsible employee |
| 12_similar_memory | Verified active episodes with checked causal relevance |
| 13_agent_shared_state | Persisted findings and actual tool events available across agents |
| 14_verification_coverage | Recorded verifier outcome and actual ERP comparison payload |

The full classification query lives in `docs/cypher/06_classification_facts.cypher`. Core path:

```cypher
MATCH (n:ChangeNotice {id:$notice})-[a:APPLIES_TO_LOT]->(l:IngredientLot)
MATCH (b:ProductionBatch)-[c:CONSUMED_LOT]->(l)
MATCH (b)-[:PACKAGED_WITH]->(p:PackagingVersion)-[:HAS_DECLARATION]->(d:AllergenDeclaration)
OPTIONAL MATCH (b)-[:INCLUDED_IN_SHIPMENT]->(s:Shipment)-[:FULFILLS]->(o:CustomerOrder)-[:ORDERED_BY]->(customer:Customer)
RETURN b.id,l.id,c.certainty,a.certainty,p.id,d.allergens,s.id,o.id,customer.name
```

This smaller example discovers notified paths only. The actual impact query covers **all** manufacturing batches, uses optional notice applicability to preserve unaffected rows and detects missing source records conservatively. This is necessary to measure false-positive containment and distinguish similar recipes consuming other lots. LLM tools cannot replace these traversals with remembered answers.
