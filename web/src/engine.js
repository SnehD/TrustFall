/* Trustfall engine: scenario state, verification, recovery, report. Pure logic, no rendering.
 * UMD so it runs in the browser (window.TrustfallEngine) and in Node (tests). ES5-safe syntax. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.TrustfallEngine = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  function clone(o) { return JSON.parse(JSON.stringify(o)); }

  // Canonical JSON identical to backend/app/verification/canonical.py (sorted keys, no spaces, no floats).
  function canonical(v) {
    if (v === null || typeof v === 'boolean' || typeof v === 'string') return JSON.stringify(v);
    if (typeof v === 'number') {
      if (!isFinite(v) || Math.floor(v) !== v) throw new Error('floats not allowed');
      return String(v);
    }
    if (Array.isArray(v)) return '[' + v.map(canonical).join(',') + ']';
    var keys = Object.keys(v).sort();
    return '{' + keys.map(function (k) { return JSON.stringify(k) + ':' + canonical(v[k]); }).join(',') + '}';
  }
  function canonicalBytes(rec) {
    var body = {};
    Object.keys(rec).forEach(function (k) { if (k !== 'signature') body[k] = rec[k]; });
    return new TextEncoder().encode(canonical(body));
  }
  function b64(s) {
    var bin = atob(s), out = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }

  var REQUIRED = ['evidence_id', 'type', 'timestamp', 'actor', 'payload', 'signing_key_id'];

  // Live Ed25519 verification via WebCrypto when the browser supports it. Same statuses as the Python engine.
  async function verifyRecordLive(rec, keyring) {
    var id = rec && typeof rec.evidence_id === 'string' ? rec.evidence_id : '?';
    if (!rec || typeof rec !== 'object') return { evidence_id: id, status: 'INVALID', reason: 'malformed: not an object' };
    var absent = REQUIRED.filter(function (f) { return !(f in rec); });
    if (absent.length) return { evidence_id: id, status: 'INVALID', reason: 'malformed: missing ' + absent.join(',') };
    if (!rec.signature) return { evidence_id: id, status: 'MISSING', reason: 'signature is missing' };
    var pub = keyring[rec.signing_key_id];
    if (!pub) return { evidence_id: id, status: 'UNKNOWN', reason: "signing key '" + rec.signing_key_id + "' is not configured" };
    try {
      var key = await crypto.subtle.importKey('raw', b64(pub), { name: 'Ed25519' }, false, ['verify']);
      var ok = await crypto.subtle.verify({ name: 'Ed25519' }, key, b64(rec.signature), canonicalBytes(rec));
      return ok
        ? { evidence_id: id, status: 'VERIFIED', reason: 'signature valid for configured key (says nothing about authorization)' }
        : { evidence_id: id, status: 'INVALID', reason: 'signature does not match record content' };
    } catch (e) {
      if (e && (e.name === 'NotSupportedError' || e.name === 'SyntaxError')) throw e; // caller falls back
      return { evidence_id: id, status: 'INVALID', reason: 'malformed: ' + (e && e.message) };
    }
  }

  function webCryptoEd25519Available() {
    return typeof crypto !== 'undefined' && crypto.subtle && typeof crypto.subtle.importKey === 'function';
  }

  function evaluateAuthorization(agentId, action, scope, grants, identityVerified) {
    var list = grants[agentId] || [];
    for (var i = 0; i < list.length; i++) {
      if (list[i].action === action && list[i].scopes.indexOf(scope) >= 0)
        return { identity_verified: identityVerified, authorized: true, reason: 'grant ' + action + " on scope '" + scope + "' present" };
    }
    return { identity_verified: identityVerified, authorized: false,
      reason: 'no grant for ' + action + " on scope '" + scope + "' (identity verification is irrelevant to authorization)" };
  }

  function Engine(data) {
    this.data = data;
    this.records = clone(data.records);
    this.health = clone(data.initial_health);
    this.status = 'OPEN';
    this.log = data.timeline.map(function (t) { return { t: t.time, text: t.text, evidence: t.evidence.slice() }; });
    this.actions = [];
    this.agentIsolated = false;
    this.verification = clone(data.verification_precomputed);
    this.verificationSource = 'precomputed by Python backend';
    this.listeners = [];
  }

  Engine.prototype.onChange = function (fn) { this.listeners.push(fn); };
  Engine.prototype._emit = function () { var s = this; this.listeners.forEach(function (f) { f(s); }); };

  // Re-verify all required evidence. Uses live WebCrypto if possible, else the precomputed backend results.
  Engine.prototype.verifyAll = async function (recordsOverride) {
    var recs = recordsOverride || this.records, self = this, out = {}, live = false;
    if (webCryptoEd25519Available()) {
      try {
        for (var i = 0; i < this.data.required_evidence.length; i++) {
          var id = this.data.required_evidence[i];
          var rec = recs.filter(function (r) { return r.evidence_id === id; })[0];
          out[id] = rec ? await verifyRecordLive(rec, this.data.public_keys)
                        : { evidence_id: id, status: 'MISSING', reason: 'required evidence record not available' };
        }
        live = true;
      } catch (e) { live = false; out = {}; }
    }
    if (!live) return { results: clone(this.data.verification_precomputed), source: 'precomputed by Python backend (browser lacks Ed25519)' };
    if (!recordsOverride) { this.verification = out; this.verificationSource = 'verified live in this browser (WebCrypto Ed25519)'; this._emit(); }
    return { results: out, source: 'verified live in this browser (WebCrypto Ed25519)' };
  };

  // Tamper demo: edit EV-003 scope in a COPY and re-verify. Original state is untouched.
  Engine.prototype.tamperDemo = async function () {
    var copy = clone(this.records);
    copy.forEach(function (r) { if (r.evidence_id === 'EV-003') r.payload.scope = 'staging'; });
    var r = await this.verifyAll(copy);
    if (r.source.indexOf('precomputed') === 0) return { result: this.data.tamper_demo.result, source: 'precomputed by Python backend' };
    return { result: r.results['EV-003'], source: r.source };
  };

  Engine.prototype.identityVerified = function () { return this.verification['EV-002'].status === 'VERIFIED'; };

  Engine.prototype.authorization = function () {
    var ch = this.records.filter(function (r) { return r.evidence_id === 'EV-003'; })[0];
    return evaluateAuthorization(ch.actor, ch.payload.action, ch.payload.scope, this.data.agent_grants_map || { 'agent-opsbot-7': this.data.agent.grants }, this.identityVerified());
  };

  Engine.prototype.recover = function (option) {
    var opts = this.data.recovery_options;
    if (!opts[option]) throw new Error('unknown recovery option ' + option);
    if (this.status === 'RESOLVED') return { option: option, effect: 'already resolved', resolved: true };
    this.actions.push(option);
    var res;
    if (option === 'restore_previous_config') {
      if (this.verification['EV-006'].status !== 'VERIFIED') {
        res = { option: option, effect: 'refused: snapshot EV-006 not verified', resolved: false };
      } else {
        var h = this.health;
        ['payments-api', 'orders-service', 'edge-gateway', 'analytics'].forEach(function (s) { h[s] = 'healthy'; });
        this.status = 'RESOLVED';
        this.log.push({ t: '2026-11-17T09:31:00Z', text: 'Recovery (simulated): previous config restored from EV-006', evidence: ['EV-006'] });
        res = { option: option, effect: 'service restored (simulated)', resolved: true };
      }
    } else if (option === 'isolate_agent') {
      this.agentIsolated = true;
      this.log.push({ t: '2026-11-17T09:26:00Z', text: 'Agent OpsBot-7 isolated (simulated); outage persists', evidence: [] });
      res = { option: option, effect: 'agent isolated; outage persists', resolved: false };
    } else {
      res = { option: option, effect: 'no change', resolved: false };
    }
    this._emit();
    return res;
  };

  Engine.prototype.neighbors = function (nodeId) {
    var ids = {}; ids[nodeId] = true;
    this.data.graph.edges.forEach(function (e) {
      if (e.from === nodeId) ids[e.to] = true;
      if (e.to === nodeId) ids[e.from] = true;
    });
    return Object.keys(ids);
  };
  Engine.prototype.edgesOf = function (nodeId) {
    return this.data.graph.edges.filter(function (e) { return e.from === nodeId || e.to === nodeId; });
  };
  Engine.prototype.traceOrder = function () { return ['agent', 'change', 'policy', 'event', 'service', 'recovery']; };

  Engine.prototype.report = function () {
    var auth = this.authorization(), inv = this.data.investigation;
    return {
      incident_id: this.data.incident.id,
      title: this.data.incident.title,
      timeline: clone(this.log),
      affected_service: { id: 'payments-api', label: this.data.services['payments-api'].label, health: this.health['payments-api'] },
      agent: { id: this.data.agent.agent_id, name: this.data.agent.name, identity_verified: auth.identity_verified },
      permission_findings: { authorized: auth.authorized, reason: auth.reason },
      evidence_verification: clone(this.verification),
      suspected_root_cause: inv.suspected_root_cause,
      root_cause_source: inv.source,
      supporting_evidence: inv.supporting_evidence.slice(),
      recovery_actions: this.actions.slice(),
      resolution_status: this.status === 'RESOLVED' ? 'RESOLVED' : 'UNRESOLVED',
      remaining_uncertainties: inv.unresolved_questions.slice()
    };
  };

  Engine.reportToMarkdown = function (r) {
    var L = ['# Incident ' + r.incident_id + ': ' + r.title, '', '**Status:** ' + r.resolution_status, '',
      '## Affected service', r.affected_service.label + ' (' + r.affected_service.health + ')', '',
      '## Agent', r.agent.name + ' (`' + r.agent.id + '`) - identity verified: ' + r.agent.identity_verified, '',
      '## Permission findings', 'Authorized: ' + r.permission_findings.authorized + '. ' + r.permission_findings.reason, '', '## Timeline'];
    r.timeline.forEach(function (e) { L.push('- ' + e.t + ' - ' + e.text + ' [' + e.evidence.join(', ') + ']'); });
    L.push('', '## Evidence verification');
    Object.keys(r.evidence_verification).forEach(function (k) { var v = r.evidence_verification[k]; L.push('- ' + k + ': **' + v.status + '** - ' + v.reason); });
    L.push('', '## Suspected root cause', r.suspected_root_cause + ' (source: ' + r.root_cause_source + ')', '',
      '## Supporting evidence', r.supporting_evidence.join(', ') || 'none', '',
      '## Recovery actions', r.recovery_actions.join(', ') || 'none', '', '## Remaining uncertainties');
    r.remaining_uncertainties.forEach(function (u) { L.push('- ' + u); });
    L.push('', '_A VERIFIED signature proves record integrity for a configured key, not safety, authorization, or causation._');
    return L.join('\n');
  };

  Engine.canonical = canonical;
  Engine.evaluateAuthorization = evaluateAuthorization;
  return Engine;
});
