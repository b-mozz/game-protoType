import os
import pygame
import math
import random


def load_frames(path, frame_width, frame_height=None, scale=1):
    """Slice a horizontal sprite sheet into a list of frames."""
    sheet = pygame.image.load(path).convert_alpha()
    frame_height = frame_height or sheet.get_height()
    count = sheet.get_width() // frame_width

    frames = []
    for i in range(count):
        rect = pygame.Rect(i * frame_width, 0, frame_width, frame_height)
        frame = sheet.subsurface(rect)
        if scale != 1:
            size = (int(frame_width * scale), int(frame_height * scale))
            frame = pygame.transform.scale(frame, size)
        frames.append(frame)
    return frames


def load_layers(folder, size):
    """Load a numbered set of background layers, back to front, scaled to size."""
    names = sorted(
        (f for f in os.listdir(folder) if f.endswith(".png")),
        key=lambda f: int(os.path.splitext(f)[0]),
    )
    layers = []
    for name in names:
        image = pygame.image.load(os.path.join(folder, name)).convert_alpha()
        layers.append(pygame.transform.scale(image, size))
    return layers

def ang_delta(a, b):
    """Signed shortest angular distance from b to a, in [-pi, pi]."""
    return (a - b + math.pi) % math.tau - math.pi


class Seg:
    '''
    ring segmentations, shrinks with time. clicking the vanishing seg gives point, it also has angular velocity, so while shrinking,
    also travels along the ring path
    '''

    def __init__(self, span0, lifetime, omega, angle=None):
        self.angle = random.uniform(0, math.tau) if angle is None else angle
        self.span0 = span0        # starting angular width, radians
        self.span = span0
        self.lifetime = lifetime  # seconds to shrink from span0 to nothing
        self.omega = omega        # angular velocity, radians/sec

    def update(self, dt):
        self.angle = (self.angle + self.omega * dt) % math.tau
        self.span -= (self.span0 / self.lifetime) * dt

    @property
    def dead(self):
        return self.span <= 0

    def arc_length(self, radius):
        """Current width in pixels, at the given ring radius."""
        return self.span * radius

    def contains(self, angle):
        """Does this seg currently cover the given angle?"""
        return abs(ang_delta(angle, self.angle)) <= self.span / 2

    def points(self, center, r_in, r_out, steps=None):
        """Outline of this seg as an annulus sector: out edge forward, in edge back."""
        a0, a1 = self.angle - self.span / 2, self.angle + self.span / 2
        if steps is None:
            steps = max(2, int(self.span * r_out / 4))
        cx, cy = center

        pts = []
        for radius, order in ((r_out, range(steps + 1)), (r_in, range(steps, -1, -1))):
            for i in order:
                a = a0 + (a1 - a0) * i / steps
                pts.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))
        return pts

    def hit(self, pos, center, r_in, r_out):
        """Was a click at pos inside this seg?"""
        dx, dy = pos[0] - center[0], pos[1] - center[1]
        if not r_in <= math.hypot(dx, dy) <= r_out:
            return False
        return self.contains(math.atan2(dy, dx) % math.tau)

class RingCanvas:
    """Draws ring segments on a supersampled surface, then downscales for smooth edges."""

    def __init__(self, center, r_in, r_out, ss=3, pad=2):
        self.r_in, self.r_out, self.ss = r_in, r_out, ss
        self.size = 2 * (r_out + pad)
        self.big = pygame.Surface((self.size * ss, self.size * ss), pygame.SRCALPHA)
        self.local = (self.size * ss / 2, self.size * ss / 2)
        self.topleft = (center[0] - self.size / 2, center[1] - self.size / 2)

    def draw(self, surface, segs, color):
        self.big.fill((0, 0, 0, 0))
        for seg in segs:
            if seg.dead:
                continue
            pts = seg.points(self.local, self.r_in * self.ss, self.r_out * self.ss)
            pygame.draw.polygon(self.big, color, pts)
        surface.blit(pygame.transform.smoothscale(self.big, (self.size, self.size)), self.topleft)


class Animation:
    """Plays a list of frames at a fixed rate."""

    def __init__(self, frames, fps=10):
        self.frames = frames
        self.fps = fps
        self.timer = 0
        self.index = 0

    def update(self, dt):
        self.timer += dt
        step = 1 / self.fps
        while self.timer >= step:
            self.timer -= step
            self.index = (self.index + 1) % len(self.frames)

    @property
    def image(self):
        return self.frames[self.index]

    def draw(self, surface, center, scale=1):
        image = self.image
        if scale != 1:
            size = (int(image.get_width() * scale), int(image.get_height() * scale))
            image = pygame.transform.scale(image, size)
        surface.blit(image, image.get_rect(center=center))
