"""Browser interaction tests via Chrome DevTools Protocol (Edge headless). Needs: pip install websockets.
Usage: python web/tests/browser_test.py   (serve web/ on :8765 first)
Part 1: desktop real mouse events. Part 2: IWER-emulated Quest 3 XR session with emulated hand input.
IWER is an EMULATOR; passing here does not prove behaviour on a physical headset."""
import asyncio, json, subprocess, sys, time, urllib.request, os, tempfile
import websockets

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 9333
BASE = "http://localhost:8765/"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))


class CDP:
    def __init__(self, ws): self.ws, self.i, self.errors = ws, 0, []
    async def send(self, method, **params):
        self.i += 1; mid = self.i
        await self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("method") == "Runtime.exceptionThrown":
                self.errors.append(msg["params"]["exceptionDetails"].get("exception", {}).get("description", "exception"))
            if msg.get("method") == "Runtime.consoleAPICalled" and msg["params"]["type"] == "error":
                self.errors.append(" ".join(str(a.get("value", a.get("description", ""))) for a in msg["params"]["args"]))
            if msg.get("id") == mid:
                if "error" in msg: raise RuntimeError(msg["error"])
                return msg["result"]
    async def js(self, expr):
        r = await self.send("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in r: raise RuntimeError(r["exceptionDetails"].get("exception", {}).get("description"))
        return r["result"].get("value")
    async def goto(self, url):
        await self.send("Page.navigate", url=url)
        for _ in range(100):
            await asyncio.sleep(0.3)
            if await self.js("!!(window.__tf && window.__tf.engine)"): return
        raise RuntimeError("app did not boot")
    async def click(self, x, y):
        for t in ("mouseMoved", "mousePressed", "mouseReleased"):
            await self.send("Input.dispatchMouseEvent", type=t, x=x, y=y, button="left", clickCount=1, buttons=1 if t == "mousePressed" else 0)
            await asyncio.sleep(0.05)


PROJECT_JS = """
(function(){const T=__tf.THREE;
 window.__proj=(v)=>{const p=v.clone().project(__tf.camera);return [(p.x+1)/2*innerWidth,(1-p.y)/2*innerHeight];};
 window.__bldXY=(id)=>{const v=new T.Vector3();__tf.bld[id].body.getWorldPosition(v);return __proj(v);};
 window.__nodeXY=(id)=>{const v=new T.Vector3();__tf.gnodes[id].m.getWorldPosition(v);return __proj(v);};
 window.__btnXY=(panel,id)=>{const p=__tf.panels[panel],b=p.buttons.find(x=>x.id===id);if(!b)return null;
   const v=new T.Vector3(((b.x+b.w/2)/p.pw-0.5)*p.wM,(0.5-(b.y+b.h/2)/p.ph)*p.hM,0);p.mesh.localToWorld(v);return __proj(v);};
 return true;})()
"""


async def desktop_tests(c):
    await c.goto(BASE + "index.html?onboard=1")
    await c.js(PROJECT_JS)
    check("D1 app boots with onboarding visible", await c.js("__tf.S.onboard === true"))
    await c.click(*await c.js("__btnXY('onboard','begin')"))
    check("D2 click Begin dismisses onboarding", await c.js("__tf.S.onboard === false && __tf.panels.onboard.mesh.visible === false"))
    await c.click(*await c.js("__bldXY('payments-api')"))
    check("D3 click Payments building selects service + graph node", await c.js("__tf.S.selSvc==='payments-api' && __tf.S.selNode==='service'"))
    await c.click(*await c.js("__nodeXY('change')"))
    check("D4 click graph node 'change' selects it", await c.js("__tf.S.selNode==='change'"))
    check("D5 neighbours stay opaque, others dim", await c.js("(()=>{const g=__tf.gnodes;const nb=__tf.engine.neighbors('change');return Object.keys(g).every(k=>(g[k].mat.opacity===1)===nb.includes(k));})()"))
    await c.click(*await c.js("__btnXY('right','rtab:VERIFY')"))
    check("D6 click VERIFY tab", await c.js("__tf.S.rtab==='VERIFY'"))
    await c.click(*await c.js("__btnXY('right','tamper')"))
    await asyncio.sleep(0.8)
    check("D7 tamper test reports INVALID", await c.js("__tf.S.tamper && __tf.S.tamper.result.status==='INVALID'"))
    check("D8 tamper did not alter real state (EV-003 still VERIFIED, scope production)", await c.js("__tf.engine.verification['EV-003'].status==='VERIFIED' && __tf.engine.records.find(r=>r.evidence_id==='EV-003').payload.scope==='production'"))
    await c.click(*await c.js("__btnXY('right','verify')"))
    await asyncio.sleep(0.8)
    check("D9 live verification: EV-007 MISSING, EV-001..006 VERIFIED", await c.js("(()=>{const v=__tf.engine.verification;return v['EV-007'].status==='MISSING'&&['1','2','3','4','5','6'].every(n=>v['EV-00'+n].status==='VERIFIED');})()"))
    await c.click(*await c.js("__btnXY('right','rtab:RECOVER')"))
    await c.click(*await c.js("__btnXY('right','rec:isolate_agent')"))
    check("D10 isolate: outage persists", await c.js("__tf.engine.status==='OPEN' && __tf.engine.health['payments-api']==='failed' && __tf.engine.agentIsolated"))
    await c.click(*await c.js("__btnXY('right','rec:restore_previous_config')"))
    check("D11 restore resolves, city healthy", await c.js("__tf.engine.status==='RESOLVED' && Object.values(__tf.engine.health).every(h=>h==='healthy')"))
    check("D12 3D building turned green after recovery", await c.js("__tf.bld['payments-api'].mat.emissive.getHex()===0x2fe38a"))
    check("D13 recovery buttons disabled after resolve", await c.js("__tf.panels.right.buttons.filter(b=>b.id.startsWith('rec:')).every(b=>b.disabled)"))
    await c.click(*await c.js("__btnXY('right','rtab:REPORT')"))
    check("D14 report reflects resolved state", await c.js("(()=>{const r=__tf.engine.report();return r.resolution_status==='RESOLVED'&&r.recovery_actions.join()==='isolate_agent,restore_previous_config';})()"))
    await c.click(*await c.js("__btnXY('right','rtab:EVIDENCE')"))
    for _ in range(7):
        await c.click(*await c.js("__btnXY('right','trace')"))
    check("D15 trace steps visit 6 nodes then wraps", await c.js("__tf.S.traceI===0"))
    check("D16 input label is honest (desktop mouse, not hand tracking)", await c.js("__tf.S.inputMode.indexOf('NOT hand tracking')>0"))
    check("D17 no console/JS errors (desktop)", not c.errors, "; ".join(c.errors[:3]))


async def xr_tests(c):
    c.errors.clear()
    await c.goto(BASE + "xr-test.html?onboard=0")
    await c.js(PROJECT_JS)
    check("X1 IWER Quest 3 emulator reports immersive-vr supported", await c.js("navigator.xr.isSessionSupported('immersive-vr')"))
    btn = await c.js("(()=>{const b=[...document.querySelectorAll('button')].find(x=>/ENTER VR/i.test(x.textContent));if(!b)return null;const r=b.getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2];})()")
    check("X2 'Enter VR' button present", btn is not None)
    if not btn: return
    await c.click(*btn)
    for _ in range(40):
        await asyncio.sleep(0.25)
        if await c.js("__tf.renderer.xr.isPresenting"): break
    check("X3 XR session started (emulated)", await c.js("__tf.renderer.xr.isPresenting"))
    if not await c.js("__tf.renderer.xr.isPresenting"): return
    await asyncio.sleep(1.0)
    kinds = await c.js("__tf.xr.ctrls.map(c=>c.userData.kind)")
    check("X4 input sources detected as hand-tracking", "hand-pinch" in kinds, str(kinds))
    check("X5 UI reports hand tracking input", await c.js("__tf.S.inputMode.indexOf('Hand tracking')===0"), await c.js("__tf.S.inputMode"))
    # pinch-ray tests: calibrate the emulated hand so its targetRay passes through a world point, then pinch.
    await c.js("""window.__aim=async(tx,ty)=>{const d=window.__dev,T=__tf.THREE,h=d.hands.right;h.quaternion.set(0,0,0,1);h.position.set(tx,ty,-0.3);await new Promise(r=>setTimeout(r,1100));
      const sleep=ms=>new Promise(r=>setTimeout(r,ms));await sleep(1100);
      for(let i=0;i<3;i++){const c=__tf.xr.ctrls.find(x=>x.userData.kind==='hand-pinch'&&x.userData.handedness==='right');const o=new T.Vector3().setFromMatrixPosition(c.matrixWorld);
        h.position.x+=tx-o.x;h.position.y+=ty-o.y;await sleep(1100);}
      const c2=__tf.xr.ctrls.find(x=>x.userData.kind==='hand-pinch'&&x.userData.handedness==='right');const o2=new T.Vector3().setFromMatrixPosition(c2.matrixWorld);return [o2.x,o2.y,o2.z];};
      window.__pinch=async()=>{const sleep=ms=>new Promise(r=>setTimeout(r,ms));window.__dev.hands.right.updatePinchValue(1);await sleep(1200);window.__dev.hands.right.updatePinchValue(0);await sleep(1200);};true""")
    async def aim_and_pinch(wx, wy):
        o = await c.js(f"__aim({wx},{wy})")
        await c.js("__pinch()")
        return o
    def tgt(expr): return c.js(f"(()=>{{const v=new __tf.THREE.Vector3();{expr}.getWorldPosition(v);return [v.x,v.y];}})()")
    # empty space must do nothing
    s0 = await c.js("JSON.stringify([__tf.S.selSvc,__tf.S.selNode,__tf.S.rtab])")
    await aim_and_pinch(2.5, 0.4)
    check("X6a pinch at empty space changes nothing", await c.js("JSON.stringify([__tf.S.selSvc,__tf.S.selNode,__tf.S.rtab])") == s0)
    x, y = await tgt("__tf.bld['payments-api'].body")
    o = await aim_and_pinch(x, y + 0.02)
    check("X6b pinch ray at Payments building selects payments-api", await c.js("__tf.S.selSvc==='payments-api'"), f"ray origin {o} target {(x, y)}")
    x, y = await tgt("__tf.bld['config-store'].body")
    await aim_and_pinch(x, y)
    check("X6c pinch ray at Config Store building selects config-store (different target, different result)", await c.js("__tf.S.selSvc==='config-store' && __tf.S.selNode==='change'"))
    x, y = await tgt("__tf.gnodes['policy'].m")
    await aim_and_pinch(x, y)
    check("X6d pinch ray at graph node 'policy' selects it", await c.js("__tf.S.selNode==='policy'"))
    pb = await c.js("(()=>{const T=__tf.THREE,p=__tf.panels.right,b=p.buttons.find(x=>x.id==='rtab:AI');const v=new T.Vector3(((b.x+b.w/2)/p.pw-0.5)*p.wM,(0.5-(b.y+b.h/2)/p.ph)*p.hM,0);p.mesh.localToWorld(v);return [v.x,v.y];})()")
    await aim_and_pinch(*pb)
    check("X6e pinch ray at right-panel AI tab switches tab", await c.js("__tf.S.rtab==='AI'"), await c.js("__tf.S.rtab"))
    # poke test on a panel button: move index fingertip through RECOVER-tab button on right panel
    poke_ok = await c.js("""(async()=>{
      const d=window.__dev,T=__tf.THREE,p=__tf.panels.right,b=p.buttons.find(x=>x.id==='rtab:VERIFY');
      const v=new T.Vector3(((b.x+b.w/2)/p.pw-0.5)*p.wM,(0.5-(b.y+b.h/2)/p.ph)*p.hM,0);p.mesh.localToWorld(v);
      const n=new T.Vector3(0,0,1).transformDirection(p.mesh.matrixWorld);
      const tip=()=>{const t=__tf.xr.hands[1].joints['index-finger-tip'];const w=new T.Vector3();t.getWorldPosition(w);return w;};
      const h=d.hands.right;const sleep=ms=>new Promise(r=>setTimeout(r,ms));
      // place fingertip 8cm in front of the button, then push through
      let t0=tip();let off=t0.clone().sub(h.position);
      const setTip=(pt)=>{h.position.copy(pt.clone().sub(off));};
      setTip(v.clone().add(n.clone().multiplyScalar(0.08)));await sleep(500);
      const t1=tip();off=t1.clone().sub(h.position);
      setTip(v.clone().add(n.clone().multiplyScalar(0.08)));await sleep(400);
      for(let s=8;s>=-3;s--){setTip(v.clone().add(n.clone().multiplyScalar(s*0.01)));await sleep(120);}
      await sleep(1100);
      return {rtab:__tf.S.rtab, tipErr: tip().distanceTo(v.clone().add(n.clone().multiplyScalar(-0.03)))};})()""")
    print("   poke result:", poke_ok)
    check("X7 fingertip poke through VERIFY tab button selects it", poke_ok and poke_ok["rtab"] == "VERIFY", str(poke_ok))
    check("X8 no console/JS errors in XR session", not c.errors, "; ".join(c.errors[:3]))
    fps = await c.js("""new Promise(r=>{let n=0;const t0=performance.now();const f=()=>{n++;if(performance.now()-t0<2000)requestAnimationFrame(f);else r(n/2);};requestAnimationFrame(f);})""")
    print(f"   (informational, software-rendered headless, NOT a Quest measurement) rAF/s outside XR loop = {fps}")


async def main():
    prof = tempfile.mkdtemp(prefix="tf_edge_")
    p = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={PORT}", f"--user-data-dir={prof}", "--use-angle=swiftshader",
                          "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--window-size=1600,900", "--autoplay-policy=no-user-gesture-required", "about:blank"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json")); break
            except Exception: time.sleep(0.3)
        page = next(t for t in tabs if t["type"] == "page")
        async with websockets.connect(page["webSocketDebuggerUrl"], max_size=50_000_000) as ws:
            c = CDP(ws)
            for m in ("Page.enable", "Runtime.enable"): await c.send(m)
            await c.send("Emulation.setDeviceMetricsOverride", width=1600, height=900, deviceScaleFactor=1, mobile=False)
            await desktop_tests(c)
            await xr_tests(c)
    finally:
        p.terminate()
    ok = sum(1 for r in results if r[1]); print(f"\n{ok}/{len(results)} passed")
    json.dump([{"name": n, "pass": o, "detail": d} for n, o, d in results], open(os.path.join(os.path.dirname(__file__), "browser_test_results.json"), "w"), indent=2)
    sys.exit(0 if ok == len(results) else 1)

asyncio.run(main())
