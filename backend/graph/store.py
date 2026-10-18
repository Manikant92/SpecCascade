"""The only dependency store. Every traversal is executed by FalkorDB."""
import os
import re
import time
import uuid
from datetime import datetime, timezone
from falkordb import FalkorDB


def now():
    return datetime.now(timezone.utc).isoformat()


def uid(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class GraphStore:
    def __init__(self, name=None):
        self.name = name or os.getenv("FALKORDB_GRAPH", "speccascade")
        self.db = FalkorDB(host=os.getenv("FALKORDB_HOST", "localhost"),
                          port=int(os.getenv("FALKORDB_PORT", "6379")),
                          password=os.getenv("FALKORDB_PASSWORD") or None,
                          socket_connect_timeout=3, socket_timeout=15)
        self.graph = self.db.select_graph(self.name)
        self.count = 0

    def query(self, text, params=None, investigation=None):
        start = time.perf_counter()
        result = self.graph.query(text, params or {})
        self.count += 1
        if investigation:
            self.node("QueryExecution", uid("query"), {
                "investigation": investigation, "query": text,
                "parameters": __import__('json').dumps(params or {}),
                "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                "rows": len(result.result_set), "at": now()})
        return result.result_set

    def node(self, label, identifier, props=None):
        assert re.fullmatch(r"[A-Za-z]+", label)
        data = {"id": identifier, "kind": label, "synthetic": True, **(props or {})}
        self.query(f"MERGE (n:Entity:{label} {{id:$id}}) SET n += $props", {"id": identifier, "props": data})
        return data

    def edge(self, source, rel, target, props=None):
        assert re.fullmatch(r"[A-Z_]+", rel)
        self.query(f"MATCH (a:Entity {{id:$a}}),(b:Entity {{id:$b}}) MERGE (a)-[r:{rel}]->(b) SET r += $props",
                   {"a": source, "b": target, "props": props or {}})

    def get(self, identifier):
        rows = self.query("MATCH (n:Entity {id:$id}) RETURN properties(n)", {"id": identifier})
        if not rows:
            raise ValueError(f"Graph entity {identifier} does not exist")
        return rows[0][0]

    def list(self, kind):
        return [r[0] for r in self.query("MATCH (n:Entity) WHERE n.kind=$kind RETURN properties(n) ORDER BY n.id", {"kind": kind})]

    def event(self, investigation, agent, tool, detail, duration=0, status="completed"):
        e = self.node("AgentEvent", uid("event"), {"investigation": investigation, "agent": agent,
            "tool": tool, "detail": detail, "duration_ms": duration, "status": status, "at": now()})
        self.edge(investigation, "HAS_EVENT", e["id"])
        self.edge(e["id"], "ASSIGNED_TO", agent)
        return e

    def subgraph(self, focus, hops=2):
        hops = max(1, min(hops, 3))
        rows = self.query(f"""MATCH p=(n:Entity {{id:$id}})-[*1..{hops}]-(m)
            WHERE (n.kind <> 'ProductionBatch' OR all(x IN nodes(p) WHERE x.kind <> 'ProductionBatch' OR x.id=$id))
            AND all(x IN nodes(p) WHERE x=n OR x=m OR NOT x.kind IN ['Warehouse','ManufacturingFacility','Product','Policy','Agent','Department','RecipeVersion'])
            WITH p LIMIT 300 UNWIND relationships(p) AS r
            RETURN DISTINCT properties(startNode(r)), type(r), properties(endNode(r)), id(r), properties(r)""", {"id": focus})
        nodes, edges = {}, {}
        for source, relation, target, edge_id, props in rows:
            for p in [source, target]:
                nodes[p['id']] = {"data": {**p, "label": p.get("name", p["id"])}}
            edges[edge_id] = {"data": {**props, "id": f"edge-{edge_id}", "source": source['id'], "target": target['id'], "label": relation}}
        if not nodes:
            p = self.get(focus)
            return {"nodes": [{"data": {**p, "label": p.get("name", p["id"])}}], "edges": []}
        return {"nodes": list(nodes.values()), "edges": list(edges.values())}


IMPACT_QUERY = """
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
"""
