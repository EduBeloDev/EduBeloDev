#!/usr/bin/env python3
"""Gera os cards SVG do perfil (cabeçalho com o personagem em LEDs, cidade 3D, linguagens e projetos).

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
from datetime import date, datetime, timedelta, timezone
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
# personagem em LEDs do cabeçalho (matriz gerada por make_led.py) e a fala dele
CHARACTER = "ed"
SPEECH = "IT'S COFRE TIME!"
LED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", f"{CHARACTER}-led.txt")

QUERY = """
query($login: String!) {
  user(login: $login) {
    login
    name
    followers { totalCount }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
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


def sample_calendar():
    rnd = random.Random(7)
    start = date(2025, 10, 26)
    days = []
    for i in range(52 * 7 + 4):
        busy = rnd.random() < (0.25 if (start + timedelta(i)).weekday() >= 5 else 0.45)
        count = int(rnd.expovariate(1 / 4)) + 1 if busy else 0
        days.append(((start + timedelta(i)).isoformat(), min(count, 62)))
    return days


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

    calendar = user["contributionsCollection"]["contributionCalendar"]
    days = [(day["date"], day["contributionCount"])
            for week in calendar["weeks"] for day in week["contributionDays"]]

    return {
        "login": user["login"],
        "name": user["name"] or user["login"],
        "followers": user["followers"]["totalCount"],
        "contributions": calendar["totalContributions"],
        "calendar": days,
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


# ---------------------------------------------------------------- personagem

def load_led(path=LED_FILE):
    """Lê a matriz gerada por make_led.py: '# letra cor' e depois as linhas."""
    palette, rows = {}, []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            parts = line.split()
            if line.startswith("#"):
                if len(parts) == 3 and parts[2].startswith("#"):
                    palette[parts[1]] = parts[2]
            else:
                rows.append(line)
    return palette, rows


def led_character(x0, y0, pitch, uid="dm"):
    """Personagem como painel de LEDs: um ponto colorido por célula, com brilho e onda de luz."""
    palette, rows = load_led()
    cols = max(len(r) for r in rows)
    w, h = cols * pitch, len(rows) * pitch
    r = pitch * 0.36
    rnd = random.Random(uid)

    lines = []
    for y, row in enumerate(rows):
        dots = "".join(
            f'<circle cx="{(x + .5) * pitch:.1f}" cy="{(y + .5) * pitch:.1f}" r="{r:.2f}" fill="{palette[ch]}"/>'
            for x, ch in enumerate(row) if ch != "."
        )
        if dots:
            lines.append(f'<g class="led" style="animation-delay:{y * .045:.2f}s">{dots}</g>')

    # alguns LEDs que piscam em branco, como numa tela de verdade
    lit = [(x, y) for y, row in enumerate(rows) for x, ch in enumerate(row) if ch not in ".K"]
    sparks = "".join(
        f'<circle class="spark" style="animation-delay:{rnd.uniform(0, 5):.2f}s" '
        f'cx="{(x + .5) * pitch:.1f}" cy="{(y + .5) * pitch:.1f}" r="{r * 1.2:.2f}" fill="#ffffff"/>'
        for x, y in rnd.sample(lit, min(14, len(lit)))
    )

    defs = f"""<defs>
  <pattern id="{uid}-grid" width="{pitch}" height="{pitch}" patternUnits="userSpaceOnUse">
    <circle cx="{pitch / 2}" cy="{pitch / 2}" r="{r * .8:.2f}" fill="#24304f"/>
  </pattern>
  <radialGradient id="{uid}-vignette" cx=".5" cy=".45" r=".6">
    <stop offset=".55" stop-color="#fff"/>
    <stop offset="1" stop-color="#000"/>
  </radialGradient>
  <linearGradient id="{uid}-fade" x1="0" y1="0" x2="0" y2="1">
    <stop offset=".8" stop-color="#fff"/>
    <stop offset="1" stop-color="#000"/>
  </linearGradient>
  <mask id="{uid}-panel"><rect x="-{pitch * 6}" y="0" width="{w + pitch * 12}" height="{h}" fill="url(#{uid}-vignette)"/></mask>
  <mask id="{uid}-bottom"><rect width="{w}" height="{h}" fill="url(#{uid}-fade)"/></mask>
  <filter id="{uid}-glow" x="-10%" y="-10%" width="120%" height="120%">
    <feGaussianBlur stdDeviation="{pitch * .45:.2f}" result="blur"/>
    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
</defs>"""
    svg = (f'<g transform="translate({x0:.1f} {y0:.1f})">{defs}'
           f'<rect x="-{pitch * 6}" width="{w + pitch * 12}" height="{h}" fill="url(#{uid}-grid)" mask="url(#{uid}-panel)"/>'
           f'<g mask="url(#{uid}-bottom)"><g filter="url(#{uid}-glow)">{"".join(lines)}</g>{sparks}</g>'
           f'</g>')
    return svg, w, h


LED_CSS = """
  .led { animation: led-wave 3.6s ease-in-out infinite; }
  @keyframes led-wave { 0%, 100% { opacity: 1; } 50% { opacity: .55; } }
  .spark { opacity: 0; animation: spark 5s ease-in-out infinite; }
  @keyframes spark { 0%, 86%, 100% { opacity: 0; } 92% { opacity: .95; } }
  .dm-float { animation: dm-float 3s ease-in-out infinite; }
  @keyframes dm-float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-4px); } }
  .dm-bubble { transform-box: fill-box; transform-origin: 100% 50%; animation: dm-pop 5s ease-in-out infinite; }
  @keyframes dm-pop { 0%, 8% { transform: scale(0); } 14%, 72% { transform: scale(1); } 80%, 100% { transform: scale(0); } }
"""


def render_character():
    svg, w, h = led_character(20, 20, 5)
    return svg_doc(int(w + 40), int(h + 40), svg, LED_CSS)


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
    W, H = 860, 320
    parts = [stars_field(W, H, 40, d["login"], avoid=(24, 24, 440, 310))]
    parts.append(f'<path d="M22 22h10M27 17v10" stroke="{MINT}" stroke-width="1.2" class="twinkle"/>')
    parts.append(f'<text x="36" y="62" font-size="15" fill="{MINT}">@{escape(d["login"])}</text>')
    parts.append(f'<text x="34" y="110" font-size="46" font-weight="700" fill="#f0fbff" filter="url(#name-glow)" '
                 f'style="font-family:{SANS}">{escape(d["name"])}</text>')
    parts.append(f'<text x="36" y="140" font-size="14" fill="{MUTED}">{escape(SUBTITLE)}</text>')

    stats = [
        ("repo", d["repo_count"], "Repositórios"),
        ("star", d["stars"], "Estrelas"),
        ("contrib", d["contributions"], "Contribuições"),
        ("people", d["followers"], "Seguidores"),
    ]
    for i, (ic, value, label) in enumerate(stats):
        y = 180 + i * 27
        parts.append(icon(ic, 36, y - 13))
        parts.append(f'<text x="62" y="{y}" font-size="14" fill="{TEXT}">'
                     f'<tspan font-weight="700" fill="{MINT}">{value}</tspan>  {label}</text>')

    x = 36
    for name, color, _ in d["languages"][:4]:
        svg, w = chip(x, 278, name, color)
        if x + w > 470:
            break
        parts.append(svg)
        x += w + 8

    # personagem em LEDs à direita, com o balão de fala
    pitch = min(3.9, 280 / len(load_led()[1]))
    led, w, h = led_character(0, 0, pitch)
    left = W - 30 - w
    parts.append(f'<g class="dm-float"><g transform="translate({left:.1f} {(H - h) / 2:.1f})">{led}</g></g>')
    parts.append(
        f'<g class="dm-bubble" transform="translate({left - 160:.1f} 62)">'
        f'<rect width="150" height="30" rx="8" fill="{TEXT}"/>'
        f'<path d="M149 9l14 8-14 5z" fill="{TEXT}"/>'
        f'<text x="75" y="20" font-size="11.5" font-weight="700" fill="#3f5a1a" text-anchor="middle">{escape(SPEECH)}</text>'
        f'</g>'
    )
    glow = """<defs><filter id="name-glow" x="-10%" y="-30%" width="120%" height="160%">
  <feGaussianBlur stdDeviation="3" result="b"/><feFlood flood-color="#5eead4" flood-opacity=".6"/>
  <feComposite in2="b" operator="in"/><feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
</filter></defs>"""
    return svg_doc(W, H, glow + "\n".join(parts), LED_CSS)


def city_stats(days):
    counts = [c for _, c in days]
    active = sum(1 for c in counts if c)
    best = streak = 0
    for c in counts:
        streak = streak + 1 if c else 0
        best = max(best, streak)
    return active, max(counts, default=0), best


def render_city(d):
    """Cidade isométrica: cada dia vira um prédio com a altura das contribuições."""
    W, H = 860, 300
    days = d["calendar"][-53 * 7:]
    active, busiest, streak = city_stats(days)

    # posição de cada dia: coluna = semana (começando no domingo), linha = dia da semana
    first = date.fromisoformat(days[0][0]) if days else date.today()
    offset = (first.weekday() + 1) % 7
    cells = [((offset + i) // 7, (offset + i) % 7, c, day) for i, (day, c) in enumerate(days)]
    today = days[-1] if days else (date.today().isoformat(), 0)

    ux, uy, vx, vy = 7.0, -2.2, 8.0, 4.0      # vetores da semana e do dia
    ox, oy = 380, 248
    peak = max(busiest, 1)
    tops = ["#1f7a6d", "#2bb39b", "#45d6bd", "#8af7e3"]

    def shade(hex_color, k):
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
        return f"#{int(r * k):02x}{int(g * k):02x}{int(b * k):02x}"

    def pt(x, y):
        return f"{x:.1f},{y:.1f}"

    def label(day, c):
        dia = date.fromisoformat(day).strftime("%d/%m/%Y")
        return f"<title>{c} contribuiç{'ão' if c == 1 else 'ões'} em {dia}</title>"

    blocks, beacon = [], ""
    # desenha de trás para a frente (de cima para baixo na tela)
    for w, dd, c, day in sorted(cells, key=lambda t: t[0] * uy + t[1] * vy):
        ax, ay = ox + w * ux + dd * vx, oy + w * uy + dd * vy
        A, B, C, D = (ax, ay), (ax + ux, ay + uy), (ax + ux + vx, ay + uy + vy), (ax + vx, ay + vy)
        is_today = day == today[0]
        if not c:
            # hoje sem contribuições: o lote fica piscando, esperando um prédio
            cls = ' class="lot-today"' if is_today else ''
            blocks.append(f'<polygon{cls} points="{" ".join(pt(*p) for p in (A, B, C, D))}" fill="#0f2a33" '
                          f'stroke="#1b4650" stroke-width=".5">{label(day, c)}</polygon>')
            continue
        level = min(3, int(4 * c / (peak + 1)))
        h = 5 + 88 * (c / peak) ** .6
        up = lambda p: (p[0], p[1] - h)
        top = " ".join(pt(*up(p)) for p in (A, B, C, D))
        left = " ".join(pt(*p) for p in (A, D, up(D), up(A)))
        right = " ".join(pt(*p) for p in (D, C, up(C), up(D)))
        blocks.append(
            f'<g class="bld{" bld-today" if is_today else ""}" style="animation-delay:{w * .03:.2f}s">{label(day, c)}'
            f'<polygon points="{left}" fill="{shade(tops[level], .62)}"/>'
            f'<polygon points="{right}" fill="{shade(tops[level], .42)}"/>'
            f'<polygon points="{top}" fill="{tops[level]}" stroke="#bafff2" stroke-opacity=".35" stroke-width=".5"/></g>'
        )
        if is_today:
            # farol de luz em cima do prédio de hoje
            bx, by = (A[0] + C[0]) / 2, (A[1] + C[1]) / 2 - h
            beacon = (f'<g class="beacon"><rect x="{bx - 1.5:.1f}" y="{by - 44:.1f}" width="3" height="44" '
                      f'fill="url(#beam)"/><circle cx="{bx:.1f}" cy="{by:.1f}" r="3.5" fill="#ffffff"/></g>')

    parts = [
        stars_field(W, H, 30, "city", avoid=(300, 20, 850, 290)),
        f'<text x="32" y="56" font-size="20" font-weight="700" fill="{TEXT}">A cidade que construí este ano</text>',
        f'<text x="830" y="40" font-size="11" fill="{MINT}" text-anchor="end">visão 3D<tspan class="cursor">_</tspan></text>',
        f'<text x="32" y="104" font-size="13" fill="{MINT}" letter-spacing="1">CONTRIBUIÇÕES</text>',
        f'<text x="30" y="150" font-size="42" font-weight="700" fill="#f0fbff">{d["contributions"]}</text>',
        f'<text x="32" y="188" font-size="14" fill="{TEXT}">{active} dias ativos</text>',
        f'<text x="32" y="212" font-size="14" fill="{TEXT}">Dia mais ativo: {busiest}</text>',
        f'<text x="32" y="236" font-size="14" fill="{TEXT}">Maior sequência: {streak} dias</text>',
        f'<circle class="pulse" cx="38" cy="262" r="4" fill="{MINT}"/>'
        f'<text x="50" y="267" font-size="13" fill="{MINT}">Hoje: {today[1]} contribuiç{"ão" if today[1] == 1 else "ões"}</text>',
        '<defs><linearGradient id="beam" x1="0" y1="1" x2="0" y2="0">'
        f'<stop offset="0" stop-color="{MINT}" stop-opacity=".9"/><stop offset="1" stop-color="{MINT}" stop-opacity="0"/>'
        '</linearGradient></defs>',
        f'<g class="city">{"".join(blocks)}</g>{beacon}',
    ]
    css = """  .bld { transform-box: fill-box; transform-origin: 50% 100%; animation: rise 1.4s ease-out backwards; }
  @keyframes rise { from { transform: scaleY(0); } }
  .bld-today polygon:last-child { animation: today 1.6s ease-in-out infinite; }
  @keyframes today { 50% { fill: #ffffff; } }
  .lot-today { animation: lot 1.6s ease-in-out infinite; }
  @keyframes lot { 50% { fill: #5eead4; stroke: #ffffff; } }
  .beacon, .pulse { animation: beacon 1.6s ease-in-out infinite; }
  @keyframes beacon { 0%, 100% { opacity: .35; } 50% { opacity: 1; } }
  /* ao abrir o SVG direto no navegador: passe o mouse para ver cada dia */
  .city .bld:hover polygon { fill: #ffffff; }
  .city polygon:hover { fill: #5eead4; }
"""
    return svg_doc(W, H, "\n".join(parts), css)


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
        data = {**SAMPLE, "calendar": sample_calendar()}
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("Defina GITHUB_TOKEN (ou use --sample).")
        data = fetch(args.user, token)

    os.makedirs(args.out, exist_ok=True)
    files = {
        "profile-header.svg": render_header(data),
        "profile-city.svg": render_city(data),
        "profile-languages.svg": render_languages(data),
        "profile-projects.svg": render_projects(data),
        f"{CHARACTER}.svg": render_character(),
    }
    for name, content in files.items():
        with open(os.path.join(args.out, name), "w", encoding="utf-8") as fh:
            fh.write(content)
        print(f"gerado {args.out}/{name}")


if __name__ == "__main__":
    main()
