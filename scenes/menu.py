"""Title screen: the name, what the game is, and how to play it."""
import math

import pygame

TITLE = "PASS IF YOU CAN"
TAGLINE = "Finish the assignments before they are due"

HOW_TO = (
    "The more you miss the lower your grade",
    "3 classes: english, CS and Math",
    "If you fail one you fail the semester",
)

COUNTDOWN = "ENROLLING IN"


class TitleScreen:
    """Draws the landing screen over whatever background is passed in."""

    def __init__(self, title_text, body_text, prompt_text,
                 color=(232, 238, 230), accent=(255, 96, 96),
                 muted=(168, 178, 196)):
        self.title = title_text
        self.body = body_text
        self.prompt = prompt_text
        self.color = color
        self.accent = accent
        self.muted = muted
        self.clock = 0.0

    def update(self, dt):
        self.clock += dt

    def draw(self, surface, center_x, top, seconds_left, total, dim=195):
        veil = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        veil.fill((6, 8, 14, dim))
        surface.blit(veil, (0, 0))

        y = top
        self.title.draw(surface, TITLE, self.color, midtop=(center_x, y))
        y += 62

        rule = 240
        pygame.draw.line(surface, self.accent,
                         (center_x - rule, y), (center_x + rule, y), 2)
        y += 20

        self.body.draw(surface, TAGLINE, self.accent, midtop=(center_x, y))
        y += 46

        for line in HOW_TO:
            self.body.draw(surface, line, self.muted, midtop=(center_x, y))
            y += 26

        y += 36
        seconds = max(0, math.ceil(seconds_left))
        # the last few tick red, so the start does not surprise anyone
        tint = self.accent if seconds <= 3 else self.color
        self.prompt.draw(surface, f"{COUNTDOWN} {seconds}", tint,
                         midtop=(center_x, y))

        y += 30
        track = pygame.Rect(center_x - 120, y, 240, 8)
        pygame.draw.rect(surface, (26, 30, 40), track)
        left = max(0.0, min(1.0, seconds_left / max(total, 1e-6)))
        pygame.draw.rect(surface, tint,
                         pygame.Rect(track.x, track.y, track.w * left, track.h))
        pygame.draw.rect(surface, (90, 98, 115), track, 1)


class EnrollTransition:
    """
    The hand-off from title to play: the line punches in, holds, then both it
    and the veil fade out to reveal the ring underneath.
    """

    TEXT = "YOU ARE ENROLLED"
    POP = 0.30        # seconds spent scaling in
    HOLD = 0.85       # seconds fully visible
    FADE = 0.65       # seconds fading away

    def __init__(self, text_renderer, color=(232, 238, 230), veil_alpha=215):
        self.image = text_renderer.render(self.TEXT, color).copy()
        self.veil_alpha = veil_alpha
        self.clock = 0.0

    @property
    def duration(self):
        return self.POP + self.HOLD + self.FADE

    @property
    def done(self):
        return self.clock >= self.duration

    def update(self, dt):
        self.clock += dt

    def draw(self, surface, center):
        t = self.clock

        if t < self.POP:
            # overshoot slightly past full size, then settle -- gives it a snap
            u = t / self.POP
            scale = 0.55 + 0.45 * u + 0.16 * math.sin(u * math.pi)
            alpha, veil = 255 * u, self.veil_alpha
        elif t < self.POP + self.HOLD:
            scale, alpha, veil = 1.0, 255, self.veil_alpha
        else:
            u = min(1.0, (t - self.POP - self.HOLD) / self.FADE)
            scale = 1.0 + 0.25 * u          # drifts open as it leaves
            alpha, veil = 255 * (1 - u), self.veil_alpha * (1 - u)

        if veil > 0:
            layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            layer.fill((6, 8, 14, int(veil)))
            surface.blit(layer, (0, 0))

        image = self.image
        if scale != 1.0:
            image = pygame.transform.scale(
                image, (max(1, int(image.get_width() * scale)),
                        max(1, int(image.get_height() * scale))))
        else:
            image = image.copy()
        image.set_alpha(int(alpha))
        surface.blit(image, image.get_rect(center=center))
