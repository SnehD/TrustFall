# Trustfall — The AgentOps Command Center

**Track:** Productivity · **Division:** New Experience

## Inspiration
AI agents now change production systems. When one of them breaks something, responders must answer three questions fast: *what happened, was it allowed, and can I trust the evidence?* Flat dashboards scatter those answers across tabs.

## Problem
A valid log signature is often mistaken for approval. "This agent is who it says it is" is not the same as "this agent was permitted to do that."

## What it does
Trustfall puts you in a miniature infrastructure city. One service, Payments API, has failed. You pinch the building, meet the AI agent that touched production configuration, and see two separate verdicts: **IDENTITY VERIFIED** and **ACTION NOT AUTHORIZED**. A floating evidence graph links the agent, the change, the outage record, the permission policy, verification and recovery. Solid cyan links are facts backed by verified evidence; dashed amber links are hypotheses. You verify the evidence (including a tamper test), read evidence-cited AI findings, choose a recovery, watch the city heal, and export a Markdown/JSON incident report built from the live scenario state.

## Why VR
Incidents are relationship problems: agents, changes, policies, services and time. In 3D you can keep the city, the evidence graph and the inspector in view at once, and trace cause paths by reaching toward nodes instead of switching pages.

## Hand interaction design
Hands-first and seated-friendly: everything is within arm's reach; selection uses a pinch ray or a fingertip poke; controllers are optional. *Status: the XR hand-input paths are implemented but have not yet been validated on a headset or the emulator.*

## How it was built
WebXR with three.js for Meta Quest Browser. A Python reference backend defines the verification, policy, scenario, AI-validation and report logic; the same rules run in the browser's `engine.js`. 47 automated tests pass (31 Python, 16 JS).

## Evidence verification
Ed25519 signatures over canonical JSON (RFC 8785-compatible for float-free data), using the `cryptography` library and WebCrypto. Outcomes: VERIFIED, INVALID, MISSING, UNKNOWN. Demonstrated on tampered, unsigned, malformed, unknown-key and absent records. Fixture keys are deterministic test keys; no private keys are stored.

## AI functionality
The investigator output must pass a strict schema, cite known evidence IDs, and may only call something a "fact" if all cited evidence is VERIFIED. It can never override verification. Without an API key a deterministic fallback is used; **the demo uses this fallback**, not a live model.

## Infrastructure integration
A read-only Jenkins connector (env-var credentials, timeouts, normalized events, sample-data fallback) exists in the backend. It is tested with mocked responses only and is not verified against a live Jenkins.

## Current limitations
One fictional incident; recovery is simulated; not yet tested on a Quest headset; performance not measured; connector unverified live.

## Future improvements
Headset validation and profiling, live evidence ingestion, Kubernetes connector, more incident types, replay protection and key distribution.

## Target launch date
To be decided by the team (not yet scheduled).
