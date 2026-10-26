# My agent: CloudShift Advisor (VMware to GCP Migration Copilot)
One-liner: An enterprise-grade migration architect backend API agent deployed to Vertex AI Agent Platform that ingests synthetic/sample RVTools summaries, conducts an adaptive discovery interview (<8 questions), calculates granular On-Prem vs Target GCP TCO comparisons, and renders rich A2UI cards (in ADK Web Playground & A2A clients) to recommend optimal Google Cloud landing zones (GCVE, GCE, GKE).

## Enterprise Architecture & Layer Harness

1. **Enterprise Harness (Memory, Sessions, Tools, Storage, Code Execution)**:
   - **Memory (Cross-Session)**: Vertex AI Memory Bank (`PreloadMemoryTool` + memory extraction callback) persists client constraints (datacenter exit deadline, budget ceiling, RTO/RPO SLA, licensing agreements, and past interview answers).
   - **Sessions**: Stateful session handling via Agent Platform Session Service for multi-turn discovery interviews.
   - **Tools (Function Tools)**: 
     - `parse_workload_metrics`: Normalizes and validates synthetic/sample RVTools input metrics (vCPUs, RAM, storage, OS distribution, IOPS).
     - `evaluate_target_landing_zone`: Decision logic scoring GCVE, GCE, and GKE based on operational readiness, container maturity, and VMware lock-in.
     - `calculate_tco_comparison`: Deterministic 3-year TCO modeling comparing On-Premise run-rate against Target GCP services with Committed Use Discounts (CUDs).
     - `generate_migration_checklist`: Generates landing zone, networking, IAM, and migration tool prerequisites (e.g., Migrate to Virtual Machines).
   - **Persistent Storage**: Firestore for persisting assessment records, customer migration portfolios, and landing zone blueprints.
   - **Code Execution (Sandbox)**: Agent Platform Code Execution sandbox for dynamic TCO sensitivity analysis, ROI break-even calculations, and GCVE cluster node sizing formulas.

2. **Google Generative Models Integration**:
   - Primary reasoning powered by **Gemini 3.8 Flash** via Vertex AI.
   - Multimodal and conceptual architecture generation: Visual Landing Zone & network topology diagrams (VPC peering, Cloud Interconnect, Transit VPC, GCVE/GCE subnet layouts).

3. **Evaluation & Quality Benchmarking**:
   - Evaluation datasets (`agents-cli eval`) measuring recommendation accuracy, TCO calculation consistency, and question relevance.
   - Iterative prompt calibration and tool trace evaluation.

4. **Agent-First UI (A2UI & Protocols)**:
   - **A2UI Protocol**: Emits v0.8 A2UI JSON cards and tables for side-by-side service comparisons (Cost, Velocity, Limitations, Readiness), natively rendered in ADK Web / Playground.
   - **Agent API Protocols**: Serves A2A (Agent-to-Agent) and ADK SSE streaming protocols directly from the core agent.

5. **Deployment Target**:
   - Single unified deployment: **Vertex AI Agent Platform (Agent Runtime / Reasoning Engine)**.
   - Interaction & Testing: ADK Web Playground (`agents-cli playground`), CLI (`agents-cli run`), and A2A API clients.

---

Tool coverage summary:
- Memory: Vertex AI Memory Bank (cross-session enterprise constraints)
- Tools: `parse_workload_metrics`, `evaluate_target_landing_zone`, `calculate_tco_comparison`, `generate_migration_checklist`
- Catalog/UI: A2UI comparison cards for GCVE, GCE, and GKE rendered in ADK Playground
- Storage: Firestore for workload and assessment state
- Sandbox: Agent Platform code execution for TCO & sizing math
- Deployment: Vertex AI Agent Platform (Agent Runtime)
- Model: Gemini 3.8 Flash
