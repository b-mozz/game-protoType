import colorsys
import os
import re
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


def _layer_index(name):
    """First integer in a filename, for natural sorting ('1.png', 'Layer_0003_6.png')."""
    match = re.search(r"\d+", name)
    return int(match.group()) if match else 0


def load_layers(folder, size=None, reverse=False):
    """
    Load a numbered set of background layers in back-to-front order.

    PSD exports number layers from the top of the stack down, so their far
    layers come last -- pass reverse=True for those. Pass size to stretch each
    layer, or leave it None to keep the source resolution.
    """
    names = sorted((f for f in os.listdir(folder) if f.endswith(".png")),
                   key=_layer_index, reverse=reverse)
    layers = []
    for name in names:
        image = pygame.image.load(os.path.join(folder, name)).convert_alpha()
        layers.append(pygame.transform.scale(image, size) if size else image)
    return layers


class Parallax:
    """
    Scrolling layered background. Each layer drifts at its own speed -- far
    layers barely move, near ones slide past -- and layers whose filename says
    "Lights" breathe in and out instead of scrolling.
    """

    def __init__(self, folder, size, max_speed=26, reverse=True,
                 light_hz=0.18, light_alpha=(90, 255)):
        self.width, self.height = size
        names = sorted((f for f in os.listdir(folder) if f.endswith(".png")),
                       key=_layer_index, reverse=reverse)

        self.layers = []
        count = max(1, len(names) - 1)
        for i, name in enumerate(names):
            image = pygame.image.load(os.path.join(folder, name)).convert_alpha()
            # scale to height, keep aspect, so the tile seam stays clean
            tile_w = max(1, round(image.get_width() * self.height / image.get_height()))
            image = pygame.transform.scale(image, (tile_w, self.height))
            self.layers.append({
                "image": image,
                "tile_w": tile_w,
                # depth curve: back layers creep, front layers slide
                "speed": max_speed * (i / count) ** 1.6,
                "light": "light" in name.lower(),
                "offset": 0.0,
            })

        self.light_hz = light_hz
        self.light_alpha = light_alpha
        self.clock = 0.0

    def update(self, dt):
        self.clock += dt
        for layer in self.layers:
            if layer["light"]:
                continue
            layer["offset"] = (layer["offset"] + layer["speed"] * dt) % layer["tile_w"]

    def draw(self, surface):
        lo, hi = self.light_alpha
        glow = lo + (hi - lo) * (0.5 + 0.5 * math.sin(math.tau * self.light_hz * self.clock))

        for layer in self.layers:
            image = layer["image"]
            if layer["light"]:
                image.set_alpha(int(glow))
            x = -layer["offset"]
            while x < self.width:
                surface.blit(image, (x, 0))
                x += layer["tile_w"]

def lerp_color(c0, c1, t):
    """
    Blend two colours through HSV, t in 0..1. Interpolating hue rather than raw
    RGB keeps saturation up across the middle -- a straight RGB green-to-red
    lerp dips through a muddy khaki halfway.
    """
    t = max(0.0, min(1.0, t))
    h0, s0, v0 = colorsys.rgb_to_hsv(*(x / 255 for x in c0[:3]))
    h1, s1, v1 = colorsys.rgb_to_hsv(*(x / 255 for x in c1[:3]))
    dh = (h1 - h0 + 0.5) % 1.0 - 0.5          # take the short way round the wheel
    h = (h0 + dh * t) % 1.0
    rgb = colorsys.hsv_to_rgb(h, s0 + (s1 - s0) * t, v0 + (v1 - v0) * t)
    return tuple(round(x * 255) for x in rgb)


def ang_delta(a, b):
    """Signed shortest angular distance from b to a, in [-pi, pi]."""
    return (a - b + math.pi) % math.tau - math.pi


BEAT_START = 0.5        # fraction of life left when the beating begins
BEAT_HZ = (2.0, 5.5)    # beats/sec, at the start and end of the beating phase


class Seg:
    '''
    ring segmentations, shrinks with time. clicking the vanishing seg gives point, it also has angular velocity, so while shrinking,
    also travels along the ring path
    '''

    def __init__(self, span0, lifetime, omega=0.0, angle=None, name=""):
        self.angle = random.uniform(0, math.tau) if angle is None else angle
        self.span0 = span0        # starting angular width, radians
        self.span = span0
        self.lifetime = lifetime  # seconds to shrink from span0 to nothing
        self.omega = omega        # radians/sec; 0 keeps the seg parked
        self.name = name
        self.phase = 0.0          # beat phase, only advances once beating

    @property
    def life_left(self):
        """1.0 at spawn, 0.0 when it vanishes."""
        return max(0.0, self.span / self.span0)

    def label_pos(self, center, radius):
        """Where to draw this seg's name, just outside the ring."""
        return (center[0] + radius * math.cos(self.angle),
                center[1] + radius * math.sin(self.angle))

    def update(self, dt):
        self.angle = (self.angle + self.omega * dt) % math.tau
        self.span -= (self.span0 / self.lifetime) * dt
        if self.beating:
            f0, f1 = BEAT_HZ
            self.phase += math.tau * (f0 + (f1 - f0) * self.urgency) * dt

    @property
    def beating(self):
        """True once the seg is past the halfway point of its life."""
        return self.life_left <= BEAT_START

    @property
    def urgency(self):
        """0.0 the moment beating starts, 1.0 as it vanishes."""
        if not self.beating:
            return 0.0
        return min(1.0, 1 - self.life_left / BEAT_START)

    def color(self, c_start, c_end):
        """Fades from c_start at spawn to c_end as it shrinks."""
        return lerp_color(c_start, c_end, 1 - self.life_left)

    def radii(self, r_in, r_out, amplitude):
        """Ring thickness for this frame, swollen by the beat."""
        if not self.beating:
            return r_in, r_out
        swell = amplitude * self.urgency * (0.5 + 0.5 * math.sin(self.phase))
        mid, half = (r_in + r_out) / 2, (r_out - r_in) / 2
        return mid - half - swell, mid + half + swell

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

SEG_NAMES = ("homework", "project", "midterm", "finals", "lab", "assignment")


class SegField:
    """
    Pops segs onto the ring at random intervals. Segs are parked -- only their
    span shrinks -- so an angle that is free at spawn stays free for the seg's
    whole life. The sweeping hit bar is what moves.
    """

    def __init__(self, span0, lifetime, spawn_range=(0.4, 1.4),
                 max_segs=5, gap=math.radians(6), names=SEG_NAMES):
        self.span0 = span0
        self.lifetime = lifetime
        self.spawn_range = spawn_range
        self.max_segs = max_segs
        self.gap = gap
        self.names = names
        self.segs = []
        self.timer = random.uniform(*spawn_range)

    def free_angle(self, tries=24):
        """A random angle whose seg would not overlap any live seg, or None."""
        for _ in range(tries):
            angle = random.uniform(0, math.tau)
            # compare against span0: spans only shrink, so this is the worst case
            if all(abs(ang_delta(angle, s.angle)) > (self.span0 + s.span0) / 2 + self.gap
                   for s in self.segs):
                return angle
        return None

    def spawn(self):
        if len(self.segs) >= self.max_segs:
            return None
        angle = self.free_angle()
        if angle is None:
            return None

        taken = {s.name for s in self.segs}
        pool = [n for n in self.names if n not in taken] or list(self.names)
        seg = Seg(self.span0, self.lifetime, angle=angle, name=random.choice(pool))
        self.segs.append(seg)
        return seg

    def update(self, dt):
        """Advance every seg. Returns the segs that expired uncaught this frame."""
        self.timer -= dt
        if self.timer <= 0:
            self.spawn()
            self.timer = random.uniform(*self.spawn_range)

        for seg in self.segs:
            seg.update(dt)

        expired = [s for s in self.segs if s.dead]
        self.segs = [s for s in self.segs if not s.dead]
        return expired

    def pop_under(self, angle):
        """Remove and return the seg covering the given angle, or None."""
        for seg in self.segs:
            if seg.contains(angle):
                self.segs.remove(seg)
                return seg
        return None

    def pop_at(self, pos, center, r_in, r_out):
        """Remove and return the seg under pos, or None."""
        for seg in self.segs:
            if seg.hit(pos, center, r_in, r_out):
                self.segs.remove(seg)
                return seg
        return None

    def draw_labels(self, surface, font, center, radius, color):
        for seg in self.segs:
            text = font.render(seg.name, True, color)
            surface.blit(text, text.get_rect(center=seg.label_pos(center, radius)))


class HitBar:
    """
    A marker sweeping around the ring. Its angular speed ramps from omega0
    toward omega_max over `ramp` seconds, so the game tightens as it runs.
    """

    def __init__(self, omega0, omega_max, ramp, angle=0.0, width=7):
        self.omega0 = omega0
        self.omega_max = omega_max
        self.ramp = ramp          # seconds to reach full speed
        self.angle = angle
        self.width = width        # px, measured across the sweep
        self.elapsed = 0.0

    @property
    def omega(self):
        t = min(1.0, self.elapsed / self.ramp)
        return self.omega0 + 0.01 * t

    def update(self, dt):
        self.elapsed += dt
        self.angle = (self.angle + self.omega * dt) % math.tau

    def points(self, center, r_in, r_out):
        """Outline of the bar: a thin radial slab across the ring band."""
        half = (self.width / 2) / r_out      # px -> radians at the outer edge
        a0, a1 = self.angle - half, self.angle + half
        cx, cy = center
        return [
            (cx + r_out * math.cos(a0), cy + r_out * math.sin(a0)),
            (cx + r_out * math.cos(a1), cy + r_out * math.sin(a1)),
            (cx + r_in * math.cos(a1), cy + r_in * math.sin(a1)),
            (cx + r_in * math.cos(a0), cy + r_in * math.sin(a0)),
        ]


class RingCanvas:
    """Draws ring segments on a supersampled surface, then downscales for smooth edges."""

    def __init__(self, center, r_in, r_out, ss=3, pad=12):  # must clear the beat swell and bar overhang
        self.r_in, self.r_out, self.ss = r_in, r_out, ss
        self.size = 2 * (r_out + pad)
        self.big = pygame.Surface((self.size * ss, self.size * ss), pygame.SRCALPHA)
        self.local = (self.size * ss / 2, self.size * ss / 2)
        self.topleft = (center[0] - self.size / 2, center[1] - self.size / 2)

    def draw(self, surface, segs, c_start, c_end, beat_amplitude=6,
             bar=None, bar_color=(30, 40, 70), bar_overhang=10):
        self.big.fill((0, 0, 0, 0))
        for seg in segs:
            if seg.dead:
                continue
            r_in, r_out = seg.radii(self.r_in, self.r_out, beat_amplitude)
            pts = seg.points(self.local, r_in * self.ss, r_out * self.ss)
            pygame.draw.polygon(self.big, seg.color(c_start, c_end), pts)

        if bar is not None:
            # overhang so the bar reads as a needle crossing the band
            pygame.draw.polygon(self.big, bar_color, bar.points(
                self.local,
                (self.r_in - bar_overhang) * self.ss,
                (self.r_out + bar_overhang) * self.ss,
            ))
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


class Scoreboard:
    """Score and miss tally, drawn in a corner."""

    def __init__(self, font, color, pos=(16, 12), line_height=28):
        self.font = font
        self.color = color
        self.pos = pos
        self.line_height = line_height
        self.score = 0
        self.hits = 0
        self.missed = 0

    def hit(self, seg):
        """Score a caught seg -- the smaller it had shrunk, the more it is worth."""
        points = 1 + int(round(9 * (1 - seg.life_left)))
        self.score += points
        self.hits += 1
        return points

    def miss(self, count=1):
        self.missed += count

    def draw(self, surface):
        x, y = self.pos
        for i, line in enumerate((f"score {self.score}",
                                  f"caught {self.hits}",
                                  f"missed {self.missed}")):
            text = self.font.render(line, True, self.color)
            surface.blit(text, (x, y + i * self.line_height))
