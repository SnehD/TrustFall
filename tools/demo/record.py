"""Deterministic demo recorder: drives the real Trustfall web app in Edge (CDP), renders frame-by-frame
on a manual clock (smooth 24 fps regardless of GPU speed), overlays captions/titles, saves JPEG frames.
Usage: python tools/demo/record.py [--max-frames N] [--gpu]   (serve web/ on :8765 first)
Footage is a desktop WebGL render of the real app with scripted pointer input - NOT headset footage."""
import asyncio, base64, json, math, os, re, subprocess, sys, tempfile, time, urllib.request, wave
import websockets

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
FPS, W, H = 24, 1920, 1080
OUT = os.path.join(ROOT, "tools", "out", "frames")
TTS = os.path.join(ROOT, "tools", "out", "tts")
NARR = json.load(open(os.path.join(ROOT, "tools", "demo", "narration.json"), encoding="utf-8"))
MAXF = int(sys.argv[sys.argv.index("--max-frames") + 1]) if "--max-frames" in sys.argv else None
GPU = "--gpu" in sys.argv

# ---- timing from real TTS durations
GAP = 0.35
LS, LE, CAPTION = {}, {}, {}
SEG_START_OVERRIDE = {4: 72.8}
for s in NARR:
    t = SEG_START_OVERRIDE.get(s["seg"], s["start"])
    for i, line in enumerate(s["lines"]):
        w = wave.open(os.path.join(TTS, f"s{s['seg']}_{i}.wav")); d = w.getnframes() / w.getframerate()
        LS[(s["seg"], i)], LE[(s["seg"], i)] = t, t + d; t += d + GAP
        c = line
        for a, b in [("OpsBot seven", "OpsBot-7"), ("nine fourteen", "09:14"), ("Twenty six", "26"), ("A P I", "API"), ("A I ", "AI "), ("I D", "ID"), ("J S O N", "JSON")]:
            c = c.replace(a, b)
        CAPTION[(s["seg"], i)] = c
SEG0 = {s["seg"]: LS[(s["seg"], 0)] for s in NARR}
END_T = LE[(7, 1)] + 3.2
TOTAL = END_T

CHAPTERS = {1: "01  THE FAILURE", 2: "02  THE PROBLEM", 3: "03  THE INVESTIGATION", 4: "04  THE DISCOVERY", 5: "05  AI INVESTIGATION", 6: "06  RECOVERY", 7: "07  THE RESULT"}

# ---- camera presets (pos, look)
P = {
    "WIDE": ((0, 1.55, 1.55), (0, 1.35, -1)), "HERO": ((0, 1.3, 0.5), (0, 1.0, -1)),
    "LEFT": ((-0.54, 1.3, -0.15), (-0.92, 1.3, -0.85)), "RIGHT": ((0.54, 1.3, -0.15), (0.92, 1.3, -0.85)),
    "GRAPH": ((0, 1.7, 0.15), (0, 1.62, -1)), "WIDE2": ((0, 1.65, 1.15), (0, 1.55, -1)),
}
HOLDS = [("WIDE", 0, 1.5), ("HERO", 12.5, LS[(2, 1)] + 1.9), ("LEFT", LS[(2, 2)] + 0.2, LS[(3, 3)] + 0.2),
         ("GRAPH", LS[(3, 3)] + 2.2, LS[(3, 4)] - 0.2), ("RIGHT", LS[(3, 4)] + 2.0, LS[(6, 1)] + 3.5),
         ("WIDE2", LS[(6, 2)] + 1.2, LS[(7, 0)] - 0.4), ("RIGHT", LS[(7, 0)] + 1.4, LS[(7, 1)] - 0.3), ("WIDE2", LS[(7, 1)] + 1.2, 9999)]

def ease(x): x = max(0, min(1, x)); return x * x * (3 - 2 * x)
def cam_at(t):
    for i, (n, a, b) in enumerate(HOLDS):
        if a <= t <= b: pos, look = P[n]; break
        nxt = HOLDS[i + 1] if i + 1 < len(HOLDS) else None
        if nxt and b < t < nxt[1]:
            k = ease((t - b) / (nxt[1] - b)); p0, l0 = P[n]; p1, l1 = P[nxt[0]]
            pos = tuple(p0[j] + (p1[j] - p0[j]) * k for j in range(3)); look = tuple(l0[j] + (l1[j] - l0[j]) * k for j in range(3)); break
    else: pos, look = P["WIDE2"]
    sway = math.sin(t * 0.35) * 0.012
    return (pos[0] + sway, pos[1] + math.sin(t * 0.27) * 0.006, pos[2]), look

# ---- scripted pointer actions: (time, kind, target)   kind: click|hover
ACT = [
    (LS[(2, 1)] + 1.0, "click", "bld:payments-api"),
    (LS[(2, 2)] + 0.9, "click", "btn:left:ltab:TIMELINE"),
    (LS[(2, 2)] + 5.8, "click", "btn:left:tl:T3"),
    (LS[(3, 0)] + 0.3, "click", "btn:left:ltab:AGENT"),
    (LS[(3, 3)] + 4.0, "click", "node:change"),
    (LS[(4, 0)] + 0.4, "click", "btn:right:rtab:VERIFY"),
    (LS[(4, 1)] + 0.2, "click", "btn:right:verify"),
    (LS[(4, 2)] + 0.2, "click", "btn:right:tamper"),
    (LS[(5, 0)] + 0.4, "click", "btn:right:rtab:AI"),
    (LS[(6, 0)] + 0.4, "click", "btn:right:rtab:RECOVER"),
    (LS[(6, 0)] + 4.0, "hover", "btn:right:rec:isolate_agent"),
    (LS[(6, 1)] + 1.0, "click", "btn:right:rec:restore_previous_config"),
    (LS[(7, 0)] + 1.6, "click", "btn:right:rtab:REPORT"),
    (LS[(7, 0)] + 7.0, "hover", "btn:right:exp-md"),
]
ACT.sort()

SETUP_JS = r"""
(function(){const T=__tf.THREE;
window.__proj=(v)=>{const p=v.clone().project(__tf.camera);return [(p.x+1)/2*innerWidth,(1-p.y)/2*innerHeight];};
window.__target=(s)=>{const a=s.split(':');
 if(a[0]==='bld'){const v=new T.Vector3();__tf.bld[a[1]].body.getWorldPosition(v);v.y+=0.02;return __proj(v);}
 if(a[0]==='node'){const v=new T.Vector3();__tf.gnodes[a[1]].m.getWorldPosition(v);return __proj(v);}
 if(a[0]==='btn'){const p=__tf.panels[a[1]],id=a.slice(2).join(':'),b=p.buttons.find(x=>x.id===id);if(!b)return null;
  const v=new T.Vector3(((b.x+b.w/2)/p.pw-0.5)*p.wM,(0.5-(b.y+b.h/2)/p.ph)*p.hM,0);p.mesh.localToWorld(v);return __proj(v);}
 return null;};
const css=document.createElement('style');css.textContent=`
#ov,#ov *{pointer-events:none !important;box-sizing:border-box;font-family:'Segoe UI',system-ui,sans-serif}
#cap{position:fixed;left:50%;bottom:6.5%;transform:translateX(-50%);max-width:70%;padding:16px 30px;border-radius:16px;border-left:6px solid #22d3ee;
 background:rgba(6,11,22,.80);color:#fff;font-size:38px;font-weight:600;line-height:1.28;text-align:center;opacity:0;z-index:20;text-shadow:0 2px 6px #000}
#ch{position:fixed;left:3.5%;top:5%;padding:10px 24px;border-radius:30px;background:rgba(6,11,22,.8);border:2px solid #22d3ee;color:#22d3ee;font-size:30px;font-weight:700;letter-spacing:3px;opacity:0;z-index:20}
#prog{position:fixed;left:0;top:0;height:6px;background:linear-gradient(90deg,#22d3ee,#2fe38a);z-index:30;width:0}
#disc{position:fixed;right:1.5%;bottom:1.2%;font-size:17px;color:#9fb6cc;background:rgba(6,11,22,.6);padding:4px 12px;border-radius:8px;z-index:20}
#cur{position:fixed;width:34px;height:34px;margin:-17px 0 0 -17px;border-radius:50%;border:4px solid #22d3ee;background:rgba(34,211,238,.25);z-index:25;opacity:0;pointer-events:none;box-shadow:0 0 18px #22d3ee}
#title,#end{position:fixed;inset:0;background:radial-gradient(ellipse at center,#0d1b33 0%,#060b16 70%);z-index:40;display:flex;flex-direction:column;align-items:center;justify-content:center;opacity:0;color:#dcecff}
#title h1,#end h1{margin:18px 0 0;font-size:150px;letter-spacing:14px;font-weight:800;color:#fff}
#title h2,#end h2{margin:10px 0 0;font-size:42px;letter-spacing:8px;font-weight:600;color:#22d3ee}
#title p,#end p{margin:30px 0 0;font-size:34px;color:#9fb6cc}
#end p.big{font-size:52px;color:#fff;font-weight:700;letter-spacing:1px}
`;document.head.appendChild(css);
const logo=`<svg viewBox="0 0 128 128" width="200" height="200"><path d="M64 14 L104 29 V62 C104 85 87 102 64 114 C41 102 24 85 24 62 V29 Z" fill="none" stroke="#22d3ee" stroke-width="6" stroke-linejoin="round"/><path d="M64 34 V70" stroke="#22d3ee" stroke-width="6" stroke-linecap="round"/><path d="M48 62 L64 80 L80 62" fill="none" stroke="#22d3ee" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/><circle cx="64" cy="96" r="5.5" fill="#ff3b4e"/></svg>`;
const d=document.createElement('div');d.id='ov';d.innerHTML=`<div id="prog"></div><div id="ch"></div><div id="cap"></div><div id="cur"></div>
<div id="disc">Real app, scripted desktop run &middot; Data fictional &middot; Recovery simulated &middot; AI: deterministic fallback</div>
<div id="title">${logo}<h1>TRUSTFALL</h1><h2>THE AGENTOPS COMMAND CENTER</h2><p>Investigate AI-agent incidents with your hands &middot; Meta Quest</p></div>
<div id="end">${logo}<h1>TRUSTFALL</h1><h2>THE AGENTOPS COMMAND CENTER</h2><p class="big">Trust the evidence. Not the signature alone.</p><p>Hands-first &middot; Evidence-grounded &middot; Meta Quest</p></div>`;
document.body.appendChild(d);
window.__ov=(o)=>{const $=id=>document.getElementById(id);
 $('prog').style.width=(o.prog*100)+'%';
 const c=$('cap');c.textContent=o.cap||'';c.style.opacity=o.capOp;
 const h=$('ch');h.textContent=o.ch||'';h.style.opacity=o.chOp;h.style.transform='translateX('+((1-o.chOp)*-40)+'px)';
 $('title').style.opacity=o.title;$('title').style.pointerEvents='none';$('end').style.opacity=o.end;
 const u=$('cur');u.style.opacity=o.curOp;u.style.left=o.cx+'px';u.style.top=o.cy+'px';u.style.transform='scale('+o.curScale+')';u.style.background=o.press?'rgba(255,255,255,.7)':'rgba(34,211,238,.25)';};
window.__frame=(t,pos,look)=>{const c=__tf.camera;c.position.set(...pos);c.lookAt(...look);__tf.tick(t*1000);return true;};
return true;})()
"""


class CDP:
    def __init__(self, ws): self.ws, self.i = ws, 0
    async def send(self, method, **params):
        self.i += 1; mid = self.i
        await self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg: raise RuntimeError(msg["error"])
                return msg["result"]
    async def js(self, expr):
        r = await self.send("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in r: raise RuntimeError(r["exceptionDetails"].get("exception", {}).get("description", str(r["exceptionDetails"])))
        return r["result"].get("value")
    async def mouse(self, typ, x, y):
        await self.send("Input.dispatchMouseEvent", type=typ, x=x, y=y, button="left", clickCount=1, buttons=1 if typ == "mousePressed" else 0)


def overlay_state(t, cur):
    o = {"prog": min(1, t / TOTAL), "cap": "", "capOp": 0, "ch": "", "chOp": 0, "title": 0, "end": 0}
    for (seg, i), a in LS.items():
        b = LE[(seg, i)] + 0.25
        if a - 0.1 <= t <= b:
            o["cap"] = CAPTION[(seg, i)]; o["capOp"] = min(1, (t - a + 0.1) / 0.2, (b - t) / 0.2 + 0.0) if t < b else 0
            o["capOp"] = max(0, min(1, o["capOp"]))
    for seg, a in SEG0.items():
        if a - 0.3 <= t <= a + 4.2:
            o["ch"] = CHAPTERS[seg]; o["chOp"] = max(0, min(1, (t - a + 0.3) / 0.5, (a + 4.2 - t) / 0.5))
    o["title"] = 1 if t < 3.6 else max(0, 1 - (t - 3.6) / 1.0)
    et = LS[(7, 1)] + 0.4
    o["end"] = max(0, min(1, (t - et) / 1.0))
    if o["end"] > 0: o["capOp"] = o["capOp"] * (1 - o["end"])
    o.update(cur)
    return o


async def main():
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT): os.remove(os.path.join(OUT, f))
    prof = tempfile.mkdtemp(prefix="tf_rec_")
    flags = ["--use-angle=d3d11"] if GPU else ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
    p = subprocess.Popen([EDGE, "--headless=new", "--remote-debugging-port=9334", f"--user-data-dir={prof}", "--ignore-gpu-blocklist", "--hide-scrollbars",
                          f"--window-size={W},{H}", *flags, "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try: tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9334/json")); break
            except Exception: time.sleep(0.3)
        page = next(t for t in tabs if t["type"] == "page")
        async with websockets.connect(page["webSocketDebuggerUrl"], max_size=100_000_000) as ws:
            c = CDP(ws)
            await c.send("Page.enable"); await c.send("Runtime.enable")
            await c.send("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=False)
            await c.send("Page.navigate", url="http://localhost:8765/index.html?shot=1&onboard=0&clock=manual")
            for _ in range(120):
                await asyncio.sleep(0.3)
                if await c.js("!!(window.__tf && window.__tf.engine)"): break
            await c.js(SETUP_JS)
            n = int(TOTAL * FPS) + 1
            if MAXF: n = min(n, MAXF)
            cx, cy, ai, pressUntil = W / 2, H / 2, 0, -1
            started = time.time(); active = None; click_done = set()
            for f in range(n):
                t = f / FPS
                pos, look = cam_at(t)
                await c.js(f"__frame({t},{list(pos)},{list(look)})")
                # pointer: active action window [ta-1.1, ta+0.7]
                cur = {"curOp": 0, "cx": cx, "cy": cy, "curScale": 1, "press": False}
                for idx, (ta, kind, tgt) in enumerate(ACT):
                    if ta - 1.1 <= t <= ta + 0.8:
                        xy = await c.js(f"__target({json.dumps(tgt)})")
                        if xy:
                            k = ease((t - (ta - 1.1)) / 1.0)
                            if idx != active: active = idx; sx, sy = cx, cy
                            cx = sx + (xy[0] - sx) * k if t < ta else xy[0]; cy = sy + (xy[1] - sy) * k if t < ta else xy[1]
                            await c.mouse("mouseMoved", cx, cy)
                            cur.update(curOp=min(1, (t - (ta - 1.1)) / 0.3, (ta + 0.8 - t) / 0.3), cx=cx, cy=cy)
                            if kind == "click" and t >= ta and idx not in click_done:
                                click_done.add(idx); pressUntil = t + 0.25
                                await c.mouse("mousePressed", cx, cy); await c.mouse("mouseReleased", cx, cy)
                                await c.js(f"__frame({t},{list(pos)},{list(look)})")
                            if t < pressUntil: cur.update(curScale=0.7, press=True)
                        break
                await c.js(f"__ov({json.dumps(overlay_state(t, cur))})")
                shot = await c.send("Page.captureScreenshot", format="jpeg", quality=92)
                open(os.path.join(OUT, f"{f:05d}.jpg"), "wb").write(base64.b64decode(shot["data"]))
                if f % 120 == 0:
                    el = time.time() - started; print(f"frame {f}/{n}  t={t:.1f}s  elapsed {el:.0f}s  eta {el / (f + 1) * (n - f):.0f}s", flush=True)
            print("frames done", n, "total video seconds", TOTAL)
    finally:
        p.terminate()

if __name__ == "__main__": asyncio.run(main())
