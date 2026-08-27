import math
import os

import pygame
import config as cfg
from utils.helpers import (
    load_frames, Animation, RingCanvas, SegField, Scoreboard, HitBar, Parallax,
    Effects, CrystalRing, CrystalStyle, GlossStyle, OneShot, ReportCard,
    PixelText, HealthBar, GradePanel,
)
from utils.syllabus import Syllabus, WEIGHTS
from scenes.menu import TitleScreen, EnrollTransition

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
MISS_SOUND = "assets/sounds/missed-note.mp3"
BACKGROUND_MUSIC = "assets/music/NewGenesisCut2.flac"
SPLASH_SHEET = "assets/images/blood-splash.png"
# monogram is a true pixel font: it is cut for 16px and only stays crisp at
# integer multiples of that, so every size below is 16 * n.
FONT_PATH = "assets/fonts/monogram/ttf/monogram-extended.ttf"
FONT_UNIT = 16                  # the font's native pixel size
SPLASH_FRAME = 96
FRAME_SIZE = 250

SEMESTER_SECONDS = 80           # one full run
SEG_SPAN = math.radians(40)     # starting angular width
SEG_LIFETIME = 4.2              # must outlast one bar lap, or it is uncatchable
SEG_SPAWN_RANGE = (0.30, 1.30)  # safety rails only; pacing picks the interval
RUSH_AFTER = 50.0               # seconds, then blocks start coming faster
RUSH_FACTOR = 0.62              # interval multiplier by the final whistle
MAX_SEGS = 7
# outer edge of everything the ring can draw: the band, its beat swell and
# the hit bar's overhang. Labels are placed wholly outside this.
RING_EDGE = out_rad + BEAT_AMPLITUDE + 10
LABEL_GAP = 8               # px of air between the ring edge and a name
LABEL_COLOR = (255, 214, 102)   # warm gold: reads against the forest, and is
                                # not either of the seg colours
LABEL_OUTLINE = (12, 14, 10)    # near-black, for the brightly lit bg patches

BAR_OMEGA0 = 2.6                # radians/sec at the start (lap 2.4s)
BAR_OMEGA_MAX = 5.0             # radians/sec once fully ramped
BAR_RAMP = SEMESTER_SECONDS     # fully ramped by the final whistle
BAR_BOOST_AFTER = 0.0           # the bar speeds up from the first second
BAR_BOOST_RATE = 0.05           # rad/s added per second, linear all run
BAR_COLOR = (255, 246, 214)   # warm cream, reads against the trees
SPLASH_FPS = 22
SPLASH_SCALE = 1.2

MAX_HEALTH = 10                 # mis-presses tolerated
TITLE_SECONDS = 10              # landing page auto-starts after this
TITLE_TOP = 108
TITLE_X = 390                   # text block sits left of the character
TITLE_CHAR_POS = (840, 360)
TITLE_CHAR_SCALE = 3.6
REPORT_X = 70                   # report panel sits left...
REPORT_TOP = 120
END_CHAR_POS = (W - 265, H // 2 - 95)   # ...character to its right
END_CHAR_SCALE = 4.0


def main():
    pygame.init()
    pygame.mixer.init()
    if os.path.exists(BACKGROUND_MUSIC):
        pygame.mixer.music.load(BACKGROUND_MUSIC)
        pygame.mixer.music.set_volume(0.35)
        pygame.mixer.music.play(-1)
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

    label_font = pygame.font.Font(FONT_PATH, FONT_UNIT * 2)
    tiny = pygame.font.Font(FONT_PATH, FONT_UNIT)   # PixelText scales this up
    hud_text = PixelText(tiny, scale=2)
    big_text = PixelText(tiny, scale=3)
    small_text = PixelText(tiny, scale=2)

    hit_sound = pygame.mixer.Sound(HIT_SOUND)
    miss_sound = pygame.mixer.Sound(MISS_SOUND)
    splash_frames = load_frames(SPLASH_SHEET, SPLASH_FRAME, SPLASH_FRAME)
    grades = GradePanel(hud_text, WEIGHTS)
    report_card = ReportCard(big_text, hud_text, small_text, TEXT_COLOR)
    title_screen = TitleScreen(PixelText(tiny, scale=4), small_text, hud_text,
                               TEXT_COLOR, RING_COLOR)
    enroll_text = PixelText(tiny, scale=4)

    def new_run():
        syllabus = Syllabus()
        return {
            "syllabus": syllabus,
            "field": SegField(SEG_SPAN, SEG_LIFETIME, spawn_range=SEG_SPAWN_RANGE,
                              max_segs=MAX_SEGS, queue=syllabus.build_queue()),
            "bar": HitBar(BAR_OMEGA0, BAR_OMEGA_MAX, BAR_RAMP,
                          boost_after=BAR_BOOST_AFTER,
                          boost_rate=BAR_BOOST_RATE),
            "health": HealthBar(hud_text, MAX_HEALTH),
            "effects": Effects(),
            "clock": 0.0,
            "phase": "title",    # title -> enroll -> play -> dying -> report
            "title_clock": 0.0,
            "transition": None,
            "dead": False,
            "ending": None,      # the character animation shown at the end
        }

    run = new_run()

    def finish(dead):
        """Leave play. Death plays out in full before the report appears."""
        run["dead"] = dead
        show_death = dead or run["syllabus"].failing()
        if show_death:
            run["phase"] = "dying"
            run["ending"] = OneShot(death_frames, END_CHAR_POS, fps=9,
                                    scale=END_CHAR_SCALE, hold=True)
        else:
            # passed: the idle pose stands beside the report instead
            run["phase"] = "report"
            run["ending"] = None

    while running:
        field, bar, health = run["field"], run["bar"], run["health"]
        playing = run["phase"] == "play"
        on_title = run["phase"] == "title"
        time_left = max(0.0, SEMESTER_SECONDS - run["clock"])
        spawn_left = max(0.0, SEMESTER_SECONDS - SEG_LIFETIME - run["clock"])
        rush = 1.0
        if run["clock"] > RUSH_AFTER:
            ramp = (run["clock"] - RUSH_AFTER) / max(SEMESTER_SECONDS - RUSH_AFTER, 1e-6)
            rush = 1.0 - (1.0 - RUSH_FACTOR) * min(1.0, ramp)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                run = new_run()
            elif playing and (
                    event.type == pygame.MOUSEBUTTONDOWN
                    or (event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE)):
                caught = field.pop_under(bar.angle)
                if caught:
                    run["syllabus"].record(*caught.meta)
                    health.heal()
                    hit_sound.play()
                    run["effects"].spawn(splash_frames,
                                         caught.label_pos((CX, CY), (in_rad + out_rad) / 2),
                                         fps=SPLASH_FPS, scale=SPLASH_SCALE)
                else:
                    # pressing with nothing under the bar is what costs you
                    miss_sound.play()
                    if health.damage():
                        finish(dead=True)

        background.draw(screen)
        if run["phase"] in ("play", "enroll"):
            idle_animation.draw(screen, (W / 2, H / 2 - 30), 4)
        crystal.draw(screen)
        if playing:
            ring.draw(screen, field.segs, SEG_FRESH, SEG_DYING, BEAT_AMPLITUDE,
                      bar=bar, bar_color=BAR_COLOR, style=seg_style)
            field.draw_labels(screen, label_font, (CX, CY), RING_EDGE, LABEL_COLOR,
                              gap=LABEL_GAP, outline=LABEL_OUTLINE)
        run["effects"].draw(screen)

        if on_title:
            title_screen.draw(screen, TITLE_X, TITLE_TOP,
                              TITLE_SECONDS - run["title_clock"], TITLE_SECONDS)
            # after the veil, so the character reads at full brightness
            idle_animation.draw(screen, TITLE_CHAR_POS, TITLE_CHAR_SCALE)
        if run["transition"] is not None:
            run["transition"].draw(screen, (CX, CY - 40))
        if run["phase"] == "report":
            report_card.draw(screen, run["syllabus"], REPORT_X, REPORT_TOP,
                             dead=run["dead"])
        if run["ending"] is not None:
            run["ending"].draw(screen)
        elif run["phase"] == "report":
            idle_animation.draw(screen, END_CHAR_POS, END_CHAR_SCALE)
        if playing:
            grades.draw(screen, run["syllabus"])
            health.draw(screen, CX, H - 62)
            draw_clock(screen, hud_text, time_left, len(field.queue or ()))

        pygame.display.flip()

        dt = clock.tick(60) / 1000
        background.update(dt)
        run["effects"].update(dt)
        health.update(dt)

        idle_animation.update(dt)
        title_screen.update(dt)

        if on_title:
            run["title_clock"] += dt
            if run["title_clock"] >= TITLE_SECONDS:
                run["phase"] = "enroll"
                run["transition"] = EnrollTransition(enroll_text, TEXT_COLOR)
            continue
        if run["phase"] == "enroll":
            run["transition"].update(dt)
            if run["transition"].done:
                run["transition"] = None
                run["phase"] = "play"
            continue
        if run["phase"] == "dying":
            run["ending"].update(dt)
            # let the animation land before the numbers go up
            if run["ending"].index >= len(death_frames) + 8:
                run["phase"] = "report"
            continue
        if run["phase"] == "report":
            continue

        run["clock"] += dt
        bar.update(dt)
        for seg in field.update(dt, spawn_left, rush):
            run["syllabus"].expire(*seg.meta)

        if run["clock"] >= SEMESTER_SECONDS or (not field.queue and not field.segs):
            finish(dead=False)

    pygame.quit()


def draw_clock(surface, text, time_left, blocks_left):
    """Countdown and remaining blocks, top right."""
    urgent = (236, 92, 92) if time_left <= 10 else TEXT_COLOR
    text.draw(surface, f"{time_left:5.1f}S", urgent, topright=(W - 18, 18))
    text.draw(surface, f"{blocks_left} LEFT", TEXT_COLOR, topright=(W - 18, 46))


if __name__ == "__main__":
    main()
