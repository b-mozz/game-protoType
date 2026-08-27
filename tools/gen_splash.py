"""
Generates the blood splash sprite sheet.

Simulates a burst of droplets under gravity and bakes each step to a frame, so
the sheet is a horizontal strip that utils.helpers.load_frames can slice.
Re-run after tweaking the constants below to regenerate the asset.
"""
import math
import os
import random

import pygame

FRAMES = 9
SIZE = 96                       # px per frame, square
OUT = "assets/images/blood-splash.png"

DROPLETS = 44
SPEED = (2.6, 9.5)              # px per frame
GRAVITY = 0.55                  # px per frame squared
DROP_RADIUS = (1.4, 5.6)
CORE_RADIUS = 21                # opening blob, fades over the first frames

DEEP = (152, 20, 28)
MID = (206, 38, 42)
BRIGHT = (250, 96, 78)


def build(seed=7):
    random.seed(seed)
    cx = cy = SIZE / 2

    drops = []
    for _ in range(DROPLETS):
        a = random.uniform(0, math.tau)
        speed = random.uniform(*SPEED)
        drops.append({
            "x": cx, "y": cy,
            "vx": math.cos(a) * speed,
            "vy": math.sin(a) * speed - 1.4,     # slight upward bias
            "r": random.uniform(*DROP_RADIUS),
            "color": random.choice((DEEP, MID, MID, BRIGHT)),
        })

    frames = []
    for f in range(FRAMES):
        surf = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
        life = f / (FRAMES - 1)                  # 0 at burst, 1 at the end
        fade = max(0.0, 1.0 - life ** 1.6)

        if f < 4:                                # opening splat
            r = CORE_RADIUS * (0.45 + 0.55 * f / 3)
            alpha = int(255 * (1 - f / 4) ** 0.8)
            pygame.draw.circle(surf, (*MID, alpha), (round(cx), round(cy)), round(r))
            pygame.draw.circle(surf, (*BRIGHT, alpha), (round(cx), round(cy)), round(r * 0.55))

        for d in drops:
            r = d["r"] * (1 - 0.55 * life)
            if r < 0.6 or fade <= 0:
                continue
            pygame.draw.circle(surf, (*d["color"], int(255 * fade)),
                               (round(d["x"]), round(d["y"])), round(r))
            d["x"] += d["vx"]
            d["y"] += d["vy"]
            d["vy"] += GRAVITY
        frames.append(surf)

    sheet = pygame.Surface((SIZE * FRAMES, SIZE), pygame.SRCALPHA)
    for i, frame in enumerate(frames):
        sheet.blit(frame, (i * SIZE, 0))
    return sheet


if __name__ == "__main__":
    pygame.init()
    pygame.display.set_mode((1, 1))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    pygame.image.save(build(), OUT)
    print(f"wrote {OUT}  ({FRAMES} frames of {SIZE}x{SIZE})")
