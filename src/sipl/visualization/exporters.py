"""Tree exporters: text, JSON, Graphviz DOT and standalone SVG (VIS-01).

Every exported node keeps its link to the source: the text view prints the
span and the code fragment, DOT/SVG put them into the label and the tooltip.
"""

from __future__ import annotations

import json
from html import escape

from .model import VNode

# ---------------------------------------------------------------------- text


def to_text(root: VNode, source: str, show_spans: bool = True, fragment_width: int = 36) -> str:
    rows: list[tuple[str, str, str]] = []

    def visit(node: VNode, prefix: str, child_prefix: str) -> None:
        span = str(node.span) if node.span is not None and show_spans else ""
        frag = ""
        if node.span is not None and node.kind != "token":
            frag = "«" + node.span.snippet(source, fragment_width) + "»"
        rows.append((prefix + node.label, span, frag))
        for i, c in enumerate(node.children):
            last = i == len(node.children) - 1
            visit(c, child_prefix + ("└── " if last else "├── "),
                  child_prefix + ("    " if last else "│   "))

    visit(root, "", "")
    w1 = max(len(r[0]) for r in rows) + 2
    w2 = max(len(r[1]) for r in rows) + 2
    return "\n".join(f"{a:<{w1}}{b:<{w2}}{c}".rstrip() for a, b, c in rows)


def to_json(root: VNode, source: str) -> str:
    return json.dumps(root.to_dict(source), ensure_ascii=False, indent=2)


# ----------------------------------------------------------------------- DOT

_COLORS = {
    "rule": "#dbeafe", "token": "#f1f5f9", "program": "#ede9fe", "stmt": "#dcfce7",
    "aexpr": "#fef3c7", "bexpr": "#fce7f3", "term": "#e0f2fe",
}


def _dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def to_dot(root: VNode, source: str, title: str = "SIPL") -> str:
    lines = [
        f'digraph "{_dot_escape(title)}" {{',
        '  graph [rankdir=TB, fontname="Helvetica", labelloc=t, label="'
        + _dot_escape(title) + '"];',
        '  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11];',
        "  edge [arrowsize=0.6];",
    ]
    for node in root.walk():
        label = node.label
        tooltip = node.label
        if node.span is not None:
            label += f"\\n{node.span}"
            tooltip = f"{node.label} [{node.span}]: {node.span.snippet(source, 80)}"
        lines.append(
            f'  n{node.id} [label="{_dot_escape(label).replace(chr(92) * 2 + "n", chr(92) + "n")}", '
            f'fillcolor="{_COLORS.get(node.kind, "#ffffff")}", tooltip="{_dot_escape(tooltip)}"];')
        for c in node.children:
            lines.append(f"  n{node.id} -> n{c.id};")
    lines.append("}")
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------- SVG

_CHAR_W = 7.2
_H = 38
_LEVEL = 64
_GAP = 10


def _node_width(node: VNode) -> float:
    sub = str(node.span) if node.span is not None else ""
    return max(len(node.label) * _CHAR_W, len(sub) * 6.0) + 18


def to_svg(root: VNode, source: str, title: str = "") -> str:
    """Tidy top-down tree layout rendered as standalone SVG with tooltips."""
    widths: dict[int, float] = {}

    def measure(n: VNode) -> float:
        own = _node_width(n)
        kids = sum(measure(c) for c in n.children) + _GAP * max(0, len(n.children) - 1)
        widths[id(n)] = max(own, kids)
        return widths[id(n)]

    total = measure(root)
    pos: dict[int, tuple[float, float]] = {}
    depth_max = 0

    def place(n: VNode, left: float, depth: int) -> None:
        nonlocal depth_max
        depth_max = max(depth_max, depth)
        w = widths[id(n)]
        if n.children:
            kids_w = sum(widths[id(c)] for c in n.children) + _GAP * (len(n.children) - 1)
            x = left + (w - kids_w) / 2
            for c in n.children:
                place(c, x, depth + 1)
                x += widths[id(c)] + _GAP
            first, last = pos[id(n.children[0])][0], pos[id(n.children[-1])][0]
            cx = (first + last) / 2
        else:
            cx = left + w / 2
        pos[id(n)] = (cx, 40 + depth * _LEVEL + (24 if title else 0))

    place(root, 20, 0)
    width = total + 40
    height = 40 + (depth_max + 1) * _LEVEL + (24 if title else 0)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" font-family="Helvetica, Arial, sans-serif">',
        "<style>.n rect{stroke:#64748b;stroke-width:1}.n:hover rect{stroke:#dc2626;"
        "stroke-width:2}.l{font-size:12px;fill:#0f172a}.s{font-size:9px;fill:#475569}"
        ".e{stroke:#94a3b8;stroke-width:1.2;fill:none}</style>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    if title:
        out.append(f'<text x="20" y="22" font-size="15" font-weight="bold">{escape(title)}</text>')
    for n in root.walk():
        x, y = pos[id(n)]
        for c in n.children:
            cx, cy = pos[id(c)]
            out.append(f'<path class="e" d="M{x:.1f},{y + _H / 2:.1f} C{x:.1f},{y + _H:.1f} '
                       f'{cx:.1f},{cy - _H / 2 - 12:.1f} {cx:.1f},{cy - _H / 2:.1f}"/>')
    for n in root.walk():
        x, y = pos[id(n)]
        w = _node_width(n)
        tip = n.label
        attrs = f'data-id="{n.id}"'
        if n.span is not None:
            tip += f"  [{n.span}]\n{n.span.text(source)}"
            attrs += (f' data-start="{n.span.start.offset}" data-end="{n.span.end.offset}"')
        if n.ast_id is not None:
            attrs += f' data-ast="{n.ast_id}"'
        fill = _COLORS.get(n.kind, "#ffffff")
        out.append(f'<g class="n" {attrs}><title>{escape(tip)}</title>'
                   f'<rect x="{x - w / 2:.1f}" y="{y - _H / 2:.1f}" width="{w:.1f}" height="{_H}" '
                   f'rx="7" fill="{fill}"/>'
                   f'<text class="l" x="{x:.1f}" y="{y - 1:.1f}" text-anchor="middle">'
                   f"{escape(n.label)}</text>")
        if n.span is not None:
            out.append(f'<text class="s" x="{x:.1f}" y="{y + 12:.1f}" text-anchor="middle">'
                       f"{n.span}</text>")
        out.append("</g>")
    out.append("</svg>")
    return "\n".join(out) + "\n"
