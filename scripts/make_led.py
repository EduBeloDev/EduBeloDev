#!/usr/bin/env python3
"""Converte uma imagem do personagem na matriz de LEDs usada no cabeçalho.

Só é preciso rodar quando quiser trocar o desenho (precisa do Pillow):

    pip install pillow
    python3 scripts/make_led.py imagem.jpg --crop 140,420,1010,1480 --cols 44

O fundo (céu ciano e nuvens brancas) é removido com um flood fill a partir
das bordas; sobra só o maior pedaço conectado, que é o personagem. O
resultado vai para assets/doodieman-led.txt, lido por profile_cards.py.
"""

import argparse
from collections import deque

from PIL import Image

# cores dos LEDs: letra -> (cor no arquivo, cor de referência na imagem)
PALETTE = {
    "R": ("#ff2b2b", (254, 0, 0)),
    "r": ("#b3141c", (150, 10, 10)),
    "p": ("#ff8a8a", (255, 140, 140)),
    "S": ("#ffc79e", (250, 200, 160)),
    "W": ("#ffffff", (255, 255, 255)),
    "G": ("#9aa3b5", (150, 150, 150)),
    "K": ("#4a3040", (20, 20, 20)),
}


def is_background(rgb):
    r, g, b = rgb
    sky = r < 200 and g > 210 and b > 210
    cloud = r > 225 and g > 225 and b > 225
    return sky or cloud


def foreground_mask(img):
    w, h = img.size
    px = img.load()
    bg = bytearray(w * h)
    queue = deque()
    for x in range(w):
        queue.extend(((x, 0), (x, h - 1)))
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


def nearest(rgb):
    return min(PALETTE, key=lambda k: sum((a - b) ** 2 for a, b in zip(rgb, PALETTE[k][1])))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image")
    ap.add_argument("--crop", help="x0,y0,x1,y1 da área do personagem")
    ap.add_argument("--cols", type=int, default=44)
    ap.add_argument("--fill", type=float, default=0.45, help="fração mínima do personagem na célula")
    ap.add_argument("--out", default="assets/doodieman-led.txt")
    args = ap.parse_args()

    img = Image.open(args.image).convert("RGB")
    if args.crop:
        img = img.crop(tuple(int(v) for v in args.crop.split(",")))
    w, h = img.size
    mask = foreground_mask(img)
    px = img.load()

    cell = w / args.cols
    rows = int(h / cell)
    lines = []
    for gy in range(rows):
        line = []
        for gx in range(args.cols):
            x0, x1 = int(gx * cell), int((gx + 1) * cell)
            y0, y1 = int(gy * cell), int((gy + 1) * cell)
            total, acc = 0, [0, 0, 0]
            for y in range(y0, y1):
                for x in range(x0, x1):
                    if mask[y * w + x]:
                        total += 1
                        for k, v in enumerate(px[x, y]):
                            acc[k] += v
            area = (x1 - x0) * (y1 - y0)
            if total / area < args.fill:
                line.append(".")
            else:
                line.append(nearest(tuple(v / total for v in acc)))
        lines.append("".join(line).rstrip("."))

    while lines and not lines[0]:
        lines.pop(0)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write("# Doodieman em LEDs, gerado por scripts/make_led.py\n")
        for key, (color, _) in PALETTE.items():
            fh.write(f"# {key} {color}\n")
        fh.write("\n".join(lines) + "\n")
    print(f"{args.out}: {args.cols}x{len(lines)}")


if __name__ == "__main__":
    main()
