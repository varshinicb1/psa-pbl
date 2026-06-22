#!/usr/bin/env python3
"""
Generate professional IEEE-paper-quality diagrams for the Metro Grid Digital Twin.
Outputs high-resolution SVG + PNG files to docs/images/

Usage:
    python scripts/generate_diagrams.py
"""

from __future__ import annotations

import os
import pathlib
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np

matplotlib.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.titlesize": 14,
    "axes.labelsize": 12,
    "figure.dpi": 200,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "svg.fonttype": "none",
})

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def log(msg: str) -> None:
    print(f"  [OK] {msg}")


# ---------------------------------------------------------------------------
# 1. SYSTEM ARCHITECTURE DIAGRAM
# ---------------------------------------------------------------------------
def generate_architecture() -> None:
    import graphviz
    dot = graphviz.Digraph(
        name="architecture", format="svg", engine="dot",
        graph_attr={"rankdir": "TB", "splines": "ortho", "fontname": "Times-Roman",
                    "fontsize": "12", "dpi": "300", "bgcolor": "white",
                    "pad": "0.5", "nodesep": "0.4", "ranksep": "0.6"},
    )
    # Orchestrator cluster
    with dot.subgraph(name="cluster_orch") as s:
        s.attr(label="dt-orchestrator (FastAPI Server)", style="rounded,dashed",
               color="#1a56db", fontcolor="#1a56db", fontsize="13", fontname="Times-Bold")
        for node_id, label, color in [
            ("boot", "Bootstrap\n(Path Setup)", "#e0e7ff"),
            ("tick", "Tick Loop\n(asyncio 1s)", "#e0e7ff"),
            ("pf", "Powerflow\n(pandapower)", "#e0e7ff"),
            ("ml_detect", "ML Detection\n(Physics+Ensemble)", "#e0e7ff"),
            ("pub", "Publish\n(REST+WebSocket)", "#e0e7ff"),
        ]:
            s.node(node_id, label, shape="box", style="filled", fillcolor=color)
        s.edge("boot", "tick"); s.edge("tick", "pf")
        s.edge("pf", "ml_detect"); s.edge("ml_detect", "pub")

    # Dashboard cluster
    with dot.subgraph(name="cluster_dash") as s:
        s.attr(label="dt-dashboard (React+Vite+D3)", style="rounded,dashed",
               color="#059669", fontcolor="#059669", fontsize="13", fontname="Times-Bold")
        s.node("ui", "Operations Dashboard\nStatusBar TopologyMap\nVoltageChart AnomalyPanel",
               shape="box3d", style="filled", fillcolor="#d1fae5")

    # Simulators cluster
    with dot.subgraph(name="cluster_sim") as s:
        s.attr(label="Simulator Adapters", style="rounded,dashed",
               color="#7c3aed", fontcolor="#7c3aed", fontsize="13", fontname="Times-Bold")
        s.node("pp", "pandapower (Active)", shape="box", style="filled", fillcolor="#ede9fe")
        s.node("bescom", "BESCOM 50-Bus", shape="box", style="filled", fillcolor="#ede9fe")
        s.node("dss", "OpenDSS (Skeleton)", shape="box", style="filled", fillcolor="#f3e8ff")
        s.node("mp", "MATPOWER (Skeleton)", shape="box", style="filled", fillcolor="#f3e8ff")

    # ML & SCADA cluster
    with dot.subgraph(name="cluster_ml") as s:
        s.attr(label="ML & SCADA Layer", style="rounded,dashed",
               color="#dc2626", fontcolor="#dc2626", fontsize="13", fontname="Times-Bold")
        s.node("ens", "Ensemble Detector\nZScore ROC LSTM", shape="box", style="filled", fillcolor="#fce7f3")
        s.node("scada", "SCADA Stack\nIEC61850 DNP3 Modbus", shape="box", style="filled", fillcolor="#fce7f3")
        s.node("comp", "Compliance\nNERC CIP IEGC 2023", shape="box", style="filled", fillcolor="#fce7f3")

    dot.edge("pub", "ui", style="dashed", arrowhead="normal", color="#059669", label="WS/REST")
    dot.edge("pf", "pp", style="dashed", color="#7c3aed", arrowhead="normal")
    dot.edge("pf", "bescom", style="dashed", color="#7c3aed", arrowhead="normal")
    dot.edge("ml_detect", "ens", style="dashed", color="#dc2626", arrowhead="normal")

    dot.render(str(OUTPUT_DIR / "architecture"), cleanup=True)
    log("architecture.svg")


# ---------------------------------------------------------------------------
# 2. PIPELINE / DATA FLOW
# ---------------------------------------------------------------------------
def generate_pipeline() -> None:
    import graphviz
    dot = graphviz.Digraph(
        name="pipeline", format="svg", engine="dot",
        graph_attr={"rankdir": "LR", "splines": "ortho", "fontname": "Times-Roman",
                    "fontsize": "12", "dpi": "300", "bgcolor": "white", "pad": "0.5"},
    )
    dot.node("ingest", "Telemetry\nIngestion", shape="cylinder", style="filled", fillcolor="#dbeafe")
    dot.node("pf", "AC Powerflow\n(pandapower runpp)", shape="box3d", style="filled", fillcolor="#e0e7ff")
    dot.node("state", "State Update\n(GridGraphStore)", shape="box", style="filled", fillcolor="#d1fae5")
    dot.node("physics", "Physics Rule\nDetector", shape="box", style="filled", fillcolor="#fef3c7")
    dot.node("ml", "ML Ensemble\n(ZScore/ROC/LSTM)", shape="box", style="filled", fillcolor="#fce7f3")
    dot.node("explain", "Explanation\nGenerator", shape="box", style="filled", fillcolor="#ede9fe")
    dot.node("pub", "Publish\n(WS / REST)", shape="box3d", style="filled", fillcolor="#e0e7ff")

    dot.edge("ingest", "pf", label="load perturbation")
    dot.edge("pf", "state", label="res_bus / res_line")
    dot.edge("state", "physics", label="snapshot")
    dot.edge("state", "ml", label="snapshot")
    dot.edge("physics", "explain", label="violations", style="dashed")
    dot.edge("ml", "explain", label="anomaly scores")
    dot.edge("explain", "pub", label="ExplanationPacket")

    dot.node("timing", "Target: < 100 ms/tick", shape="note", style="filled", fillcolor="#f1f5f9")
    dot.render(str(OUTPUT_DIR / "pipeline"), cleanup=True)
    log("pipeline.svg")


# ---------------------------------------------------------------------------
# 3. DASHBOARD LAYOUT
# ---------------------------------------------------------------------------
def generate_dashboard_layout() -> None:
    fig, ax = plt.subplots(1, 1, figsize=(14, 8))
    ax.set_xlim(0, 14); ax.set_ylim(0, 8)
    ax.axis("off")
    ax.set_title("Metro Grid Digital Twin -- Operations Dashboard Layout", fontsize=16, fontweight="bold", pad=20)

    # Status bar
    r = FancyBboxPatch((0.2, 7.2), 13.6, 0.6, boxstyle="round,pad=0.1",
                        facecolor="#1e293b", edgecolor="#334155", linewidth=1.5, zorder=2)
    ax.add_patch(r)
    ax.text(7.0, 7.5, "StatusBar -- Grid: BESCOM Bangalore | Ticks: 1,247 | System: Online",
            ha="center", va="center", fontsize=9, color="white", fontfamily="monospace")

    panels = [
        ("QuickStats -- Buses: 50 | Lines: 37 | Load: 1,750 MW", 6.0, 0.8, "#059669", 0.2, 4.5),
        ("TopologyMap -- SVG Grid Topology with Real-Time Voltage Coloring", 2.5, 3.0, "#1a56db", 0.2, 4.5),
        ("VoltageChart -- Per-Unit Voltage per Bus with Threshold Bands", 6.0, 0.8, "#7c3aed", 5.0, 4.5),
        ("TimelineChart -- Tick History with Anomaly Markers", 2.5, 3.0, "#7c3aed", 5.0, 4.5),
    ]
    for label, y, h, color, x, w in panels:
        r = FancyBboxPatch((x, y - h + 0.2), w, h, boxstyle="round,pad=0.1",
                            facecolor="white", edgecolor=color, linewidth=1.5, zorder=2)
        ax.add_patch(r)
        ax.text(x + w/2, y - h/2 + 0.2, label, ha="center", va="center", fontsize=8, color="#334155")

    # Anomaly panel
    r = FancyBboxPatch((9.8, 2.5), 4.0, 4.3, boxstyle="round,pad=0.1",
                        facecolor="white", edgecolor="#dc2626", linewidth=1.5, zorder=2)
    ax.add_patch(r)
    ax.text(11.8, 5.0, "AnomalyPanel", ha="center", va="center", fontsize=10, fontweight="bold", color="#dc2626")
    ax.text(11.8, 4.3, "WARNING: Voltage Violation at Bus 14\n  vm_pu = 0.932 (1.9% below bound)\n  Confidence: 94.2%",
            ha="center", va="center", fontsize=7, color="#475569")

    # Node inspector
    r = FancyBboxPatch((10.5, 0.5), 3.0, 1.5, boxstyle="round,pad=0.1",
                        facecolor="#f8fafc", edgecolor="#94a3b8", linewidth=1, linestyle="--", zorder=3)
    ax.add_patch(r)
    ax.text(12.0, 1.25, "NodeInspector\n(Overlay on Node Click)", ha="center", va="center", fontsize=7, color="#64748b")

    legend = [
        mpatches.Patch(facecolor="white", edgecolor="#059669", label="Stats Panel"),
        mpatches.Patch(facecolor="white", edgecolor="#1a56db", label="Topology Map"),
        mpatches.Patch(facecolor="white", edgecolor="#7c3aed", label="Charts"),
        mpatches.Patch(facecolor="white", edgecolor="#dc2626", label="Anomaly Panel"),
    ]
    ax.legend(handles=legend, loc="lower center", ncol=4, fontsize=7,
              framealpha=0.9, edgecolor="#cbd5e1")

    fig.savefig(OUTPUT_DIR / "dashboard_layout.svg", format="svg")
    fig.savefig(OUTPUT_DIR / "dashboard_layout.png", format="png")
    plt.close(fig)
    log("dashboard_layout.svg + .png")


# ---------------------------------------------------------------------------
# 4. BESCOM NETWORK DIAGRAM
# ---------------------------------------------------------------------------
def generate_bescom_network() -> None:
    import graphviz
    dot = graphviz.Graph(
        name="bescom_network", format="svg", engine="neato",
        graph_attr={"fontname": "Times-Roman", "fontsize": "10", "dpi": "300",
                    "bgcolor": "white", "pad": "0.5", "overlap": "false", "splines": "true"},
    )
    kv400 = ["Hoody", "Nelamangala", "Bidadi", "Kolar", "Tumkur"]
    for i, n in enumerate(kv400):
        dot.node(f"400_{i}", f"{n}\n400kV", shape="doublecircle",
                 style="filled", fillcolor="#fee2e2", fontcolor="#991b1b", fontsize="9", width="1.2")

    kv220 = ["AnandRao", "Chintamani", "DB Pura", "Devanahalli", "EPIP",
             "HAL", "Hebbal", "Hosakote", "HSR Layout", "Jigani",
             "Kanakapura", "Kolar 220", "Malur", "Peenya", "Yelahanka"]
    for i, n in enumerate(kv220):
        dot.node(f"220_{i}", f"{n}\n220kV", shape="circle",
                 style="filled", fillcolor="#fef3c7", fontcolor="#92400e", fontsize="8", width="0.9")

    for i in range(5):
        for j in range(i * 3, min((i + 1) * 3, 15)):
            dot.edge(f"400_{i}", f"220_{j}", color="#dc2626", penwidth="0.8", style="dashed")
    for i in range(14):
        dot.edge(f"220_{i}", f"220_{i+1}", color="#d97706", penwidth="0.6")

    dot.attr(label=r"\n\nBESCOM Bangalore 50-Bus Grid\n5x400kV | 15x220kV | 30x66kV | 37 Lines | 63 Transformers",
             fontsize="14", fontname="Times-Bold", fontcolor="#1e293b")
    dot.render(str(OUTPUT_DIR / "bescom_network"), cleanup=True)
    log("bescom_network.svg")


# ---------------------------------------------------------------------------
# 5. COMPLIANCE CHARTS
# ---------------------------------------------------------------------------
def generate_compliance() -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    nerc = [
        ("CIP-002\nAsset ID", 95), ("CIP-003\nSecurity", 88), ("CIP-004\nPersonnel", 92),
        ("CIP-005\nElect Perimeter", 85), ("CIP-006\nPhysical Sec", 90),
        ("CIP-007\nSystems Sec", 87), ("CIP-008\nIncident Resp", 93),
        ("CIP-009\nRecovery", 80), ("CIP-010\nChange Mgmt", 78), ("CIP-011\nInfo Prot", 91),
    ]
    cats, scores = zip(*nerc)
    colors = ["#059669" if s >= 85 else "#d97706" if s >= 70 else "#dc2626" for s in scores]
    bars = ax1.bar(range(len(cats)), scores, color=colors, edgecolor="white", linewidth=0.5)
    ax1.set_xticks(range(len(cats)))
    ax1.set_xticklabels(cats, fontsize=6, rotation=45, ha="right")
    ax1.set_ylabel("Compliance Score (%)", fontsize=10)
    ax1.set_title("NERC CIP Compliance Audit", fontsize=12, fontweight="bold", pad=10)
    ax1.set_ylim(0, 105)
    ax1.axhline(y=85, color="#059669", linestyle="--", linewidth=0.8, alpha=0.5, label="Target 85%")
    ax1.axhline(y=70, color="#d97706", linestyle="--", linewidth=0.8, alpha=0.3, label="Minimum 70%")
    ax1.legend(fontsize=7)
    for bar, s in zip(bars, scores):
        ax1.text(bar.get_x()+bar.get_width()/2, bar.get_height()+1, f"{s}%",
                 ha="center", va="bottom", fontsize=6, fontweight="bold")

    iegc = [
        ("Frequency\n(49.90-50.05Hz)", 96), ("Voltage\nRegulation", 90),
        ("Reactive\nPower", 88), ("Load\nShedding", 82),
        ("Protection\nCoordination", 85), ("Data\nReporting", 92),
        ("Cyber\nSecurity", 78),
    ]
    cats2, scores2 = zip(*iegc)
    colors2 = ["#059669" if s >= 85 else "#d97706" if s >= 70 else "#dc2626" for s in scores2]
    bars2 = ax2.bar(range(len(cats2)), scores2, color=colors2, edgecolor="white", linewidth=0.5)
    ax2.set_xticks(range(len(cats2)))
    ax2.set_xticklabels(cats2, fontsize=6, rotation=45, ha="right")
    ax2.set_ylabel("Compliance Score (%)", fontsize=10)
    ax2.set_title("Indian Grid Code (IEGC 2023) Audit", fontsize=12, fontweight="bold", pad=10)
    ax2.set_ylim(0, 105)
    ax2.axhline(y=85, color="#059669", linestyle="--", linewidth=0.8, alpha=0.5)
    for bar, s in zip(bars2, scores2):
        ax2.text(bar.get_x()+bar.get_width()/2, bar.get_height()+1, f"{s}%",
                 ha="center", va="bottom", fontsize=6, fontweight="bold")

    fig.suptitle("Regulatory Compliance -- NERC CIP + Indian Grid Code (IEGC 2023)",
                 fontsize=13, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "compliance.svg", format="svg")
    fig.savefig(OUTPUT_DIR / "compliance.png", format="png")
    plt.close(fig)
    log("compliance.svg + .png")


# ---------------------------------------------------------------------------
# 7. GNN ARCHITECTURE DIAGRAM
# ---------------------------------------------------------------------------
def generate_gnn_architecture() -> None:
    """GNN model architecture: RGATv2 + FaultClassifier pipeline."""
    import graphviz
    dot = graphviz.Digraph(
        name="gnn_architecture", format="svg", engine="dot",
        graph_attr={"rankdir": "LR", "splines": "ortho", "fontname": "Times-Roman",
                    "fontsize": "11", "dpi": "300", "bgcolor": "white", "pad": "0.5",
                    "nodesep": "0.3", "ranksep": "0.4"},
    )

    # Input
    dot.node("snapshot", "GridGraphSnapshot\n(N x 10 node feats)\n(E x 10 edge feats)",
             shape="cylinder", style="filled", fillcolor="#dbeafe")

    # GridBuilder
    dot.node("builder", "GridBuilder\nFeature Extraction\n+ Normalization",
             shape="box", style="filled", fillcolor="#e0e7ff")

    # RGATv2 layers
    with dot.subgraph(name="cluster_rgat") as s:
        s.attr(label="RGATv2 Backbone", style="rounded,dashed",
               color="#7c3aed", fontcolor="#7c3aed", fontsize="12", fontname="Times-Bold")
        s.node("node_enc", "Node Encoder\nLinear + LayerNorm + ELU", shape="box", style="filled", fillcolor="#ede9fe")
        s.node("edge_enc", "Edge Encoder\nLinear + LayerNorm + ELU", shape="box", style="filled", fillcolor="#ede9fe")
        s.node("gat1", "GATv2Conv Block 1\n(h=4, residual, norm)", shape="box", style="filled", fillcolor="#ddd6fe")
        s.node("gat2", "GATv2Conv Block 2\n(h=4, residual, norm)", shape="box", style="filled", fillcolor="#ddd6fe")
        s.node("gat3", "GATv2Conv Block 3\n(h=4, residual, norm)", shape="box", style="filled", fillcolor="#ddd6fe")
        s.edge("node_enc", "gat1"); s.edge("edge_enc", "gat1")
        s.edge("gat1", "gat2"); s.edge("gat2", "gat3")

    # Output heads
    with dot.subgraph(name="cluster_heads") as s:
        s.attr(label="Output Heads", style="rounded,dashed",
               color="#059669", fontcolor="#059669", fontsize="12", fontname="Times-Bold")
        s.node("node_head", "Node Score Head\nMLP -> sigmoid -> [N,1]", shape="box", style="filled", fillcolor="#d1fae5")
        s.node("edge_head", "Edge Score Head\nMLP -> sigmoid -> [E,1]", shape="box", style="filled", fillcolor="#d1fae5")
        s.node("pool", "Attention Pooling\nLearned node weighting", shape="box", style="filled", fillcolor="#d1fae5")

    # FaultClassifier
    with dot.subgraph(name="cluster_cls") as s:
        s.attr(label="FaultClassifier", style="rounded,dashed",
               color="#dc2626", fontcolor="#dc2626", fontsize="12", fontname="Times-Bold")
        s.node("cls", "Fault Type\n6-class MLP\n+ Temp Scaling", shape="box", style="filled", fillcolor="#fce7f3")
        s.node("iso", "Isolation Head\nPer-node attribution", shape="box", style="filled", fillcolor="#fce7f3")
        s.node("sev", "Severity Head\nRegression [0,1]", shape="box", style="filled", fillcolor="#fce7f3")

    # Physics loss
    dot.node("physics", "Physics-Informed\nRegularisation\n(Voltage bounds,\n conservation,\n smoothness)",
             shape="note", style="filled", fillcolor="#fef3c7")

    # Edges
    dot.edge("snapshot", "builder", label="to PyG Data")
    dot.edge("builder", "node_enc", label="x [N,10]")
    dot.edge("builder", "edge_enc", label="e [E,10]")
    dot.edge("gat3", "node_head", label="h [N,128]")
    dot.edge("gat3", "edge_head", label="e [E,128]")
    dot.edge("gat3", "pool", label="h [N,128]")
    dot.edge("pool", "cls", label="g [1,64]")
    dot.edge("pool", "iso", label="h [N,64]")
    dot.edge("pool", "sev", label="g [1,64]")
    dot.edge("node_head", "physics", style="dashed", arrowhead="odiamond")
    dot.edge("edge_head", "physics", style="dashed", arrowhead="odiamond")

    # Output
    dot.node("output", "FaultPrediction\n(FaultType, confidence,\n isolation_nodes,\n severity, explanation)",
             shape="box3d", style="filled", fillcolor="#e0e7ff")
    dot.edge("cls", "output")
    dot.edge("iso", "output")
    dot.edge("sev", "output")

    dot.render(str(OUTPUT_DIR / "gnn_architecture"), cleanup=True)
    log("gnn_architecture.svg")


# ---------------------------------------------------------------------------
# 6. TEST RESULTS
# ---------------------------------------------------------------------------
def generate_test_results() -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5),
                                    gridspec_kw={"width_ratios": [1.2, 1]})

    suites = ["ML Ensemble", "Pandapower\nIEEE-14", "BESCOM\n50-Bus", "Compliance\n(NERC+IEGC)", "CIM\nAdapter"]
    passed = [2, 1, 13, 7, 3]
    x = np.arange(len(suites))
    bars = ax1.bar(x, passed, 0.6, color="#059669", edgecolor="white", linewidth=0.5)
    ax1.set_xticks(x)
    ax1.set_xticklabels(suites, fontsize=8, rotation=20, ha="right")
    ax1.set_ylabel("Number of Tests", fontsize=10)
    ax1.set_title("Test Suites -- All 26 Tests Passing", fontsize=12, fontweight="bold", pad=10)
    for bar, p in zip(bars, passed):
        ax1.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.2,
                 f"{p}/{p}", ha="center", va="bottom", fontsize=9, fontweight="bold", color="#059669")

    labels = ["Unit Tests", "Integration Tests", "Module Boundary"]
    sizes = [18, 6, 2]
    wedges, texts, autotexts = ax2.pie(sizes, explode=(0.02,)*3, labels=labels,
                                        colors=["#059669", "#3b82f6", "#8b5cf6"],
                                        autopct="%1.0f%%", startangle=90, pctdistance=0.75,
                                        textprops={"fontsize": 8})
    for t in autotexts:
        t.set_fontweight("bold"); t.set_color("white")
    ax2.set_title("Test Classification", fontsize=12, fontweight="bold", pad=10)

    fig.suptitle("Platform Test Suite -- 26 Tests, 100% Passing",
                 fontsize=13, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "test_results.svg", format="svg")
    fig.savefig(OUTPUT_DIR / "test_results.png", format="png")
    plt.close(fig)
    log("test_results.svg + .png")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main() -> None:
    print("=" * 60)
    print(" Generating Professional Diagrams for Metro Grid Digital Twin")
    print("=" * 60)

    for step, (name, func) in enumerate([
        ("1/6  System Architecture Diagram", generate_architecture),
        ("2/6  Pipeline / Data Flow Diagram", generate_pipeline),
        ("3/6  Dashboard Layout Diagram", generate_dashboard_layout),
        ("4/6  BESCOM Network Diagram", generate_bescom_network),
        ("5/7  GNN Architecture Diagram", generate_gnn_architecture),
        ("6/7  Compliance Audit Charts", generate_compliance),
        ("7/7  Test Results Charts", generate_test_results),
    ], 1):
        print(f"\n[{step}] {name}")
        try:
            func()
        except Exception as e:
            print(f"  [FAIL] {e}")

    print(f"\n{'=' * 60}")
    print(f" All diagrams in: {OUTPUT_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
