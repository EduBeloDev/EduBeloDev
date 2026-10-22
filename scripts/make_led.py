#!/usr/bin/env python3
"""Converte uma imagem do personagem na matriz de LEDs usada no cabeçalho.

Só é preciso rodar quando quiser trocar o desenho (precisa do Pillow):

    pip install pillow
    python3 scripts/make_led.py ed.jpg --palette ed --crop 200,14,700,818 --cols 48
    python3 scripts/make_led.py doodieman.jpg --palette doodieman --crop 180,420,980,1484 --cols 60

O fundo (céu ciano, nuvens brancas ou o xadrez de "transparente") é removido
com um flood fill a partir das bordas de cima e dos lados (o personagem
costuma estar cortado embaixo); sobra só o maior pedaço conectado, que é o
personagem. O resultado vai para assets/<paleta>-led.txt, lido por
profile_cards.py.
"""

import argparse
from collections import deque

from PIL import Image

# cores dos LEDs por personagem: letra -> (cor do LED, cor de referência na imagem)
PALETTES = {
    "doodieman": {
        "R": ("#ff2b2b", (254, 0, 0)),
        "r": ("#b3141c", (150, 10, 10)),
        "p": ("#ff8a8a", (255, 140, 140)),
        "S": ("#ffc79e", (250, 200, 160)),
        "W": ("#ffffff", (255, 255, 255)),
        "G": ("#9aa3b5", (150, 150, 150)),
        "K": ("#4a3040", (20, 20, 20)),
    },
    "ed": {
        "Y": ("#fff35c", (255, 247, 114)),
        "y": ("#c9b435", (190, 175, 75)),
        "J": ("#93b83c", (100, 113, 59)),
        "j": ("#56702a", (55, 62, 32)),
        "R": ("#ff3b2b", (184, 37, 27)),
        "P": ("#ffa98a", (224, 160, 132)),
        "W": ("#ffffff", (255, 255, 255)),
        "K": ("#3d3640", (30, 28, 30)),
    },
}


def is_background(rgb):
    r, g, b = rgb
    sky = r < 200 and g > 210 and b > 210
    light_gray = min(rgb) > 225 and max(rgb) - min(rgb) < 20   # nuvem ou xadrez
    return sky or light_gray


def foreground_mask(img):
    w, h = img.size
    px = img.load()
    bg = bytearray(w * h)
    queue = deque()
    for x in range(w):
        queue.append((x, 0))
    for y in range(h):
        queue.extend(((0, y), (w - 1, y)))
    while queue:
        x, y = queue.popleft()
        i = y * w + x
        if bg[i] or not is_background(px[x, y]):
            continue
        bg[i] = 1
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not bg[ny * w + nx]:
                queue.append((nx, ny))

    # fica só com o maior pedaço que não é fundo (descarta ícones soltos)
    label = [0] * (w * h)
    best, best_size, current = 0, 0, 0
    for start in range(w * h):
        if bg[start] or label[start]:
            continue
        current += 1
        size, queue = 0, deque([start])
        label[start] = current
        while queue:
            i = queue.popleft()
            size += 1
            x, y = i % w, i // w
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                j = ny * w + nx
                if 0 <= nx < w and 0 <= ny < h and not bg[j] and not label[j]:
                    label[j] = current
                    queue.append(j)
        if size > best_size:
            best, best_size = current, size
    return [lab == best for lab in label]


def nearest(rgb, palette):
    return min(palette, key=lambda k: sum((a - b) ** 2 for a, b in zip(rgb, palette[k][1])))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image")
    ap.add_argument("--crop", help="x0,y0,x1,y1 da área do personagem")
    ap.add_argument("--cols", type=int, default=44)
    ap.add_argument("--fill", type=float, default=0.45, help="fração mínima do personagem na célula")
    ap.add_argument("--lines", type=float, default=0.3, help="fração de contorno que vira LED apagado")
    ap.add_argument("--palette", choices=PALETTES, default="ed")
    ap.add_argument("--out", help="padrão: assets/<paleta>-led.txt")
    args = ap.parse_args()
    palette = PALETTES[args.palette]
    out = args.out or f"assets/{args.palette}-led.txt"

    img = Image.open(args.image).convert("RGB")
    if args.crop:
        img = img.crop(tuple(int(v) for v in args.crop.split(",")))
    w, h = img.size
    mask = foreground_mask(img)
    px = img.load()

    cache = {}
    cell = w / args.cols
    rows = int(h / cell)
    lines = []
    for gy in range(rows):
        line = []
        for gx in range(args.cols):
            x0, x1 = int(gx * cell), int((gx + 1) * cell)
            y0, y1 = int(gy * cell), int((gy + 1) * cell)
            votes = {}
            for y in range(y0, y1):
                for x in range(x0, x1):
                    if mask[y * w + x]:
                        rgb = px[x, y]
                        if rgb not in cache:
                            cache[rgb] = nearest(rgb, palette)
                        votes[cache[rgb]] = votes.get(cache[rgb], 0) + 1
            total = sum(votes.values())
            area = (x1 - x0) * (y1 - y0)
            if total / area < args.fill:
                line.append(".")
            elif votes.get("K", 0) / total >= args.lines:
                # contornos finos (olhos, boca) ganham prioridade para não sumirem
                line.append("K")
            else:
                line.append(max((k for k in votes if k != "K"), key=votes.get, default="K"))
        lines.append("".join(line).rstrip("."))

    while lines and not lines[0]:
        lines.pop(0)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(f"# {args.palette} em LEDs, gerado por scripts/make_led.py\n")
        for key, (color, _) in palette.items():
            fh.write(f"# {key} {color}\n")
        fh.write("\n".join(lines) + "\n")
    print(f"{out}: {args.cols}x{len(lines)}")


if __name__ == "__main__":
    main()
