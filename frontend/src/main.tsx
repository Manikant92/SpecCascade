import React, { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import cytoscape from "cytoscape";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  CartesianGrid,
} from "recharts";
import {
  Activity,
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  Boxes,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock,
  Database,
  FileText,
  GitBranch,
  LayoutDashboard,
  Loader2,
  Maximize2,
  Network,
  Play,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  ShieldAlert,
  Sparkles,
  Truck,
  Users,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import "./style.css";

type Data = Record<string, any>;
const pages = [
  "Command Center",
  "Change Intelligence",
  "Live Impact Graph",
  "Agent Control Room",
  "Containment & ERP",
  "QA Approvals",
  "Agent Memory",
  "Evaluation & Proof",
];
const icons = [
  LayoutDashboard,
  FileText,
  Network,
  Activity,
  Boxes,
  ShieldCheck,
  GitBranch,
  Database,
];
const prerequisites = [
  "supplier_reconciliation",
  "label_review",
  "quality_review",
  "relabeling_validation",
];
async function api(path: string, body?: Data) {
  const r = await fetch(
    "/api" + path,
    body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : undefined,
  );
  const data = await r.json();
  if (!r.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  return data;
}
function Badge({ value }: { value: string }) {
  return (
    <span className={"badge " + value.toLowerCase().replaceAll(" ", "_")}>
      {value.replaceAll("_", " ")}
    </span>
  );
}
function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="empty">
      <Network size={30} />
      <p>{children}</p>
    </div>
  );
}
function Panel({
  title,
  eyebrow,
  action,
  children,
  className = "",
}: {
  title: string;
  eyebrow?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={"panel " + className}>
      <div className="panel-head">
        <div>
          {eyebrow && <span className="eyebrow">{eyebrow}</span>}
          <h3>{title}</h3>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
function GraphView({
  focus,
  setFocus,
  inv,
  compact = false,
}: {
  focus: string;
  setFocus: (s: string) => void;
  inv?: string;
  compact?: boolean;
}) {
  const el = useRef<HTMLDivElement>(null),
    cy = useRef<cytoscape.Core | null>(null);
  const [selected, setSelected] = useState<Data | null>(null),
    [error, setError] = useState(""),
    [kind, setKind] = useState("all"),
    [severity, setSeverity] = useState("all");
  const [elements, setElements] = useState<Data>({ nodes: [], edges: [] }),
    [risks, setRisks] = useState<Data>({});
  useEffect(() => {
    api("/graph?focus=" + encodeURIComponent(focus) + "&hops=2")
      .then(setElements)
      .catch((e) => setError(e.message));
    if (inv)
      api("/batches?investigation=" + inv).then((bs) =>
        setRisks(
          Object.fromEntries(bs.map((b: Data) => [b.id, b.classification])),
        ),
      );
  }, [focus, inv]);
  useEffect(() => {
    if (!el.current) return;
    const nodes = elements.nodes.map((n: Data) => ({
      data: { ...n.data, risk: risks[n.data.id] || "" },
    }));
    const instance = cytoscape({
      container: el.current,
      elements: [...nodes, ...elements.edges],
      style: [
        {
          selector: "node",
          style: {
            "background-color": "#cbd6d3",
            label: "data(label)",
            color: "#586e68",
            "font-size": 10,
            "text-valign": "bottom",
            "text-margin-y": 9,
            width: 23,
            height: 23,
            "border-width": 3,
            "border-color": "#fff",
            "text-max-width": "100px",
            "text-wrap": "ellipsis",
          },
        },
        {
          selector: "edge",
          style: {
            "line-color": "#d1ddd8",
            width: 1.3,
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "#d1ddd8",
            "arrow-scale": 0.65,
          },
        },
        {
          selector: 'node[kind="ProductionBatch"]',
          style: { "background-color": "#79aa98", shape: "round-rectangle" },
        },
        {
          selector: 'node[risk="confirmed"]',
          style: { "background-color": "#df6c55" },
        },
        {
          selector: 'node[risk="uncertain"]',
          style: { "background-color": "#e7b85b" },
        },
        {
          selector: 'node[kind="IngredientLot"]',
          style: { "background-color": "#789fcb", width: 33, height: 33 },
        },
        {
          selector: 'node[kind="ChangeNotice"]',
          style: {
            "background-color": "#e78f67",
            shape: "diamond",
            width: 38,
            height: 38,
          },
        },
        {
          selector: 'node[kind="PackagingVersion"]',
          style: {
            "background-color": "#aa9bc4",
            shape: "hexagon",
            width: 30,
            height: 30,
          },
        },
        {
          selector: 'node[kind="Shipment"]',
          style: { "background-color": "#71c3bb", shape: "round-rectangle" },
        },
        {
          selector: ":selected",
          style: { "border-color": "#174d3d", "border-width": 5 },
        },
        {
          selector: ".highlight",
          style: {
            "line-color": "#d27052",
            "target-arrow-color": "#d27052",
            width: 3,
          },
        },
      ],
      layout: {
        name: "concentric",
        concentric: (n: cytoscape.NodeSingular) =>
          n.id() === focus ? 10 : n.data("kind") === "IngredientLot" ? 5 : 1,
        levelWidth: () => 3,
        minNodeSpacing: 30,
        animate: false,
      } as any,
      minZoom: 0.2,
      maxZoom: 3,
    });
    cy.current = instance;
    instance.on("tap", "node", (e) => {
      const data = e.target.data();
      instance.edges().removeClass("highlight");
      e.target.connectedEdges().addClass("highlight");
      api(
        "/nodes/" +
          encodeURIComponent(data.id) +
          (inv ? "?investigation=" + inv : ""),
      )
        .then(setSelected)
        .catch((err) => setError(err.message));
    });
    instance.ready(() => instance.fit(undefined, 30));
    return () => {
      instance.destroy();
      cy.current = null;
    };
  }, [elements, risks, focus, inv]);
  useEffect(() => {
    if (!cy.current) return;
    cy.current.nodes().forEach((n) => {
      const visible =
        (kind === "all" || n.data("kind") === kind) &&
        (severity === "all" ||
          n.data("risk") === severity ||
          n.data("kind") !== "ProductionBatch");
      n.style("display", visible ? "element" : "none");
    });
  }, [kind, severity, elements, risks]);
  return (
    <div
      data-node-count={elements.nodes.length}
      className={"graph-wrap " + (compact ? "compact" : "")}
    >
      {!compact && (
        <div className="graph-filter">
          <button
            className="btn small"
            onClick={() =>
              api(
                "/nodes/" +
                  encodeURIComponent(focus) +
                  (inv ? "?investigation=" + inv : ""),
              )
                .then(setSelected)
                .catch((e) => setError(e.message))
            }
          >
            Inspect focused node
          </button>
          <label>
            Focus{" "}
            <input
              aria-label="Graph focus"
              value={focus}
              onChange={(e) => setFocus(e.target.value)}
            />
          </label>
          <select
            aria-label="Node type"
            value={kind}
            onChange={(e) => setKind(e.target.value)}
          >
            <option value="all">All node types</option>
            {Array.from(
              new Set<string>(elements.nodes.map((n: Data) => n.data.kind)),
            ).map((k) => (
              <option key={k}>{k}</option>
            ))}
          </select>
          <select
            aria-label="Risk filter"
            value={severity}
            onChange={(e) => setSeverity(e.target.value)}
          >
            <option value="all">All classifications</option>
            <option>confirmed</option>
            <option>uncertain</option>
            <option>unaffected</option>
          </select>
        </div>
      )}
      {error && <div className="error">{error}</div>}
      <div
        ref={el}
        className="graph-canvas"
        aria-label="Interactive FalkorDB dependency graph"
      />
      <div className="graph-legend">
        <span>
          <i className="dot coral" />
          Confirmed
        </span>
        <span>
          <i className="dot amber" />
          Uncertain
        </span>
        <span>
          <i className="dot green" />
          Unaffected
        </span>
        <span>
          <i className="dot blue" />
          Ingredient lot
        </span>
      </div>
      <div className="graph-controls">
        <button
          aria-label="Zoom in"
          onClick={() => cy.current?.zoom((cy.current?.zoom() || 1) * 1.3)}
        >
          <ZoomIn size={16} />
        </button>
        <button
          aria-label="Zoom out"
          onClick={() => cy.current?.zoom((cy.current?.zoom() || 1) / 1.3)}
        >
          <ZoomOut size={16} />
        </button>
        <button
          aria-label="Fit graph"
          onClick={() => cy.current?.fit(undefined, 30)}
        >
          <Maximize2 size={16} />
        </button>
      </div>
      {selected && (
        <div className="node-inspector">
          <button
            className="close"
            aria-label="Close inspector"
            onClick={() => setSelected(null)}
          >
            <X size={16} />
          </button>
          <span className="eyebrow">SOURCE GRAPH EVIDENCE</span>
          <h3>{selected.node.name || selected.node.id}</h3>
          <Badge value={selected.node.kind} />
          {selected.finding && (
            <>
              <p>{selected.finding.rationale}</p>
              <div className="evidence-path">
                {selected.finding.evidence.filter(Boolean).map((x: string) => (
                  <button key={x} onClick={() => setFocus(x)}>
                    {x}
                    <ChevronRight size={12} />
                  </button>
                ))}
              </div>
            </>
          )}
          <pre>{JSON.stringify(selected.node, null, 2)}</pre>
          <button
            className="btn small"
            onClick={() => {
              setFocus(selected.node.id);
              setSelected(null);
            }}
          >
            Expand relationships <ArrowUpRight size={14} />
          </button>
        </div>
      )}
    </div>
  );
}

function App() {
  const [page, setPage] = useState(0),
    [d, setD] = useState<Data | null>(null),
    [batches, setBatches] = useState<Data[]>([]),
    [memories, setMemories] = useState<Data[]>([]),
    [evaluation, setEvaluation] = useState<Data>({}),
    [decisions, setDecisions] = useState<Data[]>([]);
  const [graphReady, setGraphReady] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(""),
    [toast, setToast] = useState(""),
    [error, setError] = useState(""),
    [search, setSearch] = useState(""),
    [filter, setFilter] = useState("all"),
    [focus, setFocus] = useState("B-001"),
    [selectedInv, setSelectedInv] = useState("");
  const [notice, setNotice] = useState("NOTICE-001"),
    [scenario, setScenario] = useState("primary"),
    [batch, setBatch] = useState("B-001"),
    [role, setRole] = useState("Viewer"),
    [reason, setReason] = useState(""),
    [evidence, setEvidence] = useState<Data[]>([]),
    [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<Data>({
    id: "NOTICE-CUSTOM",
    supplier: "SUP-1",
    title: "Supplier allergen corrective notice",
    allergen: "milk",
    lots: "LOT-A101",
    effective_from: "2026-09-01",
    effective_to: "2026-09-30",
    scope: "exact",
    evidence: "Synthetic supplier corrective declaration",
  });
  const inv = d?.current?.id;
  const refresh = useCallback(async () => {
    try {
      const q = selectedInv ? "?investigation=" + selectedInv : "";
      const [dashboard, bs, ms, ev, ds] = await Promise.all([
        api("/dashboard" + q),
        api("/batches" + q),
        api("/memory"),
        api("/evaluation" + q),
        api("/approvals" + q),
      ]);
      setD(dashboard);
      setBatches(bs);
      setMemories(ms);
      setEvaluation(ev);
      setDecisions(ds);
      setGraphReady(true);
    } catch (e: any) {
      setGraphReady(false);
      setError(e.message);
    }
  }, [selectedInv]);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      await refresh();
      if (active) timer = setTimeout(poll, 4000);
    };
    poll();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [refresh]);
  useEffect(() => {
    if (inv)
      api("/evidence/" + inv + "/" + batch)
        .then(setEvidence)
        .catch((e) => setError(e.message));
  }, [inv, batch, decisions.length]);
  async function act(label: string, fn: () => Promise<any>) {
    setBusy(label);
    setToast("");
    setError("");
    try {
      const r = await fn();
      setToast(label + " · " + (r.status || "done"));
      await refresh();
      return r;
    } catch (e: any) {
      setToast("");
      setError(e.message);
    } finally {
      setBusy("");
    }
  }
  const inject = () =>
    act("Notice injected", async () => {
      const n = await api("/demo/inject/" + scenario, {});
      setNotice(n.id);
      setPage(1);
      return n;
    });
  const run = () =>
    act("Investigation started", async () => {
      const i = await api("/investigations", { notice, mode: "auto" });
      setSelectedInv(i.id);
      setPage(3);
      return i;
    });
  const hold = () =>
    inv &&
    act("Containment applied", () =>
      api("/investigations/" + inv + "/contain", {}),
    );
  const verify = () =>
    inv &&
    act("Verification complete", () =>
      api("/investigations/" + inv + "/verify", {}),
    );
  const currentNotice = d?.notices?.find(
    (n: Data) => n.id === (d?.current?.notice || notice),
  );
  const currentBatch = batches.find((b) => b.id === batch);
  const filtered = batches.filter(
    (b) =>
      (filter === "all" || b.classification === filter) &&
      (b.id + " " + b.product + " " + (b.lots || []).join(" "))
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  const pending = batches.filter((b) => b.hold_required);
  const pct = d && d.total ? Math.round((d.unaffected / d.total) * 100) : 0;
  const progress =
    d?.current?.status === "verified"
      ? 100
      : d?.current?.status === "contained"
        ? 75
        : d?.current?.status === "awaiting_containment"
          ? 50
          : d?.current?.status === "running"
            ? 25
            : 0;
  const events = d?.events || [];
  const controls = (
    <>
      <select
        aria-label="Demo scenario"
        value={scenario}
        onChange={(e) => setScenario(e.target.value)}
      >
        <option value="primary">01 · Undeclared milk</option>
        <option value="second">02 · Related lot correction</option>
        <option value="ambiguity">03 · Ambiguous identifiers</option>
      </select>
      <button className="btn primary" disabled={!!busy} onClick={inject}>
        <Plus size={16} />
        Inject Supplier Change
      </button>
    </>
  );
  return (
    <div className="app">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setPage(0);
          }}
        >
          <span className="logo">
            <GitBranch size={22} />
          </span>
          <span>
            SpecCascade<small>CONNECTED CHANGE INTELLIGENCE</small>
          </span>
        </a>
        <div className="workspace">
          <div className="workspace-icon">N</div>
          <div>
            <strong>Northstar Foods</strong>
            <small>Manufacturing workspace</small>
          </div>
          <ChevronRight size={14} />
        </div>
        <span className="nav-label">OPERATIONS</span>
        <nav>
          {pages.map((p, i) => {
            const Icon = icons[i];
            return (
              <button
                key={p}
                className={page === i ? "active" : ""}
                onClick={() => setPage(i)}
              >
                <Icon size={18} />
                <span>{p}</span>
                {i === 5 && pending.length > 0 && <b>{pending.length}</b>}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <div className="db-status">
            <i className={"dot " + (graphReady ? "green" : "coral")} />
            <span>
              FalkorDB graph
              <small>
                {graphReady === null
                  ? "Checking connection"
                  : graphReady
                    ? "Live connected context"
                    : "Connection needs attention"}
              </small>
            </span>
            <Database size={17} />
          </div>
          <div className="demo-label">
            <Sparkles size={15} />
            Synthetic demo environment
          </div>
          <div className="profile">
            <div className="avatar">MC</div>
            <div>
              <strong>Manufacturing Operations</strong>
              <small>Demo authorization simulation</small>
            </div>
          </div>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div>
            <span>Workspace</span>
            <ChevronRight size={13} />
            <strong>{pages[page]}</strong>
          </div>
          <div className="top-right">
            <span className="live-indicator">
              <i className={"dot " + (graphReady ? "green" : "coral")} />
              {graphReady === null
                ? "Checking graph"
                : graphReady
                  ? "Live graph"
                  : "Graph unavailable"}
            </span>
            <span className="top-separator" />
            <span className="avatar small-avatar">N</span>
          </div>
        </header>
        <div className="content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">NORTHSTAR FOODS / CHANGE OPERATIONS</div>
              <h1>{pages[page]}</h1>
              <p>
                {
                  [
                    "Every change connected. Every response accounted for.",
                    "From supplier correction to a defensible response.",
                    "Follow the evidence, from source lot to customer shipment.",
                    "Real tools. Shared graph context. Accountable execution.",
                    "Targeted containment without unnecessary production stops.",
                    "Evidence first. Human authority at every disposition.",
                    "Verified experience, available to the next investigation.",
                    "Measured behavior. Inspectable queries. Reproducible proof.",
                  ][page]
                }
              </p>
            </div>
            <div className="heading-actions">
              <button
                className="btn"
                disabled={!!busy}
                onClick={() =>
                  act("Demo reset", async () => {
                    const r = await api("/demo/reset", {
                      confirmation: "RESET SYNTHETIC DEMO",
                    });
                    setSelectedInv("");
                    setNotice("NOTICE-001");
                    setPage(0);
                    return r;
                  })
                }
              >
                <RefreshCw size={14} />
                Reset Demo
              </button>
              <span className="badge neutral">DEMO MODE</span>
            </div>
          </div>
          {error && (
            <div className="error" role="alert">
              <ShieldAlert size={18} />
              {error}
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={15} />
              </button>
            </div>
          )}
          {toast && (
            <div className="success" role="status">
              <CheckCircle2 size={16} />
              {toast}
            </div>
          )}
          {busy && (
            <div className="working">
              <Loader2 size={15} className="spin" />
              {busy}…
            </div>
          )}
          <div className="demo-bar">
            <div className="demo-caption">
              <span className="demo-symbol">
                <GitBranch size={20} />
              </span>
              <div>
                <strong>One change. The right response.</strong>
                <small>
                  {d?.mode === "llm"
                    ? "OpenAI Agents SDK · live model tools"
                    : "Local workflow · graph tools active"}
                </small>
              </div>
            </div>
            <div className="demo-actions">
              {controls}
              <button
                className="btn dark"
                disabled={!!busy || !d?.notices?.length}
                onClick={run}
              >
                <Play size={14} />
                Run Investigation
              </button>
            </div>
          </div>
          {d?.investigations?.length > 0 && (
            <div className="run-selector">
              <label>
                Active context{" "}
                <select
                  aria-label="Investigation context"
                  value={selectedInv || inv || ""}
                  onChange={(e) => setSelectedInv(e.target.value)}
                >
                  {d?.investigations.map((i: Data) => (
                    <option key={i.id} value={i.id}>
                      {i.notice} · {i.id} · {i.status}
                    </option>
                  ))}
                </select>
              </label>
              <Badge value={d?.current?.status || "ready"} />
            </div>
          )}
          {page === 0 && (
            <>
              <div className="metric-grid">
                {[
                  {
                    label: "Production batches",
                    n: d?.total ?? "—",
                    sub: "Across 2 manufacturing facilities",
                    icon: Boxes,
                    color: "neutral",
                  },
                  {
                    label: "Confirmed affected",
                    n: d?.confirmed ?? "—",
                    sub: "Exact lot exposure established",
                    icon: ShieldAlert,
                    color: "coral",
                  },
                  {
                    label: "Under investigation",
                    n: d?.uncertain ?? "—",
                    sub: "Lot evidence requires reconciliation",
                    icon: Search,
                    color: "amber",
                  },
                  {
                    label: "Unaffected by notice",
                    n: d?.unaffected ?? "—",
                    sub: d?.unclassified
                      ? "Awaiting supplier investigation"
                      : "Cleared by historical lot provenance",
                    icon: ShieldCheck,
                    color: "green",
                  },
                ].map((m) => (
                  <div className="metric" key={m.label}>
                    <div>
                      <span>{m.label}</span>
                      <m.icon size={18} className={m.color + "-text"} />
                    </div>
                    <strong>{m.n}</strong>
                    <small>
                      <i className={"dot " + m.color} />
                      {m.sub}
                    </small>
                  </div>
                ))}
              </div>
              <div className="dashboard-grid">
                <Panel
                  title="Contain the impact. Keep production moving."
                  eyebrow="CURRENT RESPONSE"
                  action={
                    <Badge
                      value={
                        d?.verification?.passed ? "verified" : "monitoring"
                      }
                    />
                  }
                  className="response-panel"
                >
                  <div className="response-main">
                    <div
                      className="ring"
                      style={{ "--pct": pct + "%" } as React.CSSProperties}
                    >
                      <div>
                        <strong>
                          {d?.unaffected || 0}
                          <small>of {d?.total || 120} batches</small>
                        </strong>
                      </div>
                    </div>
                    <div className="response-copy">
                      <span className="eyebrow green-text">
                        {d?.current
                          ? "PRECISE, EVIDENCE-BASED CONTAINMENT"
                          : "READY FOR THE NEXT CHANGE"}
                      </span>
                      <h2>
                        {d?.current
                          ? `${pct}% of batches can keep moving.`
                          : "Connected context. Controlled action."}
                      </h2>
                      <p>
                        {d?.current
                          ? `${d?.confirmed} confirmed and ${d?.uncertain} uncertain batches require a response. Unaffected inventory retains its eligibility.`
                          : "Inject a synthetic supplier notice to trace historical lots, protect shipments and coordinate quality review."}
                      </p>
                      <div className="response-stats">
                        <span>
                          <b>{d?.held || 0}</b> ERP holds
                        </span>
                        <span>
                          <b>{d?.impacted_shipments || 0}</b> impacted shipments
                        </span>
                        <span>
                          <b>
                            {d?.tasks?.filter((t: Data) => t.status === "open")
                              .length || 0}
                          </b>{" "}
                          open response tasks
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="response-footer">
                    <span>
                      <ShieldCheck size={16} />
                      QA-17 · Allergen containment policy
                    </span>
                    <button onClick={() => setPage(4)}>
                      Review containment <ArrowRight size={15} />
                    </button>
                  </div>
                </Panel>
                <Panel title="Response progress" eyebrow="WORKFLOW">
                  <div className="progress-number">
                    <strong>
                      {progress}
                      <small>%</small>
                    </strong>
                    <Badge value={d?.current?.status || "ready"} />
                  </div>
                  <div className="progress-track">
                    <i style={{ width: progress + "%" }} />
                  </div>
                  <div className="workflow-steps">
                    {[
                      "Graph investigation",
                      "Containment planning",
                      "ERP holds applied",
                      "Independent verification",
                    ].map((s, i) => (
                      <div key={s}>
                        <span
                          className={
                            progress >= (i + 1) * 25 ? "step-done" : ""
                          }
                        >
                          {progress >= (i + 1) * 25 ? (
                            <Check size={12} />
                          ) : (
                            i + 1
                          )}
                        </span>
                        {s}
                        {progress >= (i + 1) * 25 && (
                          <Check size={13} className="green-text" />
                        )}
                      </div>
                    ))}
                  </div>
                  <button className="text-link" onClick={() => setPage(3)}>
                    Open agent control room <ArrowUpRight size={14} />
                  </button>
                </Panel>
                <Panel
                  title="Connected impact map"
                  eyebrow="LIVE KNOWLEDGE GRAPH"
                  action={
                    <button className="text-link" onClick={() => setPage(2)}>
                      Explore graph <ArrowUpRight size={14} />
                    </button>
                  }
                >
                  <GraphView
                    focus={focus}
                    setFocus={setFocus}
                    inv={inv}
                    compact
                  />
                </Panel>
                <Panel
                  title="Agent activity"
                  eyebrow="EXECUTION FEED"
                  action={
                    <span className="live-indicator">
                      <i className="dot green" />
                      Live
                    </span>
                  }
                >
                  <div className="activity-list">
                    {events.length ? (
                      events
                        .slice(-5)
                        .reverse()
                        .map((e: Data) => (
                          <div className="activity" key={e.id}>
                            <div
                              className={
                                "activity-icon " +
                                (e.status === "failed"
                                  ? "coral-text"
                                  : "green-text")
                              }
                            >
                              {e.agent === "memory" ? (
                                <GitBranch size={15} />
                              ) : (
                                <Activity size={15} />
                              )}
                            </div>
                            <div>
                              <strong>
                                {e.agent.charAt(0).toUpperCase() +
                                  e.agent.slice(1)}
                              </strong>
                              <p>{e.tool.replaceAll("_", " ")}</p>
                              <small>
                                {e.status} · {e.duration_ms} ms
                              </small>
                            </div>
                            <span className="activity-time">
                              {new Date(e.at).toLocaleTimeString([], {
                                hour: "2-digit",
                                minute: "2-digit",
                              })}
                            </span>
                          </div>
                        ))
                    ) : (
                      <Empty>
                        Agents are standing by. Inject a supplier change to
                        begin.
                      </Empty>
                    )}
                  </div>
                  <button
                    className="text-link padded-link"
                    onClick={() => setPage(3)}
                  >
                    View execution evidence <ArrowRight size={14} />
                  </button>
                </Panel>
              </div>
              <Panel
                title="Supplier change notices"
                eyebrow="INCOMING INTELLIGENCE"
                action={
                  <button className="text-link" onClick={() => setPage(1)}>
                    View all <ArrowRight size={14} />
                  </button>
                }
              >
                {d?.notices?.length ? (
                  <div className="notice-list">
                    {d.notices.map((n: Data) => (
                      <button
                        key={n.id}
                        onClick={() => {
                          setNotice(n.id);
                          setPage(1);
                        }}
                      >
                        <span className="notice-icon">
                          <FileText size={19} />
                        </span>
                        <div>
                          <strong>{n.title}</strong>
                          <small>
                            {n.supplier} · {n.id} · Effective {n.effective_from}
                          </small>
                        </div>
                        <Badge
                          value={
                            n.scope === "ambiguous"
                              ? "uncertain"
                              : "corrective notice"
                          }
                        />
                        <ChevronRight size={18} />
                      </button>
                    ))}
                  </div>
                ) : (
                  <Empty>
                    No supplier changes received. Your 120 synthetic batches are
                    available.
                  </Empty>
                )}
              </Panel>
            </>
          )}
          {page === 1 && (
            <>
              <div className="section-toolbar">
                <div className="tabs">
                  {d?.notices?.map((n: Data) => (
                    <button
                      key={n.id}
                      className={notice === n.id ? "chosen" : ""}
                      onClick={() => setNotice(n.id)}
                    >
                      {n.id}
                    </button>
                  ))}
                </div>
                <div className="button-row">
                  <label className="btn">
                    <FileText size={14} />
                    Upload JSON / CSV
                    <input
                      type="file"
                      accept=".json,.csv"
                      hidden
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (!f) return;
                        act("Notice uploaded", async () => {
                          const data = new FormData();
                          data.append("file", f);
                          const r = await fetch("/api/notices/upload", {
                            method: "POST",
                            body: data,
                          });
                          const n = await r.json();
                          if (!r.ok) throw Error(n.detail);
                          setNotice(n.id);
                          return n;
                        });
                      }}
                    />
                  </label>
                  <button
                    className="btn"
                    onClick={() => setShowForm(!showForm)}
                  >
                    <Plus size={14} />
                    Create Notice
                  </button>
                </div>
              </div>
              {showForm && (
                <Panel title="Submit a synthetic supplier correction">
                  <div className="form-grid">
                    {Object.keys(form).map((k) => (
                      <label key={k}>
                        {k.replaceAll("_", " ")}
                        <input
                          aria-label={k}
                          value={form[k]}
                          onChange={(e) =>
                            setForm({ ...form, [k]: e.target.value })
                          }
                        />
                      </label>
                    ))}
                  </div>
                  <button
                    className="btn primary"
                    onClick={() =>
                      act("Notice submitted", async () => {
                        const n = await api("/notices", {
                          ...form,
                          lots: form.lots
                            .split(",")
                            .map((s: string) => s.trim()),
                        });
                        setNotice(n.id);
                        setShowForm(false);
                        return n;
                      })
                    }
                  >
                    Validate & submit
                  </button>
                </Panel>
              )}
              {(() => {
                const n =
                  d?.notices?.find((n: Data) => n.id === notice) ||
                  currentNotice;
                return n ? (
                  <>
                    <Panel
                      title={n.title}
                      eyebrow={n.id}
                      action={
                        <Badge
                          value={
                            n.scope === "ambiguous" ? "uncertain" : "validated"
                          }
                        />
                      }
                    >
                      <div className="spec-compare">
                        <div>
                          <span className="eyebrow">
                            PREVIOUS SPECIFICATION · V1
                          </span>
                          <h2>
                            {n.supplier === "SUP-1"
                              ? "Cocoa blend"
                              : "Ingredient declaration"}
                          </h2>
                          <p>
                            Supplier:{" "}
                            {
                              (
                                {
                                  "SUP-1": "Aster Ingredients",
                                  "SUP-2": "Valley Harvest",
                                  "SUP-3": "Meridian Naturals",
                                } as Record<string, string>
                              )[n.supplier]
                            }
                          </p>
                          <div className="spec-line">
                            Declared allergens <Badge value="none declared" />
                          </div>
                        </div>
                        <div className="change-arrow">
                          <ArrowRight />
                        </div>
                        <div className="corrected-spec">
                          <span className="eyebrow coral-text">
                            CORRECTIVE DECLARATION · V2
                          </span>
                          <h2>
                            {n.allergen.charAt(0).toUpperCase() +
                              n.allergen.slice(1)}{" "}
                            component disclosed
                          </h2>
                          <p>Retrospective correction to delivered lots</p>
                          <div className="spec-line">
                            Newly disclosed <Badge value={n.allergen} />
                          </div>
                        </div>
                      </div>
                      <div className="detail-grid">
                        <div>
                          <small>Applicable scope</small>
                          <strong>
                            {JSON.parse(n.payload).lots.join(" · ")}
                          </strong>
                        </div>
                        <div>
                          <small>Effective window</small>
                          <strong>
                            {n.effective_from} — {n.effective_to}
                          </strong>
                        </div>
                        <div>
                          <small>Evidence provenance</small>
                          <strong>Supplier corrective declaration</strong>
                        </div>
                        <div>
                          <small>Certainty</small>
                          <strong>
                            {n.scope === "exact"
                              ? "Exact lot identifiers"
                              : "Incomplete identifiers · investigate"}
                          </strong>
                        </div>
                      </div>
                      <p className="source-note">{n.evidence}</p>
                      <button
                        className="btn primary"
                        onClick={run}
                        disabled={!!busy}
                      >
                        <Play size={15} />
                        Start Investigation
                      </button>
                    </Panel>
                    <div className="callout">
                      <ShieldCheck size={22} />
                      <div>
                        <strong>
                          Historical facts determine the response.
                        </strong>
                        <p>
                          Current recipes do not establish historical exposure.
                          Agents inspect consumed lots, exact packaging versions
                          and actual shipment dependencies.
                        </p>
                      </div>
                    </div>
                  </>
                ) : (
                  <Empty>
                    Inject a supplier change, upload a JSON / CSV notice, or
                    create one with the form.
                  </Empty>
                );
              })()}
            </>
          )}
          {page === 2 && (
            <Panel
              title="Historical dependency network"
              eyebrow="FALKORDB · LIVE TRAVERSAL"
              action={<Badge value="source graph" />}
            >
              <GraphView focus={focus} setFocus={setFocus} inv={inv} />
              <div className="graph-help">
                <Network size={16} />
                Click a batch to inspect its lot, recipe, artwork and decision
                evidence. Expand any selected node to follow the next
                relationship.
              </div>
            </Panel>
          )}
          {page === 3 && (
            <>
              <div className="agent-grid">
                {["investigator", "coordinator", "verifier", "memory"].map(
                  (a, i) => {
                    const last = events
                      .filter((e: Data) => e.agent === a)
                      .slice(-1)[0];
                    return (
                      <div className="agent-card" key={a}>
                        <div className="agent-avatar">
                          {React.createElement(
                            [Search, Users, ShieldCheck, GitBranch][i],
                            { size: 22 },
                          )}
                          <i className="dot green" />
                        </div>
                        <span className="eyebrow">
                          AGENT {String(i + 1).padStart(2, "0")}
                        </span>
                        <h3>
                          {
                            [
                              "Change Investigator",
                              "Response Coordinator",
                              "Independent Verifier",
                              "Memory & Learning",
                            ][i]
                          }
                        </h3>
                        <Badge value={last?.status || "standby"} />
                        <p>
                          {last?.tool.replaceAll("_", " ") ||
                            "Waiting for connected context"}
                        </p>
                      </div>
                    );
                  },
                )}
              </div>
              <Panel
                title="Tool execution timeline"
                eyebrow={
                  d?.current?.mode === "llm"
                    ? "OPENAI AGENTS SDK · MODEL TOOL CALLING"
                    : "LOCAL WORKFLOW MODE"
                }
                action={
                  <div className="button-row">
                    <button
                      className="btn primary small"
                      disabled={!!busy || !inv}
                      onClick={hold}
                    >
                      Apply Containment
                    </button>
                    <button
                      className="btn small"
                      disabled={!!busy || !inv}
                      onClick={verify}
                    >
                      Run Independent Verification
                    </button>
                  </div>
                }
              >
                {events.length ? (
                  <div className="execution-list">
                    {events.map((e: Data) => (
                      <details key={e.id}>
                        <summary>
                          <span className={"event-dot " + e.status} />
                          <time>{new Date(e.at).toLocaleTimeString()}</time>
                          <strong>{e.agent}</strong>
                          <span>{e.tool.replaceAll("_", " ")}</span>
                          <Badge value={e.status} />
                          <small>{e.duration_ms} ms</small>
                        </summary>
                        <pre>{e.detail}</pre>
                      </details>
                    ))}
                  </div>
                ) : (
                  <Empty>
                    Start an investigation to execute tools and record evidence
                    in FalkorDB.
                  </Empty>
                )}
              </Panel>
              {d?.current?.error && (
                <div className="error">{d.current.error}</div>
              )}
            </>
          )}
          {page === 4 && (
            <Panel
              title="Batch inventory"
              eyebrow="PERSISTED ERP SIMULATION"
              action={
                <div className="button-row">
                  <button
                    className="btn primary small"
                    disabled={!!busy || !inv}
                    onClick={hold}
                  >
                    <ShieldCheck size={14} />
                    Apply Containment
                  </button>
                  <button
                    className="btn small"
                    disabled={!!busy || !inv}
                    onClick={verify}
                  >
                    Verify ERP
                  </button>
                </div>
              }
            >
              <div className="table-toolbar">
                <label className="searchbox">
                  <Search size={16} />
                  <input
                    placeholder="Search batch, product or lot…"
                    aria-label="Search batches"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </label>
                <select
                  aria-label="Classification"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                >
                  <option value="all">All classifications</option>
                  <option>confirmed</option>
                  <option>uncertain</option>
                  <option>unaffected</option>
                </select>
                <span>{filtered.length} batches</span>
              </div>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Batch / product</th>
                      <th>Source lot</th>
                      <th>Classification</th>
                      <th>ERP status</th>
                      <th>Shipment</th>
                      <th>Owner / action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((b) => (
                      <tr key={b.id}>
                        <td>
                          <button
                            className="batch-link"
                            onClick={() => {
                              setFocus(b.id);
                              setPage(2);
                            }}
                          >
                            {b.id}
                            <ArrowUpRight size={12} />
                          </button>
                          <small>{b.product || "Awaiting investigation"}</small>
                        </td>
                        <td>
                          <code>{b.lots?.join(", ") || "—"}</code>
                          <small>{b.recipe || ""}</small>
                        </td>
                        <td>
                          <Badge value={b.classification} />
                        </td>
                        <td>
                          <Badge value={b.erp_status} />
                        </td>
                        <td>
                          {b.shipments?.map((s: Data) => (
                            <div key={s.id}>
                              <button
                                className="text-link"
                                disabled={!!busy}
                                onClick={() =>
                                  act("Dispatch", () =>
                                    api("/erp/dispatch/" + s.id, {}),
                                  )
                                }
                              >
                                <Truck size={13} />
                                {s.id}
                              </button>
                              <small>{s.customer}</small>
                            </div>
                          )) || "—"}
                        </td>
                        <td>
                          <small>{b.owner}</small>
                          {b.hold_required && (
                            <button
                              className="text-link"
                              onClick={() => {
                                setBatch(b.id);
                                setPage(5);
                              }}
                            >
                              Review QA <ArrowRight size={13} />
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}
          {page === 5 && (
            <div className="qa-layout">
              <Panel
                title="Disposition queue"
                eyebrow="HUMAN DECISION REQUIRED"
              >
                <div className="queue-list">
                  {pending.length ? (
                    pending.map((b) => (
                      <button
                        key={b.id}
                        className={batch === b.id ? "selected" : ""}
                        onClick={() => setBatch(b.id)}
                      >
                        <span>
                          <strong>{b.id}</strong>
                          <small>{b.product}</small>
                        </span>
                        <Badge value={b.classification} />
                      </button>
                    ))
                  ) : (
                    <Empty>
                      Containment proposals will appear after investigation.
                    </Empty>
                  )}
                </div>
              </Panel>
              <div>
                <Panel
                  title={batch + " · QA disposition"}
                  eyebrow="DEMO AUTHORIZATION SIMULATION"
                  action={
                    <Badge value={currentBatch?.erp_status || "pending"} />
                  }
                >
                  <p className="qa-rationale">
                    {currentBatch?.rationale || "Select an investigated batch."}
                  </p>
                  <div className="evidence-path">
                    {currentBatch?.evidence
                      ?.filter(Boolean)
                      .map((x: string) => (
                        <button
                          key={x}
                          onClick={() => {
                            setFocus(x);
                            setPage(2);
                          }}
                        >
                          {x}
                          <ChevronRight size={12} />
                        </button>
                      ))}
                  </div>
                  <div className="qa-role">
                    <label>
                      Assume demo authority
                      <select
                        aria-label="Demo authority"
                        value={role}
                        onChange={(e) => setRole(e.target.value)}
                      >
                        <option>Viewer</option>
                        <option>Warehouse</option>
                        <option value="QA">QA</option>
                      </select>
                    </label>
                    <span>
                      This local role selector simulates authority; it is not
                      authentication.
                    </span>
                  </div>
                  <label className="rationale-label">
                    Decision / evidence rationale
                    <textarea
                      aria-label="Decision rationale"
                      placeholder="Record the specific evidence reviewed and why this action is justified…"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    />
                  </label>
                  <h4>Release prerequisites</h4>
                  <div className="prerequisites">
                    {prerequisites.map((p) => {
                      const found = evidence.find((e) => e.prerequisite === p);
                      return (
                        <div key={p}>
                          <span
                            className={found ? "prereq-done" : "prereq-missing"}
                          >
                            {found ? <Check size={13} /> : <Clock size={13} />}
                          </span>
                          <div>
                            <strong>{p.replaceAll("_", " ")}</strong>
                            <small>
                              {found
                                ? "Attested by QA · " + found.id
                                : "Explicit supporting QA attestation required"}
                            </small>
                          </div>
                          <button
                            className="btn small"
                            disabled={
                              !!busy ||
                              !inv ||
                              !currentBatch?.hold_required ||
                              !!found
                            }
                            onClick={() =>
                              act("Evidence recorded", async () => {
                                const e = await api("/approvals/evidence", {
                                  investigation: inv,
                                  batch,
                                  role,
                                  prerequisite: p,
                                  reason,
                                });
                                setEvidence(
                                  await api("/evidence/" + inv + "/" + batch),
                                );
                                return e;
                              })
                            }
                          >
                            {found ? "Recorded" : "Attest"}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                  {currentBatch?.classification === "uncertain" && (
                    <div className="warning">
                      Unresolved lot exposure cannot be released, even with
                      packaging attestations. Reconcile source facts and
                      reinvestigate.
                    </div>
                  )}
                  <div className="decision-buttons">
                    {["release", "dispose", "reject", "request_evidence"].map(
                      (decision) => (
                        <button
                          key={decision}
                          className={
                            "btn " + (decision === "release" ? "primary" : "")
                          }
                          disabled={
                            !!busy || !inv || !currentBatch?.hold_required
                          }
                          onClick={() =>
                            act("QA " + decision, () =>
                              api("/approvals/decide", {
                                investigation: inv,
                                batch,
                                role,
                                decision,
                                reason,
                              }),
                            )
                          }
                        >
                          {decision === "release"
                            ? "Approve Release"
                            : decision === "dispose"
                              ? "Approve Disposal"
                              : decision === "reject"
                                ? "Reject"
                                : "Request Evidence"}
                        </button>
                      ),
                    )}
                  </div>
                </Panel>
                <Panel title="Immutable decision history" eyebrow="AUDIT TRAIL">
                  {decisions.length ? (
                    decisions.map((a) => (
                      <div className="audit-item" key={a.id}>
                        <Badge value={a.decision} />
                        <strong>{a.batch}</strong>
                        <p>{a.reason}</p>
                        <small>
                          {a.authority} · {new Date(a.at).toLocaleString()} ·{" "}
                          {a.id}
                        </small>
                      </div>
                    ))
                  ) : (
                    <Empty>No human decisions have been recorded.</Empty>
                  )}
                </Panel>
              </div>
            </div>
          )}
          {page === 6 && (
            <>
              <div className="memory-intro">
                <GitBranch size={27} />
                <div>
                  <h2>Experience that survives the session.</h2>
                  <p>
                    Verified episodes live in FalkorDB. Reuse is limited by
                    supplier, allergen, causal mechanism and memory validity.
                  </p>
                </div>
                <button
                  className="btn primary"
                  disabled={!!busy}
                  onClick={() =>
                    act("Second investigation started", async () => {
                      const n = await api("/demo/inject/second", {});
                      setNotice(n.id);
                      const i = await api("/investigations", {
                        notice: n.id,
                        mode: "auto",
                      });
                      setSelectedInv(i.id);
                      return i;
                    })
                  }
                >
                  Start Second Investigation <ArrowRight size={15} />
                </button>
              </div>
              <div className="memory-grid">
                {memories.map((m) => (
                  <Panel
                    key={m.id}
                    title={m.name}
                    eyebrow={m.id}
                    action={
                      <Badge value={m.outdated ? "outdated" : "verified"} />
                    }
                  >
                    <div className="memory-tags">
                      <Badge value={m.allergen} />
                      <Badge value={m.supplier} />
                    </div>
                    <p>{m.lesson}</p>
                    <div className="memory-scope">
                      <span className="eyebrow">APPLICABILITY BOUNDARY</span>
                      <p>{m.scope}</p>
                    </div>
                    <small>{new Date(m.at).toLocaleString()}</small>
                    <button
                      className="text-link"
                      onClick={() => {
                        setFocus(m.id);
                        setPage(2);
                      }}
                    >
                      Inspect memory graph <ArrowUpRight size={14} />
                    </button>
                  </Panel>
                ))}
              </div>
              {d?.current?.retrieved_memory && (
                <Panel
                  title="Context retrieved for this investigation"
                  eyebrow="CHECKED AGAINST CURRENT NOTICE"
                >
                  {JSON.parse(d.current.retrieved_memory).map((m: Data) => (
                    <div className="retrieval" key={m.id}>
                      <strong>{m.name}</strong>
                      <p>{m.applicability}</p>
                      <span className="green-text">Reused: {m.reused}</span>
                      <p className="coral-text">Rejected: {m.rejected}</p>
                    </div>
                  ))}
                </Panel>
              )}
            </>
          )}
          {page === 7 && (
            <>
              <div className="proof-banner">
                <Database size={28} />
                <div>
                  <h2>Connected context is a dependency.</h2>
                  <p>
                    Restricted mode reads only the notice. It cannot classify
                    inventory or act without the graph.
                  </p>
                </div>
                <button
                  className="btn"
                  disabled={!!busy || !d?.notices?.length}
                  onClick={() =>
                    act("Restricted comparison started", async () => {
                      const i = await api("/investigations", {
                        notice,
                        mode: "restricted",
                      });
                      setSelectedInv(i.id);
                      return i;
                    })
                  }
                >
                  Run Restricted Comparison
                </button>
              </div>
              <div className="metric-grid">
                {[
                  {
                    label: "Confirmed detection recall",
                    n:
                      evaluation.confirmed_recall == null
                        ? "—"
                        : Math.round(evaluation.confirmed_recall * 100) + "%",
                    sub: "Primary scenario golden labels",
                  },
                  {
                    label: "False positive containment",
                    n:
                      evaluation.false_positive_containment == null
                        ? "—"
                        : Math.round(
                            evaluation.false_positive_containment * 100,
                          ) + "%",
                    sub: "Unaffected held / unaffected total",
                  },
                  {
                    label: "Containment completeness",
                    n:
                      evaluation.containment_completeness == null
                        ? "—"
                        : Math.round(
                            evaluation.containment_completeness * 100,
                          ) + "%",
                    sub: "Verified holds or authorized disposition",
                  },
                  {
                    label: "Recorded graph queries",
                    n: evaluation.graph_queries ?? "—",
                    sub: "Audited workflow tool queries",
                  },
                ].map((m) => (
                  <div className="metric" key={m.label}>
                    <div>
                      <span>{m.label}</span>
                      <Database size={17} />
                    </div>
                    <strong>{m.n}</strong>
                    <small>{m.sub}</small>
                  </div>
                ))}
              </div>
              <div className="dashboard-grid">
                <Panel
                  title="Measured investigation duration"
                  eyebrow="REAL EXECUTION · NO CLAIMED SPEEDUP"
                >
                  <div className="chart">
                    <ResponsiveContainer width="100%" height={220}>
                      <AreaChart
                        data={(evaluation.runs || [])
                          .filter((r: Data) => r.duration_ms != null)
                          .slice()
                          .reverse()
                          .map((r: Data, i: number) => ({
                            run: "Run " + (i + 1),
                            ms: r.duration_ms,
                          }))}
                      >
                        <defs>
                          <linearGradient
                            id="gradient"
                            x1="0"
                            y1="0"
                            x2="0"
                            y2="1"
                          >
                            <stop
                              offset="0%"
                              stopColor="#419b78"
                              stopOpacity={0.25}
                            />
                            <stop
                              offset="100%"
                              stopColor="#419b78"
                              stopOpacity={0}
                            />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="run" fontSize={11} />
                        <Tooltip />
                        <Area
                          type="monotone"
                          dataKey="ms"
                          stroke="#278961"
                          fill="url(#gradient)"
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                  <p className="source-note">
                    Durations include real tool and persistence costs. Memory
                    retrieval does not imply a performance improvement.
                  </p>
                </Panel>
                <Panel
                  title="Independent verification"
                  eyebrow="GRAPH VS ERP"
                  action={
                    <button
                      className="btn small"
                      disabled={!!busy || !inv}
                      onClick={verify}
                    >
                      Verify now
                    </button>
                  }
                >
                  {evaluation.verification ? (
                    <>
                      <div className="verification-symbol">
                        <ShieldCheck size={30} />
                        <h2>
                          {evaluation.verification.passed
                            ? "Containment verified"
                            : "Discrepancies detected"}
                        </h2>
                      </div>
                      <p>
                        {evaluation.verification.covered} /{" "}
                        {evaluation.verification.required} required batches
                        accounted for.
                      </p>
                      <p>{evaluation.verification.resolution}</p>
                      <Badge
                        value={
                          evaluation.verification.unresolved + " unresolved"
                        }
                      />
                      {evaluation.verification.discrepancies.map(
                        (e: Data, i: number) => (
                          <div className="error" key={i}>
                            {e.batch}: {e.problem}
                          </div>
                        ),
                      )}
                    </>
                  ) : (
                    <Empty>
                      Run independent verification after containment.
                    </Empty>
                  )}
                </Panel>
              </div>
              <Panel
                title="First and repeated investigation comparison"
                eyebrow="PERSISTED RUNS"
              >
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Investigation</th>
                        <th>Notice</th>
                        <th>Mode</th>
                        <th>Duration</th>
                        <th>Retrieved episodes</th>
                        <th>Outcome</th>
                      </tr>
                    </thead>
                    <tbody>
                      {evaluation.runs?.map((r: Data) => (
                        <tr key={r.id}>
                          <td>
                            <button
                              className="text-link"
                              onClick={() => setSelectedInv(r.id)}
                            >
                              {r.id}
                            </button>
                          </td>
                          <td>{r.notice}</td>
                          <td>{r.mode}</td>
                          <td>{r.duration_ms} ms</td>
                          <td>{r.memory_retrieved}</td>
                          <td>
                            <Badge value={r.status} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Panel>
              <Panel
                title="Executed Cypher and provenance"
                eyebrow="DEVELOPER EVIDENCE"
              >
                {evaluation.queries?.length ? (
                  evaluation.queries.map((q: Data) => (
                    <details className="query" key={q.id}>
                      <summary>
                        <Database size={15} />
                        {q.rows} rows · {q.duration_ms} ms <small>{q.at}</small>
                      </summary>
                      <pre>{q.query}</pre>
                      <code>{q.parameters}</code>
                    </details>
                  ))
                ) : (
                  <Empty>No graph tool queries executed in this context.</Empty>
                )}
              </Panel>
            </>
          )}
          <footer>
            <span>
              <GitBranch size={13} />
              SpecCascade <i /> Autonomous manufacturing change intelligence
            </span>
            <span>
              Synthetic data · Simulated enterprise actions · Powered by
              FalkorDB
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
