import math

import pygame
import config as cfg
from utils.helpers import (
    load_frames, load_layers, Animation, RingCanvas, SegField, Scoreboard, HitBar,
)

W, H = cfg.WIDTH, cfg.HEIGHT # game width and height
out_rad, in_rad = 180, 150
CX, CY = W // 2, H // 2 # center of the ring, in pixel
SS = 3 # super sample factor
RING_COLOR = "red"
TEXT_COLOR = (30, 40, 70)
SEG_FRESH = (152, 221, 160)   # pastel green, just popped
SEG_DYING = (240, 141, 141)   # pastel red, about to vanish
BEAT_AMPLITUDE = 6           # px the ring swells at peak beat

IDLE_SHEET = "assets/char animation/Sprites/Idle.png"
SKY_DIR = "assets/coud_bg/Clouds/Clouds 5"
HIT_SOUND = "assets/sounds/hit-note.mp3"
FRAME_SIZE = 250

SEG_SPAN = math.radians(40)     # starting angular width
SEG_LIFETIME = 5.0              # seconds to shrink away
SEG_SPAWN_RANGE = (0.4, 1.4)    # seconds between popups
MAX_SEGS = 5
LABEL_RADIUS = out_rad + 26

BAR_OMEGA0 = 1.6                # radians/sec at the start
BAR_OMEGA_MAX = 5.0             # radians/sec once fully ramped
BAR_RAMP = 45.0                 # seconds to reach full speed
BAR_COLOR = (30, 40, 70)


def main():
    pygame.init()
    pygame.mixer.init()
    screen = pygame.display.set_mode((W, H))
    clock = pygame.time.Clock()
    running = True

    sky = load_layers(SKY_DIR, (W, H))
    idle_animation = Animation(load_frames(IDLE_SHEET, FRAME_SIZE, FRAME_SIZE), fps=8)
    ring = RingCanvas((CX, CY), in_rad, out_rad, ss=SS)
    field = SegField(SEG_SPAN, SEG_LIFETIME,
                     spawn_range=SEG_SPAWN_RANGE, max_segs=MAX_SEGS)
    bar = HitBar(BAR_OMEGA0, BAR_OMEGA_MAX, BAR_RAMP)

    label_font = pygame.font.SysFont("menlo", 16, bold=True)
    score_font = pygame.font.SysFont("menlo", 20, bold=True)
    scoreboard = Scoreboard(score_font, TEXT_COLOR)
    hit_sound = pygame.mixer.Sound(HIT_SOUND)

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif (event.type == pygame.MOUSEBUTTONDOWN 
                  or (event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE)):
                caught = field.pop_under(bar.angle)
                if caught:
                    scoreboard.hit(caught)
                    hit_sound.play()

        for layer in sky:
            screen.blit(layer, (0, 0))
        idle_animation.draw(screen, (W / 2, H / 2 - 30), 4)
        pygame.draw.circle(screen, RING_COLOR, (CX, CY), out_rad, 2)
        pygame.draw.circle(screen, RING_COLOR, (CX, CY), in_rad, 2)
        ring.draw(screen, field.segs, SEG_FRESH, SEG_DYING, BEAT_AMPLITUDE,
                  bar=bar, bar_color=BAR_COLOR)
        field.draw_labels(screen, label_font, (CX, CY), LABEL_RADIUS, TEXT_COLOR)
        scoreboard.draw(screen)

        pygame.display.flip()

        dt = clock.tick(60) / 1000
        idle_animation.update(dt)
        bar.update(dt)
        scoreboard.miss(len(field.update(dt)))

    pygame.quit()

if __name__ == "__main__":
    main()
