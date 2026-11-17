# User Guide

1. Read the welcome card; **Begin investigation** (pinch it).
2. The banner says **PAYMENTS API FAILED**. Pinch the red building. The left panel opens the **Agent inspector**: IDENTITY VERIFIED but ACTION NOT AUTHORIZED. These are different questions.
3. Pinch nodes in the floating graph. Connected nodes stay bright. The right panel shows the evidence IDs with their verification status and *why* nodes connect, tagged FACT (solid cyan) or HYPOTHESIS (dashed amber). **Trace sequence** steps through the incident.
4. **VERIFY** tab: statuses for EV-001…EV-007 (EV-007, the approval ticket, is MISSING). **Tamper test** edits a copy of EV-003 and shows INVALID.
5. **AI** tab: root-cause summary, each finding labelled FACT/HYPOTHESIS with evidence IDs, confidence and unresolved questions. Shown source: deterministic fallback unless a validated AI result is provided.
6. **RECOVER** tab: choose *Restore config* (resolves, simulated), *Isolate agent* (outage persists), or *Keep investigating*.
7. **REPORT** tab: live summary; export Markdown or JSON.
8. Restart: reload the page.

Desktop preview: mouse click substitutes for pinch — a development convenience, not hand tracking.
