#!/usr/bin/env python3
"""Gera os cards SVG do perfil (cabeçalho com o Doodieman, linguagens e projetos).

Usa só a biblioteca padrão. No GitHub Actions lê os dados pela API GraphQL
com o GITHUB_TOKEN; localmente dá para testar com --sample.

    python3 scripts/profile_cards.py --user EduBeloDev --out dist
    python3 scripts/profile_cards.py --sample --out /tmp/cards
"""

import argparse
import json
import math
import os
import random
import urllib.request
from datetime import datetime, timezone
from xml.sax.saxutils import escape

MONO = "'JetBrains Mono','Fira Code',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
SANS = "'Segoe UI','Helvetica Neue',Arial,sans-serif"

BG = "#0b1122"
PANEL = "#111a33"
TRACK = "#1c2747"
MINT = "#5eead4"
GREEN = "#3fb950"
TEXT = "#e6edf3"
MUTED = "#8b9bb4"

SUBTITLE = "Desenvolvedor em constante evolução"

QUERY = """
query($login: String!) {
  user(login: $login) {
    login
    name
    followers { totalCount }
    contributionsCollection { contributionCalendar { totalContributions } }
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      totalCount
      nodes {
        name
        description
        isFork
        stargazerCount
        pushedAt
        primaryLanguage { name color }
        repositoryTopics(first: 3) { nodes { topic { name } } }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          totalSize
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

SAMPLE = {
    "login": "EduBeloDev",
    "name": "Eduardo",
    "followers": 8,
    "contributions": 672,
    "repo_count": 7,
    "stars": 5,
    "languages": [
        ("Python", "#3572A5", 60.0),
        ("Rust", "#dea584", 22.0),
        ("PHP", "#4F5D95", 10.0),
        ("Shell", "#89e051", 6.0),
        ("HTML", "#e34c26", 2.0),
    ],
    "projects": [
        {
            "name": "awesome-project",
            "description": "Um projeto open-source para aprender na prática.",
            "stars": 3,
            "topics": ["open-source", "cli"],
            "language": ("Python", "#3572A5"),
            "share": 88,
            "pushed": "2026-10-22T08:00:00Z",
        },
        {
            "name": "rusty-tools",
            "description": "Ferramentas de terminal escritas em Rust.",
            "stars": 2,
            "topics": ["rust", "terminal"],
            "language": ("Rust", "#dea584"),
            "share": 56,
            "pushed": "2026-10-20T10:00:00Z",
        },
    ],
}


# ---------------------------------------------------------------- dados

def fetch(login, token):
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise SystemExit(f"Erro na API do GitHub: {payload['errors']}")
    user = payload["data"]["user"]

    repos = [r for r in user["repositories"]["nodes"] if not r["isFork"]]

    # linguagens ponderadas pelo tamanho do código em cada repositório
    sizes, colors = {}, {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            sizes[name] = sizes.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or MUTED
    total = sum(sizes.values()) or 1
    languages = [(n, colors[n], s * 100 / total)
                 for n, s in sorted(sizes.items(), key=lambda kv: -kv[1])[:5]]

    # projetos em destaque: mais estrelas primeiro, depois os mais recentes
    candidates = [r for r in repos if r["name"].lower() != login.lower()]
    candidates.sort(key=lambda r: r["stargazerCount"], reverse=True)  # estável: mantém a ordem por push
    projects = []
    for repo in candidates[:2]:
        lang = repo["primaryLanguage"]
        langs = repo["languages"]
        share = 0
        if lang and langs["totalSize"]:
            main = next((e["size"] for e in langs["edges"] if e["node"]["name"] == lang["name"]), 0)
            share = round(main * 100 / langs["totalSize"])
        projects.append({
            "name": repo["name"],
            "description": repo["description"] or "Sem descrição (ainda).",
            "stars": repo["stargazerCount"],
            "topics": [t["topic"]["name"] for t in repo["repositoryTopics"]["nodes"]][:2],
            "language": (lang["name"], lang["color"] or MUTED) if lang else None,
            "share": share,
            "pushed": repo["pushedAt"],
        })

    return {
        "login": user["login"],
        "name": user["name"] or user["login"],
        "followers": user["followers"]["totalCount"],
        "contributions": user["contributionsCollection"]["contributionCalendar"]["totalContributions"],
        "repo_count": user["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "languages": languages,
        "projects": projects,
    }


# ---------------------------------------------------------------- utilidades

def time_ago(iso):
    then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    hours, days = secs / 3600, secs / 86400
    if hours < 1:
        return "agora mesmo"
    if hours < 24:
        return f"há {int(hours)}h"
    if days < 30:
        return f"há {int(days)}d"
    if days < 365:
        months = int(days // 30)
        return f"há {months} {'mês' if months == 1 else 'meses'}"
    years = int(days // 365)
    return f"há {years} {'ano' if years == 1 else 'anos'}"


def wrap(text, width, lines):
    words, out, cur = text.split(), [], ""
    for word in words:
        if len(cur) + len(word) + (1 if cur else 0) <= width:
            cur = f"{cur} {word}".strip()
        else:
            out.append(cur)
            cur = word[:width]
    out.append(cur)
    out = [l for l in out if l]
    if len(out) > lines:
        out = out[:lines]
        out[-1] = out[-1][: width - 1].rstrip() + "…"
    return out


def svg_doc(width, height, body, extra_css=""):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<style>
  text {{ font-family: {MONO}; }}
  .twinkle {{ animation: twinkle 3s ease-in-out infinite; }}
  @keyframes twinkle {{ 0%, 100% {{ opacity: .15; }} 50% {{ opacity: .9; }} }}
  .cursor {{ animation: blink 1s steps(1) infinite; }}
  @keyframes blink {{ 50% {{ opacity: 0; }} }}
{extra_css}</style>
<defs>
  <linearGradient id="border" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{MINT}"/>
    <stop offset="1" stop-color="{GREEN}"/>
  </linearGradient>
  <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#0f1730"/>
    <stop offset="1" stop-color="{BG}"/>
  </linearGradient>
</defs>
<rect x="1.5" y="1.5" width="{width - 3}" height="{height - 3}" rx="14" fill="url(#bg)" stroke="url(#border)" stroke-opacity=".7" stroke-width="1.5"/>
{body}
</svg>
"""


def stars_field(width, height, count, seed, avoid=None):
    rnd = random.Random(seed)
    out = []
    for i in range(count):
        x, y = rnd.uniform(12, width - 12), rnd.uniform(12, height - 12)
        if avoid and avoid[0] < x < avoid[2] and avoid[1] < y < avoid[3]:
            continue
        r = rnd.choice([0.8, 1, 1.2, 1.6])
        delay = rnd.uniform(0, 3)
        out.append(f'<circle class="twinkle" style="animation-delay:{delay:.2f}s" cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="#cfe9ff"/>')
    return "\n".join(out)


# ---------------------------------------------------------------- Doodieman

PX = 4
GRID_W, GRID_H = 32, 34

BROWN = {"K": "#2b1608", "L": "#c08a4d", "B": "#8b5a2b", "D": "#5c3a1a"}
PALETTE = {
    **BROWN,
    "W": "#ffffff", "P": "#111111", "M": "#3a1208", "T": "#ff7a8a",
    "Y": "#f5c542", "O": "#c98a12", "R": "#e5484d", "r": "#9f1f26", "C": "#38bdf8",
    "S": "#ff9db0",
}


def _ellipse(grid, cx, cy, rx, ry):
    inside = set()
    for y in range(GRID_H):
        for x in range(GRID_W):
            if ((x + .5 - cx) / rx) ** 2 + ((y + .5 - cy) / ry) ** 2 <= 1:
                inside.add((x, y))
    for x, y in inside:
        if any((x + dx, y + dy) not in inside for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            grid[(x, y)] = "K"
            continue
        nx, ny = (x + .5 - cx) / rx, (y + .5 - cy) / ry
        if ny < -.35 and nx < .15:
            grid[(x, y)] = "L"
        elif ny > .45 or nx > .6:
            grid[(x, y)] = "D"
        else:
            grid[(x, y)] = "B"


def _paint(grid, rows, ox, oy):
    for dy, row in enumerate(rows):
        for dx, ch in enumerate(row):
            if ch != ".":
                grid[(ox + dx, oy + dy)] = ch


def _rects(grid):
    """Junta pixels vizinhos da mesma cor em retângulos horizontais."""
    out = []
    for y in range(GRID_H):
        x = 0
        while x < GRID_W:
            ch = grid.get((x, y))
            if not ch:
                x += 1
                continue
            start = x
            while x < GRID_W and grid.get((x, y)) == ch:
                x += 1
            out.append(f'<rect x="{start * PX}" y="{y * PX}" width="{(x - start) * PX}" height="{PX}" fill="{PALETTE[ch]}"/>')
    return "".join(out)


def doodieman():
    """Retorna (css, svg) do Doodieman em pixel art, num quadro de 128x136."""
    cape, body, lids, stink = {}, {}, {}, {}

    # capa de super-herói, atrás do corpo
    for y in range(15, 32):
        half = 9 + (y - 15) * 0.35
        for x in range(GRID_W):
            if abs(x + .5 - 16) <= half:
                edge = abs(x + .5 - 16) > half - 1 or y == 31
                cape[(x, y)] = "r" if edge else "R"
    for x in range(GRID_W):
        if (x // 2) % 2 and (x, 31) in cape:
            del cape[(x, 31)]

    # corpo em três camadas, de baixo para cima
    _ellipse(body, 16, 24.5, 11.5, 5.5)
    _ellipse(body, 16, 16.5, 8.5, 4.2)
    _ellipse(body, 16, 10.2, 5.6, 3.2)

    # coroa de rei do doodie
    _paint(body, [
        "Y...Y...Y",
        "YY.YYY.YY",
        "YYYYYYYYY",
        "YRYYCYYRY",
        "OOOOOOOOO",
    ], 12, 2)

    # sobrancelhas de herói e olhos grandes
    _paint(body, [
        "KKK.....KKK",
        ".KKK...KKK.",
        "KWWWK.KWWWK",
        "KWWPK.KPWWK",
        "KWWPK.KPWWK",
        ".KKK...KKK.",
    ], 10, 13)
    _paint(lids, [
        "BBB...BBB",
        "BBB...BBB",
        "KKK...KKK",
    ], 11, 15)

    # sorriso com língua e bochechas
    _paint(body, [
        "S.KKKKKKKKK.S",
        "..KMMMMMMMK..",
        "...KMTTTMK...",
        "....KKKKK....",
    ], 10, 22)

    # braço erguido (punho de herói) e pezinhos
    _paint(body, [
        ".KK",
        "KBBK",
        "KBBK",
        ".KBK",
        ".KBK",
        "KBK.",
        "KBK.",
    ], 26, 13)
    _paint(body, [
        "KKKK.......KKKK",
        "KDDDK.....KDDDK",
        ".KKKK.....KKKK.",
    ], 8, 29)

    # cheirinho subindo
    for i, (x, y) in enumerate(((4, 4), (6, 1), (25, 2))):
        for k in range(5):
            stink[(x + (k % 2), y + k)] = "C"

    css = """
  .dm { animation: dm-bounce 1.4s ease-in-out infinite; }
  @keyframes dm-bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-6px); } }
  .dm-cape { transform-box: fill-box; transform-origin: 50% 0; animation: dm-cape 1.4s ease-in-out infinite; }
  @keyframes dm-cape { 0%, 100% { transform: skewX(6deg); } 50% { transform: skewX(-6deg); } }
  .dm-lids { opacity: 0; animation: dm-blink 4s steps(1) infinite; }
  @keyframes dm-blink { 0%, 90% { opacity: 0; } 92%, 96% { opacity: 1; } 98% { opacity: 0; } }
  .dm-stink { animation: dm-stink 2.2s ease-out infinite; }
  @keyframes dm-stink { 0% { transform: translateY(6px); opacity: 0; } 30% { opacity: .9; } 100% { transform: translateY(-10px); opacity: 0; } }
  .dm-bubble { transform-box: fill-box; transform-origin: 100% 100%; animation: dm-pop 4s ease-in-out infinite; }
  @keyframes dm-pop { 0%, 8% { transform: scale(0); } 16%, 70% { transform: scale(1); } 80%, 100% { transform: scale(0); } }
"""
    svg = (
        f'<g class="dm-stink" fill-opacity=".8">{_rects(stink)}</g>'
        f'<g class="dm">'
        f'<g class="dm-cape">{_rects(cape)}</g>'
        f'<g shape-rendering="crispEdges">{_rects(body)}</g>'
        f'<g class="dm-lids" shape-rendering="crispEdges">{_rects(lids)}</g>'
        f'</g>'
    )
    return css, svg


def render_doodieman():
    css, svg = doodieman()
    w, h = GRID_W * PX, GRID_H * PX
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w * 2}" height="{h * 2}" viewBox="0 0 {w} {h}" shape-rendering="crispEdges">
<style>{css}</style>
{svg}
</svg>
"""


# ---------------------------------------------------------------- cards

ICONS = {
    "repo": '<rect x="2" y="2" width="12" height="13" rx="2"/><path d="M5 2v13M8 6h4M8 9h4"/>',
    "star": '<path d="M8 1.5l2 4.3 4.6.5-3.4 3.1 1 4.6L8 11.6 3.8 14l1-4.6L1.4 6.3 6 5.8z"/>',
    "contrib": '<path d="M2 14h12M4 14V8M8 14V3M12 14V6"/>',
    "people": '<circle cx="8" cy="5" r="3"/><path d="M2.5 15c.6-3 2.8-4.6 5.5-4.6s4.9 1.6 5.5 4.6"/>',
}


def icon(name, x, y):
    return (f'<g transform="translate({x} {y})" fill="none" stroke="{MINT}" stroke-width="1.5" '
            f'stroke-linejoin="round" stroke-linecap="round">{ICONS[name]}</g>')


def chip(x, y, label, color):
    w = len(label) * 7.2 + 30
    return (f'<g transform="translate({x:.1f} {y})">'
            f'<rect width="{w:.1f}" height="24" rx="12" fill="{PANEL}" stroke="#2a3a63"/>'
            f'<circle cx="13" cy="12" r="4" fill="{color}"/>'
            f'<text x="22" y="16.5" font-size="12" fill="{TEXT}">{escape(label)}</text></g>'), w


def render_header(d):
    W, H = 860, 250
    dm_css, dm_svg = doodieman()

    parts = [stars_field(W, H, 46, d["login"], avoid=(24, 30, 420, 210))]
    parts.append(f'<text x="36" y="62" font-size="15" fill="{MINT}">@{escape(d["login"])}</text>')
    parts.append(f'<text x="34" y="110" font-size="44" font-weight="700" fill="{TEXT}" '
                 f'style="font-family:{SANS}">{escape(d["name"])}</text>')
    parts.append(f'<text x="36" y="142" font-size="14" fill="{MUTED}">{escape(SUBTITLE)}</text>')

    x = 36
    for name, color, _ in d["languages"][:4]:
        svg, w = chip(x, 168, name, color)
        if x + w > 410:
            break
        parts.append(svg)
        x += w + 8

    stats = [
        ("repo", d["repo_count"], "Repositórios"),
        ("star", d["stars"], "Estrelas"),
        ("contrib", d["contributions"], "Contribuições"),
        ("people", d["followers"], "Seguidores"),
    ]
    for i, (ic, value, label) in enumerate(stats):
        y = 64 + i * 36
        parts.append(icon(ic, 440, y - 13))
        parts.append(f'<text x="466" y="{y}" font-size="15" fill="{TEXT}">'
                     f'<tspan font-weight="700" fill="{MINT}">{value}</tspan>  {label}</text>')

    # Doodieman com o balão de fala
    parts.append(
        f'<g transform="translate(676 58) scale(1.25)">{dm_svg}</g>'
        f'<g class="dm-bubble" transform="translate(610 22)">'
        f'<rect width="150" height="30" rx="8" fill="{TEXT}"/>'
        f'<path d="M126 29l12 12-2-12z" fill="{TEXT}"/>'
        f'<text x="75" y="20" font-size="11.5" font-weight="700" fill="#2b1608" text-anchor="middle">IT\'S DOODIE TIME!</text>'
        f'</g>'
    )
    return svg_doc(W, H, "\n".join(parts), dm_css)


def render_languages(d):
    W, H = 420, 250
    parts = [
        f'<text x="24" y="38" font-size="17" font-weight="700" fill="{TEXT}">Stack de linguagens</text>',
        f'<text x="24" y="58" font-size="11" fill="{MINT}">ponderado pelos repositórios</text>',
        f'<text x="396" y="38" font-size="11" fill="{MINT}" text-anchor="end">&gt; stack.scan<tspan class="cursor">_</tspan></text>',
    ]
    # sem fill-mode: onde a animação não roda, as barras aparecem cheias
    css = "  .bar { transform-box: fill-box; transform-origin: 0 50%; animation: grow 1.6s ease-out; }\n" \
          "  @keyframes grow { from { transform: scaleX(0); } }\n"
    for i, (name, color, pct) in enumerate(d["languages"][:5]):
        y = 90 + i * 32
        parts.append(f'<circle cx="30" cy="{y - 4}" r="5" fill="{color}"/>')
        parts.append(f'<text x="44" y="{y}" font-size="13" fill="{TEXT}">{escape(name)}</text>')
        parts.append(f'<text x="196" y="{y}" font-size="12" fill="{color}" text-anchor="end">{pct:.0f}%</text>')
        parts.append(f'<rect x="210" y="{y - 9}" width="186" height="8" rx="4" fill="{TRACK}"/>')
        width = max(186 * pct / 100, 6)
        parts.append(f'<rect class="bar" x="210" y="{y - 9}" '
                     f'width="{width:.1f}" height="8" rx="4" fill="{color}"/>')
    if not d["languages"]:
        parts.append(f'<text x="24" y="120" font-size="13" fill="{MUTED}">Nenhum código público ainda.</text>')
    return svg_doc(W, H, "\n".join(parts), css)


def ring(cx, cy, pct, color):
    r = 17
    c = 2 * math.pi * r
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{TRACK}" stroke-width="4"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="4" '
            f'stroke-linecap="round" stroke-dasharray="{c * pct / 100:.1f} {c:.1f}" '
            f'transform="rotate(-90 {cx} {cy})"/>'
            f'<text x="{cx}" y="{cy + 4}" font-size="10" font-weight="700" fill="{TEXT}" text-anchor="middle">{pct}%</text>')


def render_projects(d):
    W, H = 420, 250
    parts = [
        f'<text x="24" y="38" font-size="13" fill="{TEXT}">Projects.list '
        f'<tspan fill="{MUTED}">./projetos.sh --all</tspan><tspan class="cursor" fill="{MINT}">_</tspan></text>',
    ]
    for i, p in enumerate(d["projects"][:2]):
        x, y = 18 + i * 196, 56
        lang_name, lang_color = p["language"] or ("Outros", MUTED)
        out = [f'<rect width="188" height="176" rx="10" fill="{PANEL}" stroke="#2a3a63"/>',
               f'<circle cx="16" cy="22" r="4" fill="{lang_color}"/>',
               f'<text x="26" y="26" font-size="12" font-weight="700" fill="{TEXT}">{escape(p["name"][:20])}</text>']
        for j, line in enumerate(wrap(p["description"], 18, 3)):
            out.append(f'<text x="14" y="{52 + j * 16}" font-size="10.5" fill="{MUTED}">{escape(line)}</text>')
        out.append(ring(158, 62, p["share"], lang_color))
        tx = 14
        for label in (p["topics"] or [lang_name])[:2]:
            label = label[:12]
            w = len(label) * 6.2 + 14
            if tx + w > 178:
                break
            out.append(f'<rect x="{tx}" y="112" width="{w:.1f}" height="20" rx="6" fill="none" stroke="#3b5bdb" stroke-opacity=".8"/>'
                       f'<text x="{tx + 7}" y="126" font-size="10" fill="#91a7ff">{escape(label)}</text>')
            tx += w + 6
        out.append(f'<text x="14" y="158" font-size="10.5" fill="{MUTED}">'
                   f'<tspan fill="#f5c542">★</tspan> {p["stars"]}   atualizado {time_ago(p["pushed"])}</text>')
        parts.append(f'<g transform="translate({x} {y})">{"".join(out)}</g>')
    if not d["projects"]:
        parts.append(f'<text x="24" y="120" font-size="13" fill="{MUTED}">Os primeiros projetos estão a caminho.</text>')
    return svg_doc(W, H, "\n".join(parts))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--user", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "EduBeloDev"))
    ap.add_argument("--out", default="dist")
    ap.add_argument("--sample", action="store_true", help="usa dados de exemplo em vez da API")
    args = ap.parse_args()

    if args.sample:
        data = SAMPLE
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("Defina GITHUB_TOKEN (ou use --sample).")
        data = fetch(args.user, token)

    os.makedirs(args.out, exist_ok=True)
    files = {
        "profile-header.svg": render_header(data),
        "profile-languages.svg": render_languages(data),
        "profile-projects.svg": render_projects(data),
        "doodieman.svg": render_doodieman(),
    }
    for name, content in files.items():
        with open(os.path.join(args.out, name), "w", encoding="utf-8") as fh:
            fh.write(content)
        print(f"gerado {args.out}/{name}")


if __name__ == "__main__":
    main()
