
MATCH (b:ProductionBatch)-[c:CONSUMED_LOT]->(l:IngredientLot)
MATCH (b)-[:PACKAGED_WITH]->(p:PackagingVersion)-[:HAS_DECLARATION]->(d:AllergenDeclaration)
MATCH (b)-[:USED_RECIPE_VERSION]->(r:RecipeVersion)
MATCH (b)-[:OF_PRODUCT]->(product:Product)
MATCH (b)-[:PRODUCED_AT]->(f:ManufacturingFacility)
OPTIONAL MATCH (n:ChangeNotice {id:$notice})-[a:APPLIES_TO_LOT]->(l)
OPTIONAL MATCH (b)-[:INCLUDED_IN_SHIPMENT]->(s:Shipment)-[:FULFILLS]->(o:CustomerOrder)-[:ORDERED_BY]->(customer:Customer)
OPTIONAL MATCH (b)-[:ALLOCATED_TO]->(reservation:InventoryReservation)
RETURN b.id, product.name, f.name, l.id, c.certainty, p.id, d.allergens,
       r.id, a.certainty, s.id, s.status, o.id, customer.name, reservation.id, b.manufactured_at
ORDER BY b.id
