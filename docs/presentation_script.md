# Presentation Script — Metro Grid Digital Twin

**Total time**: ~8-10 minutes | **Slides**: 15

---

## Slide 1 — Title Slide (30s)

"Good morning, sir. I'm [Name], and we are presenting our Power System Analysis PBL project: **Metro Grid Digital Twin** — an autonomous real-time monitoring platform for metropolitan power transmission grids.

The system is built for the BESCOM Bangalore grid and was developed by our team of four — Varshini, Vedant, Sethu, and Aravind — under the guidance of Dr. Manjunatha C."

---

## Slide 2 — Outline (15s)

"The presentation is organized into four parts. First, we'll cover the introduction and problem statement, then our methodology including the ML ensemble and graph neural network, followed by the implementation and results, and finally our conclusion."

---

## Slide 3 — Introduction & Motivation (1 min)

"Here's the core problem: Bangalore's power grid serves over 10 million people through the BESCOM network — 50 substations connected by hundreds of kilometers of transmission lines. Currently, operators monitor this network through basic SCADA screens with manual threshold alerts.

The problem is that **anomalies propagate fast** in a transmission grid. A fault at one substation can cascade across the entire city within milliseconds. By the time an operator notices a voltage sag, the system might already be in a critical state.

Our solution is a **digital twin** — a real-time virtual replica of the physical grid that runs simulations continuously, detects anomalies automatically using AI, and explains what's happening in plain language. Think of it as a GPS navigation system for grid operators — not just showing where you are, but predicting problems before they happen."

---

## Slide 4 — Problem Statement (30s)

"Formally, we're solving three problems:

**One** — Power system monitoring today is **reactive**. Alarms trigger after a violation occurs, not before.

**Two** — Anomaly detection on a per-node basis is extremely difficult due to **class imbalance**. In any given snapshot, fewer than 1% of buses show anomalous behavior. Standard machine learning approaches fail because they just learn to predict 'normal' for everything and get 99% accuracy.

**Three** — Existing tools don't talk to each other. Simulation, ML detection, SCADA protocols, and compliance auditing are all separate systems with no integration."

---

## Slide 5 — Objectives (30s)

"We set four objectives:

1. Build a **real-time simulation** that runs a full AC powerflow every second
2. Implement an **ML-based anomaly detector** that catches voltage violations, loading issues, and fault conditions
3. Create an **interactive dashboard** that operators can actually use
4. Ensure the system is **production-grade** — with real SCADA protocols, cybersecurity, and compliance auditing built in"

---

## Slide 6 — Literature Survey (30s)

"We reviewed existing approaches. Digital twins exist in manufacturing and aerospace, but power grid twins are still an active research area. Most academic work uses offline analysis — running simulations, then analyzing results separately. Our contribution is integrating everything into a **live, real-time pipeline** that combines physics-based simulation with a Graph Neural Network for node-level anomaly localization."

---

## Slide 7 — Methodology: Detection Ensemble (1 min)

"This slide shows our first detection layer — a **four-detector ensemble** that works together:

1. **Physics Rule** — Simple voltage bounds: if a bus goes below 0.95 or above 1.05 per unit, flag it. This catches obvious violations instantly.
2. **Statistical Z-Score** — Maintains a moving window of the last 30 values for each bus. If a bus deviates significantly from its own history, that's suspicious even if it's within absolute bounds.
3. **Rate-of-Change** — Detects sudden jumps that might indicate a switching event or fault inception.
4. **LSTM Predictor** — A lightweight sequence model that predicts the next value and flags if the prediction looks anomalous.

The ensemble achieves an average precision of 0.92 and AUC of 0.72."

---

## Slide 8 — Methodology: RGATv2 GNN (1.5 min)

"This is the most technically interesting part — our **Graph Neural Network**.

A transmission grid is naturally a graph: buses are nodes, transmission lines are edges. A GNN is designed to process exactly this kind of structured data. Each node starts with 10 features — voltage magnitude, angle, power injections, and so on. Through 3 attention layers, each node learns to **attend to its neighbors**, weighting which connections matter more.

The key innovation here is **physics-informed loss**. We don't just train the network to minimize classification error — we also penalize it when its internal representations violate physical laws. For example, if the model says a bus has a problem but its voltage is perfectly normal, that gets penalized.

Training was challenging because less than 1% of nodes are anomalous in any snapshot. We solved this through **decoupled class balancing** — we use a WeightedRandomSampler to ensure each batch has roughly equal normal and anomalous samples, while keeping a mild positive class weight of 2.0 in the loss function. The original approach had both a sampler AND a weight of 18.1 — which double-counted and caused more false alarms.

After 50 epochs of training on 6,000 synthetic samples, we achieved:

- **93.4% node-level accuracy** — the model correctly identifies whether each individual bus is normal or anomalous
- **9.5% precision** — up from 7.1% in the original version, a 34% relative improvement
- **F1 score of 0.151** — up 19% from the baseline

You'll notice the precision is still modest at 9.5%. This is because the task is inherently hard — we're asking the model to identify exactly which bus has a problem when the perturbation affects the entire grid's voltage profile. But importantly, we can **adjust the threshold** depending on the use case: at threshold 0.05, we catch 100% of anomalies (useful for safety screening); at threshold 0.60, we get the best precision (useful for actionable alerts)."

---

## Slide 9 — Implementation (30s)

"The system is implemented using:

- **Python 3.12 + FastAPI** for the backend — handles simulation, detection, and WebSocket streaming
- **React 19 + TypeScript + D3.js** for the dashboard
- **pandapower** for AC powerflow simulation
- **PyTorch + PyTorch Geometric** for the GNN

The architecture is modular — each component (simulation, detection, compliance, SCADA) is a separate Python package."

---

## Slide 10 — Results: Voltage Profiles (30s)

"Here we see voltage profiles over 60 simulation ticks on the IEEE 14-bus system. The green band shows the normal operating range. Several buses, especially bus 14, show significant voltage sags below the lower bound. About 8% of ticks trigger physics-rule violations, and 92% of those violations are concentrated on just 4 terminal buses — consistent with the physics of a transmission grid where the ends of the network are most vulnerable."

---

## Slide 11 — Results: Timing Benchmark (30s)

"Performance matters for a real-time system. Our IEEE-14 simulation runs in **20 milliseconds per tick** on average — well under our 100ms target. The BESCOM 50-bus model takes about 40ms. Both are fast enough for real-time operation.

The bottleneck is not simulation but data loading — the BESCOM model reads CSV load profiles from disk, which takes about 30ms. In production, this would use a database instead."

---

## Slide 12 — ROC & Anomaly Performance (30s)

"The ROC curves show the trade-off between true positive rate and false positive rate. The ML ensemble (blue) outperforms pure physics rules (orange) across all operating points — AUC of 0.72 vs 0.65. The physics plus ML combination is even better.

The right plot shows the anomaly detection rate across different severity levels. High-severity anomalies are caught reliably; low-severity ones require the full ML pipeline."

---

## Slide 13 — Results: GNN Training (1 min)

"This slide shows the GNN training curves. The left plot shows training and validation loss over 50 epochs — both decrease consistently without overfitting, thanks to the physics-informed regularization.

The right plot shows validation accuracy and F1 score. Validation accuracy reaches 93.4%, while F1 peaks at 0.151.

The table summarizes the key metrics. Note the **optimal threshold of 0.60** — this was found by searching 50 candidate thresholds on the validation set. The original model trained without threshold tuning and without decoupled balancing, which is why the precision was lower."

---

## Slide 14 — Results: Compliance Audit (30s)

"As part of the platform, we built a compliance auditing module for both US (NERC CIP) and Indian (IEGC 2023) grid standards. On average, the simulated system scores 86.7% on NERC CIP and 87.3% on IEGC 2023. The weakest areas are configuration management and cyber security — both are expected for a research prototype and would be addressed in production deployment."

---

## Slide 15 — Conclusion & Future Work (30s)

"To conclude: We built a production-grade digital twin that integrates real-time simulation, ML-based anomaly detection with a graph neural network, real SCADA protocols, and compliance auditing into a single platform.

**Key achievements**:
- Sub-20ms per-tick simulation
- 93.4% GNN node-level accuracy with 9.5% precision
- ML ensemble with 0.92 average precision and 72.6% recall
- Built-in compliance for NERC CIP and Indian Grid Code

**Future work** includes real-time GNN inference in the tick pipeline, scaling to 500+ bus systems, and using gradient-based explanation methods like GNNExplainer for even better node-level attribution.

Thank you. We're happy to take questions."

---

## Q&A Prep — Common Questions

### "Why is precision only 9.5%?"
Because we're doing **node-level** classification on a small (14-bus) grid where a perturbation at one bus affects EVERY bus's voltage. The model correctly flags the tick as anomalous (graph-level) but struggles to pin it to exactly one node. Think of it like finding which person in a crowded room started coughing — you know something happened, but localizing it is harder. We improved from 7.1% to 9.5% with better training, and threshold tuning lets us trade precision for recall depending on the application.

### "Why not use XGBoost or Random Forest?"
Tree-based models don't naturally handle the graph structure. A GNN explicitly models the connectivity — bus 4 is connected to bus 5 through a specific line with specific impedance. That topology matters. A Random Forest would just see 10 features per bus independently.

### "Did you test on real BESCOM data?"
The BESCOM model uses real SCADA data for network topology and load profiles. For anomaly detection training, we used synthetic perturbations injected into the IEEE-14 model because we need labeled ground truth. Deploying on live BESCOM data would require operational approval.

### "Why use Python 3.12 and not 3.14?"
PyTorch with CUDA support is only available for Python 3.12 on this system. The RTX 4050 GPU requires CUDA 12.1, which ships with PyTorch 2.5.1 for Python 3.12. Python 3.14 doesn't have CUDA-compatible PyTorch yet.

### "How many lines of code?"
The platform has approximately 15,000 lines across Python backend, TypeScript dashboard, and infrastructure code.

### "Is this ready for actual deployment?"
It's a production-grade prototype. The simulation and dashboard are functional. For real deployment, you'd need: (1) grid-specific calibration of the GNN, (2) integration with actual RTU/PMU data streams, (3) cybersecurity hardening, and (4) regulatory certification. The architecture is designed for this path.
