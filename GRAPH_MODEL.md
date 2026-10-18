# Actual graph model

Graph name: `speccascade`. Every node has `:Entity` and a concrete label, stable string `id`, `kind`, and `synthetic=true`. An index on Entity.id supports controlled lookups. The graph is stored by the official `falkordb` client; query parameters use its parameter mechanism.

| Layer | Concrete node labels |
| --- | --- |
| Supplier source | Supplier, SupplierSpecification, SpecificationVersion, ChangeNotice, Ingredient, IngredientLot, PurchaseOrder, EvidenceDocument |
| Manufacturing | Product, Recipe, RecipeVersion, ProductionBatch, ManufacturingFacility, PackagingVersion, AllergenDeclaration, QualityApproval |
| Distribution | Warehouse, InventoryReservation, Shipment, CustomerOrder, Customer |
| Organization | Policy, Employee, Department |
| Agent execution | Investigation, Agent, AgentTask, ProposedAction, Finding, AgentEvent, QueryExecution |
| Decisions and learning | ApprovalDecision, Verification, MemoryEpisode, LearnedProcedure |
| Initialization | Dataset |

## Causal paths

```text
Supplier -ISSUED-> ChangeNotice -APPLIES_TO_LOT-> IngredientLot
ProductionBatch -CONSUMED_LOT-> IngredientLot -SUPPORTED_BY-> SpecificationVersion
ProductionBatch -USED_RECIPE_VERSION-> RecipeVersion
ProductionBatch -PACKAGED_WITH-> PackagingVersion -HAS_DECLARATION-> AllergenDeclaration
ProductionBatch -INCLUDED_IN_SHIPMENT-> Shipment -FULFILLS-> CustomerOrder -ORDERED_BY-> Customer
ProductionBatch -ALLOCATED_TO-> InventoryReservation -DEPENDS_ON-> Shipment
ProductionBatch -STORED_AT-> Warehouse
Investigation -HAS_FINDING-> Finding -AFFECTS-> ProductionBatch
Finding -SUPPORTED_BY-> Policy
Investigation -PROPOSES-> ProposedAction -AFFECTS-> ProductionBatch
ProposedAction -REQUIRES_APPROVAL-> Policy
AgentTask -ASSIGNED_TO-> Employee -MEMBER_OF-> Department
AgentTask -DEPENDS_ON-> ProposedAction
ProposedAction -SUPPORTED_BY-> EvidenceDocument -APPROVED_BY-> Employee
ApprovalDecision -AFFECTS-> ProductionBatch
ApprovalDecision -APPROVED_BY-> Employee
ProposedAction -RESOLVED_BY-> ApprovalDecision
Investigation -VERIFIED_BY-> Verification
MemoryEpisode -LEARNED_FROM-> Investigation
Investigation -RETRIEVED-> MemoryEpisode
LearnedProcedure -LEARNED_FROM-> MemoryEpisode
```

Other source edges: SUPPLIES, HAS_SPECIFICATION, HAS_VERSION, SUPERSEDES, CONTRADICTS, DELIVERED, OF_INGREDIENT, RECEIVED_LOT, HAS_RECIPE, CONTAINS_INGREDIENT, OF_PRODUCT, PRODUCED_AT, APPROVED_BY, SUPPORTED_BY and CORRECTS. Workflow edges also include INVESTIGATES, HAS_EVENT, HAS_DECISION and ASSIGNED_TO.

## Provenance and time

CONSUMED_LOT records consumption certainty (`confirmed` or `unresolved`), MES source identifier and recorded time. A possible lot is represented explicitly by an unresolved consumption record, never treated as definite consumption. Notice applicability records supplier scope certainty, evidence source and effective validity window. Source delivery and production timestamps, immutable recipe/artwork versions, evidence provenance, observed finding timestamps, proposal execution times and signed decision timestamps are retained.

The initial supplier correction concerns two exact delivered lots. Four batches have unresolved consumption documentation. Other lots from the same supplier and recipes from the same families remain distinct. The fixture stores expected labels independently of causal seed facts. `IMPACT_QUERY` reads live source facts, and policy comparison decides confirmed/uncertain/unaffected. Current recipe membership cannot override historical consumption.

The ERP state is deliberately external to the graph: graph actions express intended/executed operations, while SQLite records their actual inventory consequences. The verifier compares both, rather than treating a graph action node as proof that an ERP write succeeded.

Memory episodes preserve incident links, verification payload and scope. They link to investigations that in turn retain findings, source notices, events, actions and decisions. Retrieval excludes outdated episodes and never authorizes reuse of prior batch clearances. Historical seeded memories and closeouts are labeled synthetic source records.
