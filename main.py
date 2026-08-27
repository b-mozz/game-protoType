import math
import random

import pygame
import config as cfg
from utils.helpers import load_frames, load_layers, Animation, RingCanvas, Seg

W, H = cfg.WIDTH, cfg.HEIGHT # game width and height
out_rad, in_rad = 180, 150
CX, CY = W // 2, H // 2 # center of the ring, in pixel
SS = 3 # super sample factor
RING_COLOR = "red"

IDLE_SHEET = "assets/char animation/Sprites/Idle.png"
SKY_DIR = "assets/coud_bg/Clouds/Clouds 5"
FRAME_SIZE = 250

SEG_SPAN = math.radians(50)   # starting angular width
SEG_LIFETIME = 3.0            # seconds to shrink away
SEG_COUNT = 3


def spawn_seg():
    return Seg(
        span0=SEG_SPAN,
        lifetime=SEG_LIFETIME,
        omega=random.uniform(0.3, 0.8),
    )


def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    clock = pygame.time.Clock()
    running = True

    sky = load_layers(SKY_DIR, (W, H))
    idle_animation = Animation(load_frames(IDLE_SHEET, FRAME_SIZE, FRAME_SIZE), fps=8)
    ring = RingCanvas((CX, CY), in_rad, out_rad, ss=SS)
    segs = [spawn_seg() for _ in range(SEG_COUNT)]

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                for seg in segs:
                    if seg.hit(event.pos, (CX, CY), in_rad, out_rad):
                        seg.span = 0
                        break

        for layer in sky:
            screen.blit(layer, (0, 0))
        idle_animation.draw(screen, (W / 2, H / 2 - 30), 4)
        pygame.draw.circle(screen, RING_COLOR, (CX, CY), out_rad, 2)
        pygame.draw.circle(screen, RING_COLOR, (CX, CY), in_rad, 2)
        ring.draw(screen, segs, RING_COLOR)

        pygame.display.flip()

        dt = clock.tick(60) / 1000
        idle_animation.update(dt)
        for i, seg in enumerate(segs):
            seg.update(dt)
            if seg.dead:
                segs[i] = spawn_seg()

    pygame.quit()

if __name__ == "__main__":
    main()

