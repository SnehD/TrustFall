// Run: node web/tests/engine.test.js   (no dependencies; ES5-compatible for old Node)
var assert = require('assert');
var fs = require('fs');
var path = require('path');
var Engine = require('../src/engine.js');
var data = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/scenario.json'), 'utf8'));
var passed = 0, failed = 0;
function t(name, fn) {
  try { fn(); passed++; console.log('PASS ' + name); }
  catch (e) { failed++; console.log('FAIL ' + name + ': ' + e.message); }
}
function fresh() { return new Engine(data); }

t('initial state: payments-api failed, status OPEN', function () {
  var e = fresh(); assert.equal(e.health['payments-api'], 'failed'); assert.equal(e.status, 'OPEN');
});
t('timeline has 7 steps in order', function () {
  var e = fresh(); assert.equal(e.log.length, 7); assert.ok(e.log[2].text.indexOf('PRODUCTION') > 0);
});
t('identity verified but action NOT authorized', function () {
  var a = fresh().authorization(); assert.strictEqual(a.identity_verified, true); assert.strictEqual(a.authorized, false);
});
t('staging write would be authorized', function () {
  var a = Engine.evaluateAuthorization('agent-opsbot-7', 'config.write', 'staging', { 'agent-opsbot-7': data.agent.grants }, true);
  assert.strictEqual(a.authorized, true);
});
t('EV-007 missing, others verified (precomputed)', function () {
  var v = fresh().verification; assert.equal(v['EV-007'].status, 'MISSING'); assert.equal(v['EV-003'].status, 'VERIFIED');
});
t('canonicalization sorts keys, rejects floats', function () {
  assert.equal(Engine.canonical({ b: 1, a: [true, null, 'x'] }), '{"a":[true,null,"x"],"b":1}');
  assert.throws(function () { Engine.canonical({ x: 1.5 }); });
});
t('restore recovery resolves and heals dependents', function () {
  var e = fresh(), r = e.recover('restore_previous_config');
  assert.ok(r.resolved); assert.equal(e.status, 'RESOLVED');
  Object.keys(e.health).forEach(function (k) { assert.equal(e.health[k], 'healthy'); });
  assert.ok(e.log[e.log.length - 1].text.indexOf('restored') > 0);
});
t('isolate does not fix outage', function () {
  var e = fresh(); e.recover('isolate_agent');
  assert.equal(e.health['payments-api'], 'failed'); assert.equal(e.status, 'OPEN'); assert.ok(e.agentIsolated);
});
t('continue investigation changes nothing', function () {
  var e = fresh(), n = e.log.length; e.recover('continue_investigation'); assert.equal(e.log.length, n); assert.equal(e.status, 'OPEN');
});
t('restore refused when snapshot not verified', function () {
  var e = fresh(); e.verification['EV-006'].status = 'INVALID';
  assert.ok(!e.recover('restore_previous_config').resolved); assert.equal(e.health['payments-api'], 'failed');
});
t('unknown option throws', function () { assert.throws(function () { fresh().recover('nuke'); }); });
t('graph neighbors and edges', function () {
  var e = fresh(), n = e.neighbors('change');
  ['agent', 'policy', 'event', 'verify', 'recovery'].forEach(function (x) { assert.ok(n.indexOf(x) >= 0, x); });
  assert.ok(e.edgesOf('change').some(function (x) { return x.kind === 'hypothesis'; }));
});
t('every graph edge cites known evidence', function () {
  var ids = data.required_evidence;
  data.graph.edges.forEach(function (ed) { assert.ok(ed.evidence.length > 0); ed.evidence.forEach(function (x) { assert.ok(ids.indexOf(x) >= 0); }); });
});
t('report reflects state before and after recovery', function () {
  var e = fresh(), r0 = e.report();
  assert.equal(r0.resolution_status, 'UNRESOLVED'); assert.equal(r0.affected_service.health, 'failed');
  assert.equal(r0.permission_findings.authorized, false);
  e.recover('restore_previous_config');
  var r1 = e.report();
  assert.equal(r1.resolution_status, 'RESOLVED'); assert.equal(r1.affected_service.health, 'healthy');
  assert.deepEqual(r1.recovery_actions, ['restore_previous_config']);
  var md = Engine.reportToMarkdown(r1);
  assert.ok(md.indexOf('RESOLVED') > 0 && md.indexOf('EV-007: **MISSING**') > 0);
  JSON.stringify(r1);
});
t('AI findings cite evidence and include a hypothesis', function () {
  var f = data.investigation.findings;
  assert.ok(f.every(function (x) { return x.evidence_ids.length > 0; }));
  assert.ok(f.some(function (x) { return x.kind === 'hypothesis'; }));
  assert.equal(data.investigation.source, 'deterministic-fallback');
});
t('tamper demo precomputed result is INVALID', function () {
  assert.equal(data.tamper_demo.result.status, 'INVALID');
});
console.log('\n' + passed + ' passed, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
