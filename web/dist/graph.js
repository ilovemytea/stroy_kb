// Визуализация семантической сети: простая силовая раскладка (отталкивание + пружины).
export function mountGraph(data, FOCUS = 0) {
  const CONCEPT_URL = "#/concept/";
  const controller = new AbortController();
  const signal = controller.signal;
  const svg = document.getElementById("graph");
  const NS = "http://www.w3.org/2000/svg";
  const COLORS = {
    "Материалы": "#b5462a", "Сырьё и компоненты": "#8a6d3b", "Свойства": "#2e7d9a",
    "Области применения": "#2e7d4f", "Нормативы": "#6d4fa3", "Технологии": "#c08a00"
  };
  const legend = document.getElementById("legend");
  Object.entries(COLORS).forEach(([k, c]) => {
    legend.insertAdjacentHTML("beforeend", `<span><i style="background:${c}"></i>${k}</span>`);
  });

  let nodes, links, byId, view = { x: 0, y: 0, k: 1 };
  const g = document.createElementNS(NS, "g");
  svg.appendChild(g);


  document.getElementById("relfilter").addEventListener("change", e => build(e.target.value), { signal });

  function build(rel) {
    g.innerHTML = "";
    const W = svg.clientWidth, H = svg.clientHeight;
    const ls = data.links.filter(l => !rel || l.type === rel);
    const used = new Set();
    ls.forEach(l => { used.add(l.source); used.add(l.target); });
    nodes = data.nodes.filter(n => !rel || used.has(n.id)).map((n, i) => ({
      ...n, x: W / 2 + Math.cos(i) * (100 + i * 3), y: H / 2 + Math.sin(i) * (100 + i * 3), vx: 0, vy: 0
    }));
    byId = new Map(nodes.map(n => [n.id, n]));
    links = ls.map(l => ({ ...l, s: byId.get(l.source), t: byId.get(l.target) })).filter(l => l.s && l.t);
    nodes.forEach(n => n.deg = 0);
    links.forEach(l => { l.s.deg++; l.t.deg++; });
    layout(W, H);
    fit(W, H);
    draw();
    if (FOCUS && byId.get(FOCUS)) highlight(byId.get(FOCUS), true);
  }

  // Алгоритм Фрюхтермана–Рейнгольда: отталкивание k²/d, притяжение d²/k,
  // смещение ограничено «температурой», которая убывает с каждой итерацией.
  function layout(W, H) {
    const k = Math.sqrt((W * H) / Math.max(1, nodes.length)) * 0.6;
    const ITER = 300;
    for (let it = 0; it < ITER; it++) {
      const temp = (W / 8) * (1 - it / ITER) + 1;
      nodes.forEach(n => { n.vx = 0; n.vy = 0; });
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j];
          const dx = a.x - b.x, dy = a.y - b.y, d = Math.sqrt(dx * dx + dy * dy) || 0.1;
          const f = (k * k) / d;
          a.vx += dx / d * f; a.vy += dy / d * f; b.vx -= dx / d * f; b.vy -= dy / d * f;
        }
      }
      links.forEach(l => {
        const dx = l.t.x - l.s.x, dy = l.t.y - l.s.y, d = Math.sqrt(dx * dx + dy * dy) || 0.1;
        const f = (d * d) / k;
        l.s.vx += dx / d * f; l.s.vy += dy / d * f; l.t.vx -= dx / d * f; l.t.vy -= dy / d * f;
      });
      nodes.forEach(n => {
        const d = Math.sqrt(n.vx * n.vx + n.vy * n.vy) || 1;
        n.x += n.vx / d * Math.min(d, temp);
        n.y += n.vy / d * Math.min(d, temp);
        n.x = Math.max(20, Math.min(W - 20, n.x));
        n.y = Math.max(20, Math.min(H - 20, n.y));
      });
    }
  }

  // Масштаб «по размеру области», чтобы весь граф был виден сразу.
  function fit(W, H) {
    const xs = nodes.map(n => n.x), ys = nodes.map(n => n.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    const pad = 60;
    const k = Math.min((W - 2 * pad) / (maxX - minX || 1), (H - 2 * pad) / (maxY - minY || 1), 1.5);
    view = { k, x: pad - minX * k + ((W - 2 * pad) - (maxX - minX) * k) / 2,
             y: pad - minY * k + ((H - 2 * pad) - (maxY - minY) * k) / 2 };
    applyView();
  }

  function el(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v));
    (parent || g).appendChild(e);
    return e;
  }

  function draw() {
    const style = getComputedStyle(document.body);
    const lineColor = style.getPropertyValue("--line") || "#ccc";
    const textColor = style.getPropertyValue("--text") || "#222";
    links.forEach(l => {
      l.el = el("line", { x1: l.s.x, y1: l.s.y, x2: l.t.x, y2: l.t.y, stroke: lineColor, "stroke-width": 1.2 });
      l.el.appendChild(document.createElementNS(NS, "title")).textContent = `${l.s.name} — ${l.type} — ${l.t.name}`;
    });
    nodes.forEach(n => {
      const r = 4 + Math.min(10, n.deg);
      n.el = el("g", { transform: `translate(${n.x},${n.y})`, style: "cursor:pointer" });
      el("circle", { r, fill: COLORS[n.category] || "#888", stroke: "#fff", "stroke-width": 1.5 }, n.el);
      n.label = el("text", { x: r + 3, y: 4, "font-size": 11, fill: textColor }, n.el);
      n.label.textContent = n.name;
      n.el.addEventListener("mouseenter", () => highlight(n, true));
      n.el.addEventListener("mouseleave", () => highlight(n, false));
      n.el.setAttribute("tabindex", "0");
      n.el.setAttribute("role", "link");
      n.el.setAttribute("aria-label", n.name);
      n.el.addEventListener("click", () => { if (!moved) location.hash = CONCEPT_URL + n.id; });
      n.el.addEventListener("keydown", e => { if (e.key === "Enter") location.hash = CONCEPT_URL + n.id; });
    });
  }

  function highlight(n, on) {
    const near = new Set([n.id]);
    links.forEach(l => {
      const hit = l.s === n || l.t === n;
      if (hit) { near.add(l.s.id); near.add(l.t.id); }
      l.el.setAttribute("stroke-opacity", on && !hit ? 0.12 : 1);
      l.el.setAttribute("stroke", on && hit ? "#b5462a" : getComputedStyle(document.body).getPropertyValue("--line"));
      l.el.setAttribute("stroke-width", on && hit ? 2 : 1.2);
    });
    nodes.forEach(m => {
      m.el.setAttribute("opacity", on && !near.has(m.id) ? 0.2 : 1);
      m.label.setAttribute("font-weight", on && m === n ? 700 : 400);
    });
  }

  // масштаб и сдвиг
  function applyView() { g.setAttribute("transform", `translate(${view.x},${view.y}) scale(${view.k})`); }
  svg.addEventListener("wheel", e => {
    e.preventDefault();
    const k = Math.max(0.3, Math.min(4, view.k * (e.deltaY < 0 ? 1.1 : 0.9)));
    const rect = svg.getBoundingClientRect(), mx = e.clientX - rect.left, my = e.clientY - rect.top;
    view.x = mx - (mx - view.x) * k / view.k; view.y = my - (my - view.y) * k / view.k; view.k = k;
    applyView();
  }, { passive: false, signal });
  let drag = null, moved = false;
  svg.addEventListener("pointerdown", e => {
    moved = false;
    drag = { x: e.clientX - view.x, y: e.clientY - view.y, sx: e.clientX, sy: e.clientY, id: e.pointerId };
  }, { signal });
  window.addEventListener("pointermove", e => {
    if (!drag || drag.id !== e.pointerId) return;
    if (Math.hypot(e.clientX-drag.sx, e.clientY-drag.sy)>6) moved = true;
    if (moved) { view.x=e.clientX-drag.x; view.y=e.clientY-drag.y; applyView(); }
  }, { signal });
  window.addEventListener("pointerup", () => { drag=null; }, { signal });
  window.addEventListener("pointercancel", () => { drag=null; }, { signal });
  function zoom(factor) {
    const k=Math.max(.2, Math.min(5, view.k*factor));
    view.x=svg.clientWidth/2-(svg.clientWidth/2-view.x)*k/view.k;
    view.y=svg.clientHeight/2-(svg.clientHeight/2-view.y)*k/view.k;
    view.k=k; applyView();
  }
  document.getElementById("graph-plus").addEventListener("click",()=>zoom(1.25), { signal });
  document.getElementById("graph-minus").addEventListener("click",()=>zoom(.8), { signal });
  document.getElementById("graph-fit").addEventListener("click",()=>fit(svg.clientWidth,svg.clientHeight), { signal });
  let lastWidth=svg.clientWidth;
  const observer = new ResizeObserver(() => {
    if (svg.clientWidth !== lastWidth) { lastWidth=svg.clientWidth; build(document.getElementById("relfilter").value); }
  });
  observer.observe(svg);
  build("");
  return () => { controller.abort(); observer.disconnect(); };
}
