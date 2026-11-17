// Canvas-backed spatial panels with hit-tested buttons (works for ray-pinch, poke, and desktop dev mouse).
import * as THREE from 'three';

export const C = {
  bg: '#0a1222', card: '#101b31', edge: '#1d3a57', text: '#dcecff', dim: '#8aa4c0',
  cyan: '#22d3ee', amber: '#f5a524', red: '#ff3b4e', green: '#2fe38a', violet: '#a78bfa'
};
export const STATUS_COLOR = { VERIFIED: C.green, INVALID: C.red, MISSING: C.amber, UNKNOWN: C.violet };

export function rr(ctx, x, y, w, h, r) {
  ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}

export function wrap(ctx, text, x, y, maxW, lh) {
  const words = String(text).split(' '); let line = '';
  for (const w of words) {
    const t = line ? line + ' ' + w : w;
    if (ctx.measureText(t).width > maxW && line) { ctx.fillText(line, x, y); y += lh; line = w; } else line = t;
  }
  if (line) { ctx.fillText(line, x, y); y += lh; }
  return y;
}

export function badge(ctx, x, y, label, color, size = 24) {
  ctx.font = `700 ${size}px system-ui, sans-serif`;
  const w = ctx.measureText(label).width + 24, h = size + 14;
  ctx.fillStyle = color + '33'; rr(ctx, x, y, w, h, 8); ctx.fill();
  ctx.strokeStyle = color; ctx.lineWidth = 2; rr(ctx, x, y, w, h, 8); ctx.stroke();
  ctx.fillStyle = color; ctx.textBaseline = 'middle'; ctx.fillText(label, x + 12, y + h / 2 + 1); ctx.textBaseline = 'alphabetic';
  return w;
}

export class Panel {
  // wM,hM: world size in metres. pw,ph: canvas pixels. drawFn(ctx, panel) paints and registers buttons.
  constructor(name, wM, hM, pw, ph, drawFn) {
    this.name = name; this.wM = wM; this.hM = hM; this.pw = pw; this.ph = ph; this.drawFn = drawFn;
    this.canvas = document.createElement('canvas'); this.canvas.width = pw; this.canvas.height = ph;
    this.ctx = this.canvas.getContext('2d');
    this.tex = new THREE.CanvasTexture(this.canvas); this.tex.colorSpace = THREE.SRGBColorSpace; this.tex.anisotropy = 4;
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(wM, hM),
      new THREE.MeshBasicMaterial({ map: this.tex, transparent: true, toneMapped: false }));
    this.mesh.userData.panel = this;
    this.buttons = []; this.hover = null; this.visible = true;
  }
  btn(id, x, y, w, h, label, opts = {}) {
    const hot = this.hover === id && !opts.disabled;
    this.buttons.push({ id, x, y, w, h, disabled: !!opts.disabled });
    const ctx = this.ctx, col = opts.color || C.cyan;
    ctx.fillStyle = opts.disabled ? '#0d1626' : (hot ? col + '55' : (opts.active ? col + '30' : '#0f1d33'));
    rr(ctx, x, y, w, h, 12); ctx.fill();
    ctx.strokeStyle = opts.disabled ? '#1a2a40' : col; ctx.lineWidth = hot ? 4 : (opts.active ? 3 : 2); rr(ctx, x, y, w, h, 12); ctx.stroke();
    if (label) {
      ctx.fillStyle = opts.disabled ? '#4d6178' : (opts.textColor || C.text);
      ctx.font = `${opts.active ? 700 : 600} ${opts.size || 26}px system-ui, sans-serif`;
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(label, x + w / 2, y + h / 2 + 1);
      ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
    }
  }
  redraw() {
    const ctx = this.ctx; this.buttons = [];
    ctx.clearRect(0, 0, this.pw, this.ph);
    ctx.fillStyle = C.bg + 'f2'; rr(ctx, 4, 4, this.pw - 8, this.ph - 8, 28); ctx.fill();
    ctx.strokeStyle = C.edge; ctx.lineWidth = 4; rr(ctx, 4, 4, this.pw - 8, this.ph - 8, 28); ctx.stroke();
    ctx.fillStyle = C.text; ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
    this.drawFn(ctx, this);
    this.tex.needsUpdate = true;
  }
  // uv in [0,1], origin bottom-left (three.js)
  buttonAt(uv) {
    const x = uv.x * this.pw, y = (1 - uv.y) * this.ph;
    for (const b of this.buttons) if (x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h) return b;
    return null;
  }
  setHover(id) { if (this.hover !== id) { this.hover = id; this.redraw(); } }
}

function fit(x, text, px) { do { x.font = `700 ${px}px system-ui, sans-serif`; px -= 2; } while (x.measureText(text).width > 470 && px > 14); }
// Floating text label sprite
export function labelSprite(text, color = '#dcecff', w = 0.3, fontPx = 44) {
  const c = document.createElement('canvas'); c.width = 512; c.height = 96;
  const x = c.getContext('2d'); x.textAlign = 'center'; x.textBaseline = 'middle';
  x.fillStyle = 'rgba(6,11,22,0.72)'; rr(x, 6, 10, 500, 76, 20); x.fill();
  fit(x, text, fontPx); x.fillStyle = color; x.fillText(text, 256, 50);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, transparent: true, depthWrite: false, toneMapped: false }));
  s.scale.set(w, w * 96 / 512, 1); s.userData.canvas = c; s.userData.tex = t; return s;
}
export function setSpriteText(s, text, color) {
  const c = s.userData.canvas, x = c.getContext('2d');
  x.clearRect(0, 0, 512, 96); x.textAlign = 'center'; x.textBaseline = 'middle';
  x.fillStyle = 'rgba(6,11,22,0.72)'; rr(x, 6, 10, 500, 76, 20); x.fill(); fit(x, text, 44); x.fillStyle = color; x.fillText(text, 256, 50);
  s.userData.tex.needsUpdate = true;
}

export function glowTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 128; const x = c.getContext('2d');
  const g = x.createRadialGradient(64, 64, 0, 64, 64, 64); g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(0.35, 'rgba(255,255,255,0.35)'); g.addColorStop(1, 'rgba(255,255,255,0)');
  x.fillStyle = g; x.fillRect(0, 0, 128, 128); return new THREE.CanvasTexture(c);
}
export function windowTexture() {
  const c = document.createElement('canvas'); c.width = 64; c.height = 128; const x = c.getContext('2d');
  x.fillStyle = '#000'; x.fillRect(0, 0, 64, 128);
  for (let r = 0; r < 14; r++) for (let q = 0; q < 5; q++) { if ((r * 7 + q * 3) % 5 === 0) continue; x.fillStyle = '#fff'; x.fillRect(5 + q * 11, 5 + r * 8.6, 6, 4.5); }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
