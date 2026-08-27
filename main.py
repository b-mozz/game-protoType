import math

import pygame
import config as cfg
from utils.helpers import (
    load_frames, Animation, RingCanvas, SegField, Scoreboard, HitBar, Parallax,
    Effects, CrystalRing, CrystalStyle, GlossStyle, OneShot, ReportCard,
)
from utils.syllabus import Syllabus

W, H = cfg.WIDTH, cfg.HEIGHT # game width and height
out_rad, in_rad = 180, 150
CX, CY = W // 2, H // 2 # center of the ring, in pixel
SS = 3 # super sample factor
RING_COLOR = (255, 96, 96)    # crystal base tint; facets shade off this
RING_FACETS = 14              # fewer, longer cuts read as facets
RING_JITTER = 0.07            # how chipped the cut edges look
RING_OUTLINE = 2              # px width of the facet seams
RING_SPOKES = True            # radial seams between the two edges
SEG_ALPHA = 235               # segs are the target, so they stay solid
SEG_BANDS = 24                # sub-bands shading across the thickness
SEG_CURVE = 0.55              # how rounded the band reads
SEG_RIM = 2                   # px bright rim on the outer edge
RING_ALPHA = 90               # 0-255, the translucent material in the band
RING_EDGE_ALPHA = 200         # 0-255, the facet seams drawn over it
TEXT_COLOR = (232, 238, 230)  # light: the forest bg is very dark
SEG_FRESH = (152, 221, 160)   # pastel green, just popped
SEG_DYING = (240, 141, 141)   # pastel red, about to vanish
BEAT_AMPLITUDE = 6           # px the ring swells at peak beat
BG_SCROLL = 26               # px/sec drift of the nearest parallax layer

IDLE_SHEET = "assets/char animation/Sprites/Idle.png"
DEATH_SHEET = "assets/char animation/Sprites/Death.png"
BG_DIR = "assets/forest bg/PNG/Background layers"
HIT_SOUND = "assets/sounds/hit-note.mp3"
SPLASH_SHEET = "assets/images/blood-splash.png"
SPLASH_FRAME = 96
FRAME_SIZE = 250

SEMESTER_SECONDS = 80           # one full run
SEG_SPAN = math.radians(40)     # starting angular width
SEG_LIFETIME = 4.2              # must outlast one bar lap, or it is uncatchable
SEG_SPAWN_RANGE = (0.35, 1.4)   # clamp on the paced spawn interval
MAX_SEGS = 7
LABEL_RADIUS = out_rad + 26

BAR_OMEGA0 = 2.6                # radians/sec at the start (lap 2.4s)
BAR_OMEGA_MAX = 5.0             # radians/sec once fully ramped
BAR_RAMP = SEMESTER_SECONDS     # fully ramped by the final whistle
BAR_COLOR = (255, 246, 214)   # warm cream, reads against the trees
SPLASH_FPS = 22
SPLASH_SCALE = 1.2


def main():
    pygame.init()
    pygame.mixer.init()
    screen = pygame.display.set_mode((W, H))
    clock = pygame.time.Clock()
    running = True

    background = Parallax(BG_DIR, (W, H), max_speed=BG_SCROLL)
    idle_frames = load_frames(IDLE_SHEET, FRAME_SIZE, FRAME_SIZE)
    death_frames = load_frames(DEATH_SHEET, FRAME_SIZE, FRAME_SIZE)
    idle_animation = Animation(idle_frames, fps=8)
    ring = RingCanvas((CX, CY), in_rad, out_rad, ss=SS)
    ring_style = CrystalStyle(facets=RING_FACETS, jitter=RING_JITTER,
                              alpha=RING_ALPHA, edge_alpha=RING_EDGE_ALPHA,
                              outline=RING_OUTLINE, spokes=RING_SPOKES)
    seg_style = GlossStyle(alpha=SEG_ALPHA, bands=SEG_BANDS,
                           curve=SEG_CURVE, rim=SEG_RIM)
    crystal = CrystalRing((CX, CY), in_rad, out_rad, RING_COLOR, ring_style, ss=SS)

    label_font = pygame.font.SysFont("menlo", 15, bold=True)
    score_font = pygame.font.SysFont("menlo", 20, bold=True)
    title_font = pygame.font.SysFont("menlo", 30, bold=True)
    hit_sound = pygame.mixer.Sound(HIT_SOUND)
    splash_frames = load_frames(SPLASH_SHEET, SPLASH_FRAME, SPLASH_FRAME)
    report_card = ReportCard(title_font, score_font, label_font, TEXT_COLOR)

    def new_run():
        syllabus = Syllabus()
        return {
            "syllabus": syllabus,
            "field": SegField(SEG_SPAN, SEG_LIFETIME, spawn_range=SEG_SPAWN_RANGE,
                              max_segs=MAX_SEGS, queue=syllabus.build_queue()),
            "bar": HitBar(BAR_OMEGA0, BAR_OMEGA_MAX, BAR_RAMP),
            "scoreboard": Scoreboard(score_font, TEXT_COLOR),
            "effects": Effects(),
            "clock": 0.0,
            "over": False,
            "death": None,
        }

    run = new_run()

    while running:
        field, bar = run["field"], run["bar"]
        time_left = max(0.0, SEMESTER_SECONDS - run["clock"])
        # last block must land with time left to catch it
        spawn_left = max(0.0, SEMESTER_SECONDS - SEG_LIFETIME - run["clock"])

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                run = new_run()
            elif not run["over"] and (
                    event.type == pygame.MOUSEBUTTONDOWN
                    or (event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE)):
                caught = field.pop_under(bar.angle)
                if caught:
                    run["scoreboard"].hit(caught)
                    run["syllabus"].record(*caught.meta)
                    hit_sound.play()
                    run["effects"].spawn(splash_frames,
                                         caught.label_pos((CX, CY), (in_rad + out_rad) / 2),
                                         fps=SPLASH_FPS, scale=SPLASH_SCALE)

        background.draw(screen)
        if run["death"] is not None:
            run["death"].draw(screen)
        else:
            idle_animation.draw(screen, (W / 2, H / 2 - 30), 4)
        crystal.draw(screen)
        if not run["over"]:
            ring.draw(screen, field.segs, SEG_FRESH, SEG_DYING, BEAT_AMPLITUDE,
                      bar=bar, bar_color=BAR_COLOR, style=seg_style)
            field.draw_labels(screen, label_font, (CX, CY), LABEL_RADIUS, TEXT_COLOR)
        run["effects"].draw(screen)
        run["scoreboard"].draw(screen)
        draw_clock(screen, score_font, time_left, len(field.queue or ()))

        if run["over"]:
            report_card.draw(screen, run["syllabus"], (CX, CY))

        pygame.display.flip()

        dt = clock.tick(60) / 1000
        background.update(dt)
        run["effects"].update(dt)

        if run["over"]:
            if run["death"] is not None:
                run["death"].update(dt)
            continue

        run["clock"] += dt
        idle_animation.update(dt)
        bar.update(dt)
        run["scoreboard"].miss(len(field.update(dt, spawn_left)))

        # the semester ends on the clock, or once every block has been resolved
        if run["clock"] >= SEMESTER_SECONDS or (not field.queue and not field.segs):
            run["over"] = True
            if run["syllabus"].failing():
                run["death"] = OneShot(death_frames, (W / 2, H / 2 - 30),
                                       fps=9, scale=4, hold=True)

    pygame.quit()


def draw_clock(surface, font, time_left, blocks_left):
    """Countdown and remaining blocks, top right."""
    for i, line in enumerate((f"{time_left:5.1f}s", f"{blocks_left} left")):
        text = font.render(line, True, TEXT_COLOR)
        surface.blit(text, text.get_rect(topright=(W - 16, 12 + i * 28)))


if __name__ == "__main__":
    main()
