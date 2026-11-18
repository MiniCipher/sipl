"""Interactive chain viewer: Source → Parse tree → AST → Semantic term → State transitions (SEM-03).

Generates one self-contained HTML file (no external resources). All data comes
from the real parse tree / AST / term / trace produced by the library; the
page only displays and links them. Selecting an element on any level
highlights the corresponding elements on all other levels.
"""

from __future__ import annotations

import json
from html import escape
from typing import Any

from .. import __version__
from ..parser import ParseResult
from ..semantics.builder import BuildStep
from ..semantics.evaluator import RULE_DESCRIPTIONS, EvalResult
from ..semantics.render import Piece, render
from ..semantics.state import State
from ..semantics.terms import Term
from .derivation import derivation_tree
from .model import VNode, from_ast, from_parse_tree


def _vnode_js(node: VNode) -> dict[str, Any]:
    data: dict[str, Any] = {"id": node.id, "label": node.label, "kind": node.kind}
    if node.span is not None:
        data["s"] = node.span.start.offset
        data["e"] = node.span.end.offset
        data["pos"] = str(node.span)
    if node.ast_id is not None:
        data["ast"] = node.ast_id
    if node.children:
        data["c"] = [_vnode_js(c) for c in node.children]
    return data


def _piece_js(piece: Piece) -> dict[str, Any]:
    return {"t": piece.term_id,
            "p": [p if isinstance(p, str) else _piece_js(p) for p in piece.parts]}


def build_payload(parsed: ParseResult, term: Term, steps: list[BuildStep],
                  result: EvalResult | None, initial: State | None,
                  filename: str = "<input>") -> dict[str, Any]:
    ast_terms: dict[int, int] = {s.ast_id: s.term.id for s in steps}
    ast_terms[parsed.ast.id] = term.id
    return {
        "version": __version__,
        "filename": filename,
        "source": parsed.source,
        "cst": _vnode_js(from_parse_tree(parsed.tree)),
        "deriv": _vnode_js(derivation_tree(parsed)),
        "warnings": [w.to_dict() for w in parsed.warnings],
        "ast": _vnode_js(from_ast(parsed.ast)),
        "term": _piece_js(render(term, "unicode")),
        "termAscii": render(term, "ascii").text(),
        "terms": {str(t.id): {"ast": t.ast_id, "kind": t.kind, "sort": t.sort}
                  for t in term.walk()},
        "astTerm": {str(k): v for k, v in ast_terms.items()},
        "steps": [s.to_dict() for s in steps],
        "initial": initial,
        "eval": result.to_dict() if result is not None else None,
        "rules": RULE_DESCRIPTIONS,
    }


def render_html(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    title = f"SIPL: {payload['filename']}"
    return (_TEMPLATE.replace("__TITLE__", escape(title))
            .replace("__DATA__", data))


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#f6f7f9;--panel:#fff;--ink:#16202c;--muted:#5b6675;--line:#dde2e8;--accent:#2457d6;
--sel:#ffd84d;--rel:#fff3b8;--ok:#14804a;--bad:#c62828;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
*{box-sizing:border-box}
body{margin:0;font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--ink)}
header{display:flex;flex-wrap:wrap;gap:12px;align-items:baseline;padding:12px 18px;background:#121a26;color:#e9eef5}
header h1{font-size:17px;margin:0;font-weight:600}
header .file{font-family:var(--mono);color:#a8b6c8}
header .hint{margin-left:auto;color:#a8b6c8;font-size:12px}
.badge{padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600}
.badge.ok{background:#d6f5e3;color:var(--ok)}.badge.bad{background:#fde0e0;color:var(--bad)}.badge.none{background:#e6e9ee;color:#445}
.sw{margin-left:auto;display:inline-flex;gap:2px;text-transform:none}
.sw button{border:1px solid var(--line);background:#fff;border-radius:5px;font-size:11px;padding:1px 7px;cursor:pointer;color:var(--muted)}
.sw button.on{background:var(--accent);color:#fff;border-color:var(--accent)}
.warn{color:#8a5a00;font-size:12px;margin-top:6px}
.flow{display:flex;gap:6px;align-items:center;padding:8px 18px;color:var(--muted);font-size:12px;flex-wrap:wrap}
.flow b{color:var(--ink)}
main{display:grid;grid-template-columns:minmax(260px,1fr) minmax(260px,1fr) minmax(260px,1fr);grid-auto-rows:minmax(0,auto);gap:12px;padding:0 18px 18px}
section{background:var(--panel);border:1px solid var(--line);border-radius:10px;display:flex;flex-direction:column;min-height:0}
section h2{font-size:13px;letter-spacing:.02em;text-transform:uppercase;color:var(--muted);margin:0;padding:9px 12px;border-bottom:1px solid var(--line);display:flex;gap:8px;align-items:center}
section h2 .n{background:var(--accent);color:#fff;border-radius:50%;width:19px;height:19px;display:inline-flex;align-items:center;justify-content:center;font-size:11px}
.body{padding:10px 12px;overflow:auto;max-height:440px}
#p-term,#p-exec{grid-column:span 3}
#p-term .body{max-height:none}
pre.src{margin:0;white-space:pre-wrap;font-family:var(--mono);font-size:13px;line-height:1.6;counter-reset:ln}
.src .ln{display:block}
.src .ln::before{counter-increment:ln;content:counter(ln);display:inline-block;width:2.4em;margin-right:10px;text-align:right;color:#a3acb8}
.src span[data-o]{cursor:pointer;border-radius:2px}
.src span.hl{background:var(--sel)}
.src span.hl2{background:var(--rel)}
ul.tree,ul.tree ul{list-style:none;margin:0;padding-left:16px}
ul.tree{padding-left:0}
.row{display:inline-flex;gap:6px;align-items:baseline;padding:1px 6px;border-radius:5px;cursor:pointer;white-space:nowrap}
.row:hover{background:#eef2fb}
.row .pos{font-size:11px;color:#8a95a3;font-family:var(--mono)}
.row .lbl{font-family:var(--mono);font-size:12.5px}
.row.k-token .lbl{color:#7a4b00}
.row.k-rule .lbl{color:#1d3f99}
.row.k-stmt .lbl{color:#0d6b3a}.row.k-aexpr .lbl{color:#8a5a00}.row.k-bexpr .lbl{color:#9b1f6a}
.tog{display:inline-block;width:12px;color:#8a95a3;cursor:pointer;user-select:none}
li.closed>ul{display:none}
.row.sel,.tp.sel{background:var(--sel)!important}
.row.rel,.tp.rel{background:var(--rel)}
.formula{font-family:var(--mono);font-size:15px;line-height:2;word-break:break-word}
.tp{border-radius:3px;cursor:pointer}
.ovl{text-decoration:overline}
.tp:hover{outline:1px dashed #9aa7b8}
.ascii{font-family:var(--mono);font-size:12px;color:var(--muted);margin-top:6px;word-break:break-all}
details{margin-top:8px}
summary{cursor:pointer;color:var(--accent)}
table{border-collapse:collapse;width:100%}
td,th{border-bottom:1px solid var(--line);padding:3px 6px;text-align:left;font-size:13px;vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:12px}
.mono{font-family:var(--mono)}
.steps td:first-child{white-space:nowrap}
.exec{display:grid;grid-template-columns:minmax(300px,1.1fr) minmax(260px,.9fr);gap:14px}
.controls{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
.controls button{border:1px solid var(--line);background:#fff;border-radius:6px;padding:3px 10px;cursor:pointer;font-size:13px}
.controls button:hover{background:#eef2fb}
.controls input[type=range]{flex:1;min-width:140px}
.cur{background:#f3f6fd;border:1px solid #d8e1f7;border-radius:8px;padding:8px 10px;margin-bottom:10px}
.cur .rule{font-weight:700;color:var(--accent);font-family:var(--mono)}
.cur .rd{color:var(--muted);font-size:12px}
.cur .ex{font-family:var(--mono);font-size:13px;margin-top:4px;word-break:break-word}
.trace{font-family:var(--mono);font-size:12px;max-height:330px;overflow:auto;border:1px solid var(--line);border-radius:8px}
.te{padding:1px 8px;cursor:pointer;white-space:nowrap}
.te:hover{background:#eef2fb}
.te.cur-step{background:var(--sel)}
.te.rel{background:var(--rel)}
.te.undef{color:var(--bad)}
.te .r{display:inline-block;min-width:64px;color:var(--accent);font-weight:600}
.te.lv-expr .r{color:#8a5a00}
.chg{background:#d6f5e3;font-weight:700}
.trans .t{cursor:pointer;padding:2px 6px;border-radius:5px;font-family:var(--mono);font-size:12.5px}
.trans .t:hover{background:#eef2fb}.trans .t.sel{background:var(--sel)}
.reason{color:var(--bad);font-weight:600;margin:6px 0}
.muted{color:var(--muted)}
@media (max-width:1000px){main{grid-template-columns:1fr}#p-term,#p-exec{grid-column:span 1}.exec{grid-template-columns:1fr}}
</style>
</head>
<body>
<header><h1>SIPL · Source → Parse Tree → AST → Semantic Term → State</h1>
<span class="file" id="fname"></span><span id="status"></span>
<span class="hint">Клікніть будь-який елемент - відповідні елементи на інших рівнях підсвітяться</span></header>
<div class="flow"><b>1</b> вихідний код → <b>2</b> дерево синтаксичного виводу (БНФ курсу) → <b>3</b> типізоване AST →
<b>4</b> семантичний терм → <b>5</b> переходи станів</div>
<main>
<section id="p-src"><h2><span class="n">1</span>Вихідний код</h2><div class="body"><pre class="src" id="src"></pre></div></section>
<section id="p-cst"><h2><span class="n">2</span>Дерево синтаксичного виводу
<span class="sw"><button id="sw-course" class="on" title="метазмінні та правила БНФ курсу (ПР 1)">БНФ курсу</button><button id="sw-ebnf" title="правила grammar/sipl-ext.ebnf">EBNF</button></span></h2>
<div class="body"><ul class="tree" id="deriv"></ul><ul class="tree" id="cst" style="display:none"></ul></div></section>
<section id="p-ast"><h2><span class="n">3</span>AST</h2><div class="body"><ul class="tree" id="ast"></ul></div></section>
<section id="p-term"><h2><span class="n">4</span>Семантичний терм</h2><div class="body">
<div class="formula" id="term"></div><div class="ascii" id="term-ascii"></div>
<details><summary>Побудова терму: sem_P, sem_S, sem_A, sem_B за правилами табл. 1.6</summary><table class="steps" id="steps"></table></details>
</div></section>
<section id="p-exec"><h2><span class="n">5</span>Обчислення терму на стані та переходи станів</h2><div class="body" id="exec"></div></section>
</main>
<script>
const D = __DATA__;
const $ = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));
function ovlFrag(text){ const f = document.createDocumentFragment(); const re = /((?:[^\u0305]\u0305)+)/g; let last = 0, m;
  while ((m = re.exec(text))) { if (m.index > last) f.appendChild(document.createTextNode(text.slice(last, m.index)));
    const s = document.createElement('span'); s.className = 'ovl'; s.textContent = m[1].replace(/\u0305/g, ''); f.appendChild(s); last = re.lastIndex; }
  if (last < text.length) f.appendChild(document.createTextNode(text.slice(last))); return f; }
const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt !== undefined) e.textContent = txt; return e; };

$('#fname').textContent = D.filename;
const st = $('#status');
if (!D.eval) { st.className = 'badge none'; st.textContent = 'стан не задано'; }
else if (D.eval.status === 'defined') { st.className = 'badge ok'; st.textContent = 'результат визначений'; }
else { st.className = 'badge bad'; st.textContent = 'результат невизначений (⊥)'; }

/* ---------- indexes ---------- */
const astNodes = [], cstNodes = [];
(function idx(n, list){ list.push(n); (n.c||[]).forEach(c => idx(c, list)); })(D.ast, astNodes);
(function idx(n, list){ list.push(n); (n.c||[]).forEach(c => idx(c, list)); })(D.cst, cstNodes);
(function idx(n, list){ list.push(n); (n.c||[]).forEach(c => idx(c, list)); })(D.deriv, cstNodes);
const astById = {}; astNodes.forEach(n => astById[n.ast] = n);
function innermost(list, s, e) {
  let best = null;
  for (const n of list) if (n.s !== undefined && n.s <= s && e <= n.e && (n.e > n.s || s === e))
    if (!best || (n.e - n.s) <= (best.e - best.s)) best = n;
  return best;
}
function astFor(s, e) { const n = innermost(astNodes, s, e); return n ? n.ast : null; }
function termsOfAst(a) { return Object.keys(D.terms).filter(t => D.terms[t].ast === a).map(Number); }

/* ---------- 1. source ---------- */
(function renderSource(){
  const pre = $('#src'); let line = el('span', 'ln'); pre.appendChild(line);
  [...D.source].forEach((ch, i) => {
    if (ch === '\n') { line.appendChild(document.createTextNode('\n')); line = el('span', 'ln'); pre.appendChild(line); return; }
    const s = el('span', null, ch); s.dataset.o = i; line.appendChild(s);
  });
  pre.addEventListener('click', ev => { const o = ev.target.dataset && ev.target.dataset.o;
    if (o !== undefined) { const a = astFor(+o, +o + 1); if (a !== null) select({ast: a}); } });
})();

/* ---------- 2,3. trees ---------- */
function renderTree(root, ul, kindName) {
  (function add(n, parent, depth){
    const li = el('li'); const row = el('span', 'row k-' + n.kind);
    row.dataset.tree = kindName; row.dataset.id = n.id;
    const tog = el('span', 'tog', n.c ? '▾' : ''); li.appendChild(tog);
    row.appendChild(el('span', 'lbl', n.label)); if (n.pos) row.appendChild(el('span', 'pos', n.pos));
    li.appendChild(row); n.row = row; parent.appendChild(li);
    if (n.c) { const sub = el('ul'); li.appendChild(sub); n.c.forEach(c => add(c, sub, depth + 1));
      tog.onclick = () => { li.classList.toggle('closed'); tog.textContent = li.classList.contains('closed') ? '▸' : '▾'; }; }
    row.onclick = () => kindName === 'ast' ? select({ast: n.ast}) : select({cst: n});
  })(root, ul, 0);
}
renderTree(D.cst, $('#cst'), 'cst');
renderTree(D.deriv, $('#deriv'), 'cst');
$('#sw-course').onclick = () => { $('#deriv').style.display = ''; $('#cst').style.display = 'none'; $('#sw-course').classList.add('on'); $('#sw-ebnf').classList.remove('on'); };
$('#sw-ebnf').onclick = () => { $('#deriv').style.display = 'none'; $('#cst').style.display = ''; $('#sw-ebnf').classList.add('on'); $('#sw-course').classList.remove('on'); };
if (D.warnings.length) { const w = el('div', 'warn', '⚠ використано розширення поза БНФ курсу: ' + D.warnings.map(x => x.line + ':' + x.column + ' ' + x.message.split(' (')[0]).join('; ')); $('#src').parentElement.appendChild(w); }
renderTree(D.ast, $('#ast'), 'ast');

/* ---------- 4. term ---------- */
(function renderTerm(){
  const box = $('#term');
  (function add(p, parent){
    const span = el('span', 'tp'); span.dataset.term = p.t;
    p.p.forEach(x => typeof x === 'string' ? span.appendChild(ovlFrag(x)) : add(x, span));
    parent.appendChild(span);
  })(D.term, box);
  box.addEventListener('click', ev => { const t = ev.target.closest('[data-term]');
    if (t) { ev.stopPropagation(); select({term: +t.dataset.term}); } });
  $('#term-ascii').textContent = 'ASCII: ' + D.termAscii;
  const tb = $('#steps');
  tb.innerHTML = '<tr><th>правило</th><th>застосування правила</th><th>отриманий терм</th></tr>';
  D.steps.forEach(s => { const tr = el('tr'); tr.style.cursor = 'pointer';
    tr.appendChild(el('td', 'mono', s.rule + (s.extension ? ' *' : '')));
    const ap = el('td', 'mono'); ap.appendChild(ovlFrag(s.lhs + ' = ' + s.rhs)); tr.appendChild(ap);
    const tt = el('td', 'mono'); tt.appendChild(ovlFrag(s.term)); tr.appendChild(tt); tr.title = s.rule_text; tr.onclick = () => select({ast: s.ast_id});
    tb.appendChild(tr); });
})();

/* ---------- 5. execution ---------- */
let cur = 0, showExpr = false;
const E = D.eval;
function stName(i){ return i === null || i === undefined ? '—' : 'st' + i; }
function fmtState(s){ return s ? '[' + Object.entries(s).map(([k, v]) => k + ' ↦ ' + v).join(', ') + ']' : '⊥'; }
function visible(){ return E.trace.filter(e => showExpr || e.level === 'program'); }
(function renderExec(){
  const box = $('#exec');
  if (!E) { box.innerHTML = '<p class="muted">Початковий стан не задано. Запустіть <code>sipl visualize FILE --state "X=2, Y=3"</code>, щоб побачити обчислення.</p>'; return; }
  box.innerHTML = `
  <div class="exec"><div>
    <div class="controls"><button id="b0">⏮</button><button id="bp">◀ крок</button><button id="bn">крок ▶</button><button id="b1">⏭</button>
    <input type="range" id="rng" min="0" value="0"><span id="cnt" class="mono"></span>
    <label class="muted"><input type="checkbox" id="cx"> правила виразів</label></div>
    <div class="cur" id="cur"></div>
    <div class="trace" id="trace"></div></div>
  <div><div><b>Початковий стан:</b> <span class="mono">st0 = ${fmtState(E.initial_state)}</span></div>
    <div><b>Результат:</b> <span class="mono">${E.status === 'defined' ? fmtState(E.final_state) : '⊥ (невизначено)'}</span>
    <span class="muted">(${E.steps} застосувань правил)</span></div>
    ${E.undefined ? '<div class="reason">⊥: ' + E.undefined.reason + '</div>' : ''}
    <h3 style="font-size:13px;margin:10px 0 4px">Стан на поточному кроці</h3><table id="stt"></table>
    <h3 style="font-size:13px;margin:12px 0 4px">Ланцюжок переходів станів</h3><div class="trans" id="trans"></div></div></div>`;
  const tr = $('#trans');
  tr.appendChild(Object.assign(el('div', 't', 'st0 = ' + fmtState(E.states[0])), {}));
  E.transitions.forEach(t => { const d = el('div', 't', `→ st${t.after} = st${t.before} ∇ [${t.var} ↦ ${t.value}]`);
    d.dataset.trace = t.trace_index; d.onclick = () => gotoTrace(t.trace_index); tr.appendChild(d); });
  $('#b0').onclick = () => setCur(0); $('#b1').onclick = () => setCur(visible().length - 1);
  $('#bp').onclick = () => setCur(cur - 1); $('#bn').onclick = () => setCur(cur + 1);
  $('#rng').oninput = ev => setCur(+ev.target.value);
  $('#cx').onchange = ev => { const idx = visible()[cur] ? visible()[cur].index : 0; showExpr = ev.target.checked; drawTrace(); gotoTrace(idx); };
  drawTrace(); setCur(0);
})();
function drawTrace(){
  const box = $('#trace'); box.innerHTML = '';
  const vis = visible();
  $('#rng').max = Math.max(0, vis.length - 1);
  vis.forEach((e, i) => { const d = el('div', 'te lv-' + e.level + (e.undefined ? ' undef' : ''));
    d.style.paddingLeft = (8 + e.depth * 14) + 'px'; d.dataset.i = i; d.dataset.term = e.term_id;
    d.appendChild(el('span', 'r', e.rule)); d.appendChild(ovlFrag(' ' + e.explanation));
    d.onclick = () => setCur(i); box.appendChild(d); });
}
function gotoTrace(index){ const vis = visible(); let i = vis.findIndex(e => e.index >= index); if (i < 0) i = vis.length - 1; setCur(i); }
function setCur(i){
  const vis = visible(); if (!vis.length) return;
  cur = Math.max(0, Math.min(vis.length - 1, i)); const e = vis[cur];
  $('#rng').value = cur; $('#cnt').textContent = (cur + 1) + '/' + vis.length;
  $$('.te.cur-step').forEach(x => x.classList.remove('cur-step'));
  const row = $(`.te[data-i="${cur}"]`); if (row) { row.classList.add('cur-step'); row.scrollIntoView({block: 'nearest'}); }
  $('#cur').innerHTML = '';
  const c = $('#cur'); const h = el('div'); h.appendChild(el('span', 'rule', e.rule + (e.note ? ' (' + e.note + ')' : '') + ': '));
  const rd = el('span', 'rd'); rd.appendChild(ovlFrag(D.rules[e.rule] || '')); h.appendChild(rd); c.appendChild(h);
  const ex = el('div', 'ex'); ex.appendChild(ovlFrag(e.explanation)); c.appendChild(ex);
  drawState(e);
  $$('.trans .t').forEach(t => t.classList.toggle('sel', t.dataset.trace !== undefined && +t.dataset.trace === e.index));
  select({term: e.term_id}, true);
}
function drawState(e){
  const before = E.states[e.state_in] || {}, after = e.state_out !== null ? E.states[e.state_out] : null;
  const vars = [...new Set([...Object.keys(E.states[0] || {}), ...E.states.flatMap(s => Object.keys(s))])];
  const t = $('#stt'); t.innerHTML = `<tr><th>змінна</th><th>${stName(e.state_in)} (вхід)</th><th>${after ? stName(e.state_out) + ' (вихід)' : 'вихід'}</th></tr>`;
  vars.forEach(v => { const tr = el('tr'); tr.appendChild(el('td', 'mono', v));
    const b = v in before ? before[v] : '—'; const a = after ? (v in after ? after[v] : '—') : (e.undefined ? '⊥' : '…');
    tr.appendChild(el('td', 'mono', String(b))); const ta = el('td', 'mono', String(a)); if (after && a !== b) ta.className += ' chg';
    tr.appendChild(ta); t.appendChild(tr); });
}

/* ---------- synchronised selection ---------- */
function select(q, fromStepper){
  let ast = q.ast ?? null, term = q.term ?? null, s = null, e = null;
  if (q.cst) { s = q.cst.s; e = q.cst.e; ast = astFor(s, e); }
  if (term !== null && ast === null) ast = D.terms[term] ? D.terms[term].ast : null;
  if (ast !== null && term === null) term = D.astTerm[ast] ?? null;
  if (ast !== null && s === null) { const n = astById[ast]; if (n) { s = n.s; e = n.e; } }
  // clear
  $$('.sel, .rel, .hl, .hl2').forEach(x => x.classList.remove('sel', 'rel', 'hl', 'hl2'));
  if (s === null) return;
  // 1. source
  $$('#src span[data-o]').forEach(x => { const o = +x.dataset.o; if (o >= s && o < e) x.classList.add('hl'); });
  // 2. parse tree: nodes with exactly this span are primary; their ancestors-up chain stays visible
  let exact = cstNodes.filter(n => n.s === s && n.e === e);
  if (!exact.length) { const n = innermost(cstNodes, s, e); if (n) exact = [n]; }
  exact.forEach(n => { n.row.classList.add('sel'); reveal(n.row); });
  if (q.cst && !exact.includes(q.cst)) { q.cst.row.classList.add('sel'); }
  // 3. AST
  if (ast !== null && astById[ast]) { astById[ast].row.classList.add('sel'); reveal(astById[ast].row); }
  // 4. term
  if (term !== null) { const tp = $(`#term [data-term="${term}"]`); if (tp) tp.classList.add('sel'); }
  termsOfAst(ast).forEach(t => { const tp = $(`#term [data-term="${t}"]`); if (tp && +t !== term) tp.classList.add('rel'); });
  // 5. trace entries of this term
  if (E && term !== null) $$('.te').forEach(x => { if (+x.dataset.term === term && !x.classList.contains('cur-step')) x.classList.add('rel'); });
  if (!fromStepper) scrollIntoViewIfNeeded();
}
function reveal(row){ let li = row.closest('li'); while (li) { li.classList.remove('closed'); const t = li.querySelector(':scope > .tog'); if (t && t.textContent) t.textContent = '▾'; li = li.parentElement.closest('li'); }
  const body = row.closest('.body'); if (body) { const r = row.getBoundingClientRect(), b = body.getBoundingClientRect(); if (r.top < b.top || r.bottom > b.bottom) body.scrollTop += r.top - b.top - 40; } }
function scrollIntoViewIfNeeded(){}
</script>
</body>
</html>
"""
