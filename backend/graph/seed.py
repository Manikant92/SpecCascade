from .store import now

PRODUCTS = ['Oat & Honey Bar', 'Cocoa Crunch', 'Almond Granola', 'Berry Breakfast',
            'Maple Oat Bites', 'Cinnamon Squares', 'Coconut Clusters', 'Seed Trail Mix',
            'Vanilla Protein Bar', 'Apple Oat Cookie', 'Caramel Crisps', 'Peanut Energy Bar']


def seed(g):
    if g.query("MATCH (n:Dataset {id:'northstar-v1'}) RETURN n.id"):
        return
    g.query("CREATE INDEX FOR (n:Entity) ON (n.id)")
    for i, name in enumerate(['Aster Ingredients', 'Valley Harvest', 'Meridian Naturals']):
        g.node('Supplier', f'SUP-{i+1}', {'name': name})
    for i, name in enumerate(['Leeds · Plant 01', 'Bristol · Plant 02']):
        g.node('ManufacturingFacility', f'FAC-{i+1}', {'name': name})
        g.node('Warehouse', f'WH-{i+1}', {'name': f'{name.split(" ·")[0]} Distribution'})
    for i, name in enumerate(['Quality Assurance', 'Procurement', 'Warehouse Operations', 'Customer Service']):
        g.node('Department', f'DEP-{i}', {'name': name})
        g.node('Employee', f'EMP-{i}', {'name': ['Dr. Maya Chen', 'Oliver Reed', 'Amara Singh', 'Leo Walsh'][i], 'role': 'QA' if i == 0 else name})
        g.edge(f'EMP-{i}', 'MEMBER_OF', f'DEP-{i}')
    for agent in ['investigator', 'coordinator', 'verifier', 'memory', 'planner']:
        g.node('Agent', agent, {'name': agent.title()})
    g.node('Policy', 'QA-17', {'name': 'Undeclared allergen containment', 'version': 1,
        'rule': 'Hold confirmed undeclared exposure and unresolved exposure. Human QA disposition only.',
        'release_prerequisites': ['supplier_reconciliation', 'label_review', 'quality_review', 'relabeling_validation']})
    for i, name in enumerate(['Oats', 'Cocoa blend', 'Almonds', 'Honey', 'Berries', 'Maple syrup', 'Cinnamon', 'Coconut', 'Pumpkin seeds', 'Peanut butter']):
        g.node('Ingredient', f'ING-{i}', {'name': name})
        g.edge(f'SUP-{1 if i < 2 else 2 if i < 6 else 3}', 'SUPPLIES', f'ING-{i}')
    for lot, ingredient, supplier, date in [('LOT-A101', 'ING-1', 'SUP-1', '2026-09-01'),
            ('LOT-A102', 'ING-1', 'SUP-1', '2026-09-08'), ('LOT-A103', 'ING-1', 'SUP-1', '2026-09-18'),
            ('LOT-A090', 'ING-1', 'SUP-1', '2026-08-01'), ('LOT-V201', 'ING-0', 'SUP-2', '2026-09-03'),
            ('LOT-M301', 'ING-7', 'SUP-3', '2026-09-04')]:
        g.node('IngredientLot', lot, {'name': lot, 'delivered_at': date, 'supplier': supplier})
        g.node('PurchaseOrder', f'PO-{lot}', {'name': f'Purchase {lot}'})
        g.edge(lot, 'OF_INGREDIENT', ingredient)
        g.edge(supplier, 'DELIVERED', lot)
        g.edge(supplier, 'SUPPLIES', ingredient)
        g.edge(f'PO-{lot}', 'RECEIVED_LOT', lot)
        g.edge(lot, 'SUPPORTED_BY', 'SPEC-A-v1')  # linked again after spec creation
    g.node('SupplierSpecification', 'SPEC-A', {'name': 'Cocoa blend supplier specification'})
    g.edge('SUP-1', 'HAS_SPECIFICATION', 'SPEC-A')
    for v, allergens in [(1, []), (2, ['milk'])]:
        g.node('SpecificationVersion', f'SPEC-A-v{v}', {'name': f'Cocoa specification v{v}', 'allergens': allergens,
            'effective_at': '2026-08-01' if v == 1 else '2026-09-01'})
        g.edge('SPEC-A', 'HAS_VERSION', f'SPEC-A-v{v}')
    g.edge('SPEC-A-v2', 'SUPERSEDES', 'SPEC-A-v1')
    g.edge('SPEC-A-v2', 'CONTRADICTS', 'SPEC-A-v1')
    for lot in ['LOT-A101', 'LOT-A102', 'LOT-A103', 'LOT-A090']:
        g.edge(lot, 'SUPPORTED_BY', 'SPEC-A-v1')
    for i, name in enumerate(PRODUCTS):
        p = f'PROD-{i+1:02}'
        g.node('Product', p, {'name': name, 'category': 'Breakfast & snacks'})
        g.node('Recipe', f'RECIPE-{i}', {'name': f'{name} recipe'})
        g.edge(p, 'HAS_RECIPE', f'RECIPE-{i}')
        for v in [1, 2]:
            r = f'RECIPE-{i}-v{v}'
            g.node('RecipeVersion', r, {'name': f'{name} v{v}', 'valid_from': '2026-01-01' if v == 1 else '2026-09-15'})
            g.edge(f'RECIPE-{i}', 'HAS_VERSION', r)
            g.edge(r, 'CONTAINS_INGREDIENT', 'ING-1')
            pack, dec = f'PACK-{i}-v{v}', f'DECL-{i}-v{v}'
            g.node('PackagingVersion', pack, {'name': f'{name} artwork v{v}', 'version': v})
            g.node('AllergenDeclaration', dec, {'name': 'Allergen declaration', 'allergens': ['almond'] if i == 2 else []})
            g.edge(pack, 'HAS_DECLARATION', dec)
            g.node('QualityApproval', f'QA-{i}-v{v}', {'name': 'Historical artwork approval', 'status': 'approved', 'at': '2026-08-01'})
            g.edge(pack, 'APPROVED_BY', f'QA-{i}-v{v}')
            g.edge(f'QA-{i}-v{v}', 'ASSIGNED_TO', 'EMP-0')
    for i in range(1, 121):
        b, prod = f'B-{i:03}', (i-1) % 12
        # Seed causal facts only. The engine never reads index ranges or expected labels.
        lot = 'LOT-A101' if i <= 12 else 'LOT-A102' if i <= 28 else 'LOT-A103' if i <= 40 else 'LOT-A090' if i <= 72 else 'LOT-V201' if i <= 96 else 'LOT-M301'
        certainty = 'unresolved' if 25 <= i <= 28 else 'confirmed'
        version = 1 if i % 3 else 2
        g.node('ProductionBatch', b, {'name': b, 'manufactured_at': '2026-09-20', 'units': 2400, 'source_record': f'MES-{i:04}'})
        g.edge(b, 'OF_PRODUCT', f'PROD-{prod+1:02}')
        g.edge(b, 'PRODUCED_AT', f'FAC-{1+(i%2)}')
        g.edge(b, 'STORED_AT', f'WH-{1+(i%2)}')
        g.edge(b, 'USED_RECIPE_VERSION', f'RECIPE-{prod}-v{version}')
        g.edge(b, 'PACKAGED_WITH', f'PACK-{prod}-v{version}')
        g.edge(b, 'CONSUMED_LOT', lot, {'certainty': certainty, 'source': f'MES-{i:04}', 'recorded_at': '2026-09-20'})
        g.node('EvidenceDocument', f'MES-{i:04}', {'name': 'Manufacturing lot consumption record', 'state': certainty, 'provenance': 'Synthetic MES export'})
        g.edge(b, 'SUPPORTED_BY', f'MES-{i:04}')
        if i % 4 == 1:
            s, o, c = f'SHIP-{i:03}', f'ORDER-{i:03}', f'CUS-{i%5}'
            g.node('Customer', c, {'name': ['Greenway Retail', 'Fresh Basket', 'Urban Pantry', 'Daily Market', 'North Foods'][i%5]})
            g.node('CustomerOrder', o, {'name': o, 'units': 1200})
            g.node('Shipment', s, {'name': s, 'status': 'pending', 'planned_at': '2026-10-16'})
            g.node('InventoryReservation', f'RES-{i:03}', {'name': 'Customer reservation', 'units': 1200})
            g.edge(b, 'INCLUDED_IN_SHIPMENT', s)
            g.edge(s, 'FULFILLS', o)
            g.edge(o, 'ORDERED_BY', c)
            g.edge(b, 'ALLOCATED_TO', f'RES-{i:03}')
            g.edge(f'RES-{i:03}', 'DEPENDS_ON', s)
    for i, allergen in [(1, 'milk'), (2, 'sesame')]:
        ep = f'EP-HIST-{i}'
        g.node('Investigation', f'INV-HIST-{i}', {'name': 'Historical synthetic incident', 'status': 'verified'})
        g.node('MemoryEpisode', ep, {'name': f'Historical {allergen} correction', 'cause': 'undeclared_allergen',
            'allergen': allergen, 'supplier': 'SUP-1', 'verified': True, 'outdated': False,
            'at': '2026-07-01', 'lesson': 'Trace historical lot consumption; hold uncertain exposure; reconcile artwork independently.',
            'scope': 'Procedure only. Historical lot decisions do not apply to new lots.'})
        g.edge(ep, 'LEARNED_FROM', f'INV-HIST-{i}')
        g.node('Verification', f'VER-HIST-{i}', {'name': 'Historical QA closeout', 'passed': True, 'synthetic_record': True})
        g.edge(f'INV-HIST-{i}', 'VERIFIED_BY', f'VER-HIST-{i}')
        g.node('LearnedProcedure', f'PROC-{i}', {'name': 'Version-aware allergen response', 'active': True, 'allergen': allergen})
        g.edge(f'PROC-{i}', 'LEARNED_FROM', ep)
    g.node('Dataset', 'northstar-v1', {'name': 'Northstar Foods · synthetic manufacturing dataset', 'created_at': now(), 'version': 1})
