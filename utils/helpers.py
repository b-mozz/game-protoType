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

    def __init__(self, span0, lifetime, omega=0.0, angle=None, name="", meta=None):
        self.angle = random.uniform(0, math.tau) if angle is None else angle
        self.span0 = span0        # starting angular width, radians
        self.span = span0
        self.lifetime = lifetime  # seconds to shrink from span0 to nothing
        self.omega = omega        # radians/sec; 0 keeps the seg parked
        self.name = name
        self.meta = meta          # (course, section) this block belongs to
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
                 max_segs=5, gap=math.radians(6), names=SEG_NAMES, queue=None,
                 initial_delay=None):
        self.span0 = span0
        self.lifetime = lifetime
        self.spawn_range = spawn_range
        self.max_segs = max_segs
        self.gap = gap
        self.names = names
        self.queue = list(queue) if queue else None   # syllabus blocks to hand out
        self.segs = []
        self.timer = (random.uniform(*spawn_range)
                  if initial_delay is None else initial_delay)

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
        if self.queue is not None and not self.queue:
            return None
        angle = self.free_angle()
        if angle is None:
            # no room right now; the block stays queued for the next tick
            return None

        if self.queue is not None:
            course, section = self.queue.pop()
            seg = Seg(self.span0, self.lifetime, angle=angle,
                      name=f"{course} {section}", meta=(course, section))
        else:
            taken = {s.name for s in self.segs}
            pool = [n for n in self.names if n not in taken] or list(self.names)
            seg = Seg(self.span0, self.lifetime, angle=angle, name=random.choice(pool))
        self.segs.append(seg)
        return seg

    def update(self, dt, time_left=None):
        """
        Advance every seg. Returns the segs that expired uncaught this frame.

        With a queue and a time budget the spawn interval is recomputed each
        tick as time_left / blocks_remaining, so every block still gets handed
        out even when spawns are skipped for lack of room on the ring.
        """
        self.timer -= dt
        if self.timer <= 0:
            self.spawn()
            if self.queue is not None and time_left is not None and self.queue:
                pace = time_left / len(self.queue)
                self.timer = max(self.spawn_range[0], min(self.spawn_range[1], pace))
            else:
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


def shade(color, factor):
    """Lighten (factor > 1) or darken (factor < 1) a colour, clamped."""
    return tuple(max(0, min(255, round(c * factor))) for c in color[:3])


class CrystalStyle:
    """The faceted-crystal look, shared by the ring and the segments."""

    def __init__(self, facets=14, jitter=0.07, alpha=90, edge_alpha=200,
                 outline=2, spokes=True, light_angle=-math.pi / 3, contrast=0.45):
        self.facets = facets
        self.jitter = jitter
        self.alpha = alpha
        self.edge_alpha = alpha if edge_alpha is None else edge_alpha
        self.outline = outline
        self.spokes = spokes
        self.light_angle = light_angle
        self.contrast = contrast

    def seams(self, rng, count=None, wrap=False):
        """Per-seam radial jitter. wrap=True closes the loop for a full ring."""
        n = count if count is not None else self.facets
        values = [1 + rng.uniform(-self.jitter, self.jitter) for _ in range(n)]
        return values + ([values[0]] if wrap else
                         [1 + rng.uniform(-self.jitter, self.jitter)])


def draw_crystal_arc(surface, center, r_in, r_out, a0, a1, color, style,
                     jit_out, jit_in, ss=1, glints=()):
    """
    Cut the arc a0..a1 of an annulus into facets and draw them: a translucent
    pane per facet, then brighter seams over the top. jit_out/jit_in hold one
    radial multiplier per seam and are fixed for the life of the shape, so the
    cut stays put instead of shimmering as the arc changes size.
    """
    cx, cy = center
    n = len(jit_out) - 1
    width = max(1, round(style.outline * ss))

    for i in range(n):
        b0 = a0 + (a1 - a0) * i / n
        b1 = a0 + (a1 - a0) * (i + 1) / n
        ro0, ro1 = r_out * jit_out[i], r_out * jit_out[i + 1]
        ri0, ri1 = r_in * jit_in[i], r_in * jit_in[i + 1]

        quad = [
            (cx + ro0 * math.cos(b0), cy + ro0 * math.sin(b0)),
            (cx + ro1 * math.cos(b1), cy + ro1 * math.sin(b1)),
            (cx + ri1 * math.cos(b1), cy + ri1 * math.sin(b1)),
            (cx + ri0 * math.cos(b0), cy + ri0 * math.sin(b0)),
        ]

        facing = math.cos((b0 + b1) / 2 - style.light_angle)
        factor = 1 + style.contrast * facing
        if i in glints:
            factor += 0.55
        if i % 2:
            factor -= 0.12

        if style.alpha:
            pygame.draw.polygon(surface, (*shade(color, factor), style.alpha), quad)
        if style.outline:
            ea = style.edge_alpha
            pygame.draw.line(surface, (*shade(color, factor + 0.35), ea),
                             quad[0], quad[1], width)
            pygame.draw.line(surface, (*shade(color, factor + 0.1), ea),
                             quad[3], quad[2], width)
            if style.spokes:
                pygame.draw.line(surface, (*shade(color, factor + 0.2), ea),
                                 quad[0], quad[3], width)


class GlossStyle:
    """The rounded-glass look for segments."""

    def __init__(self, alpha=235, bands=16, curve=0.55, rim=2, rim_boost=0.55,
                 rounded=True, gloss=0.34):
        self.alpha = alpha
        self.bands = bands
        self.curve = curve
        self.rim = rim
        self.rim_boost = rim_boost
        self.rounded = rounded
        self.gloss = gloss

    def kwargs(self):
        return dict(alpha=self.alpha, bands=self.bands, curve=self.curve,
                    rim=self.rim, rim_boost=self.rim_boost,
                    rounded=self.rounded, gloss=self.gloss)


def draw_gloss_arc(surface, center, r_in, r_out, a0, a1, color, ss=1,
                   alpha=235, bands=16, curve=0.55, rim=2, rim_boost=0.55,
                   rounded=True, gloss=0.34):
    """
    A smooth annulus sector shaded like a cylinder lying along the ring.

    The band is filled as thin sub-bands across its thickness, each shaded by a
    cosine falloff so the surface reads as round rather than stepped. Rounded
    ends come from extending each sub-band by the width of the end semicircle
    at that depth, so the cap is part of the same gradient instead of a flat
    disc painted over it.
    """
    cx, cy = center
    thickness = r_out - r_in
    cap_r = thickness / 2
    mid_r = (r_in + r_out) / 2
    span = abs(a1 - a0)

    for b in range(bands):
        t = (b + 0.5) / bands                      # centre of this sub-band
        ri = r_in + thickness * (b / bands)
        ro = r_in + thickness * ((b + 1) / bands) + 0.75    # overlap, no seams

        # cylinder shading: smooth dome peaking at the gloss line
        v = (t - (1 - gloss)) / max(gloss, 1 - gloss)
        factor = 1 + curve * (math.cos(max(-1.0, min(1.0, v)) * math.pi / 2) - 0.5)

        # round end: how far this depth reaches past the flat end, in radians
        ext = 0.0
        if rounded:
            d = abs(t - 0.5) * thickness
            ext = math.sqrt(max(0.0, cap_r * cap_r - d * d)) / max(mid_r, 1e-6)

        b0, b1 = a0 - ext, a1 + ext
        steps = max(3, int((span + 2 * ext) * r_out / 4))
        pts = []
        for radius, order in ((ro, range(steps + 1)), (ri, range(steps, -1, -1))):
            for i in order:
                a = b0 + (b1 - b0) * i / steps
                pts.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))
        pygame.draw.polygon(surface, (*shade(color, factor), alpha), pts)

    if rim:
        width = max(1, round(rim * ss))
        steps = max(3, int(span * r_out / 4))
        pts = [(cx + r_out * math.cos(a0 + (a1 - a0) * i / steps),
                cy + r_out * math.sin(a0 + (a1 - a0) * i / steps))
               for i in range(steps + 1)]
        pygame.draw.lines(surface, (*shade(color, 1 + rim_boost), alpha),
                          False, pts, width)


class CrystalRing:
    """
    A faceted, gem-cut version of the two ring circles.

    The geometry never changes, so the whole ring is rendered once at
    construction and blitted every frame after that.
    """

    def __init__(self, center, r_in, r_out, color, style, ss=3, pad=6,
                 glints=3, seed=4):
        self.color = color
        size = 2 * (r_out + pad)
        self.topleft = (center[0] - size / 2, center[1] - size / 2)

        rng = random.Random(seed)
        big = pygame.Surface((size * ss, size * ss), pygame.SRCALPHA)
        mid = size * ss / 2

        draw_crystal_arc(
            big, (mid, mid), r_in * ss, r_out * ss, 0, math.tau, color, style,
            style.seams(rng, wrap=True), style.seams(rng, wrap=True), ss=ss,
            glints=set(rng.sample(range(style.facets), min(glints, style.facets))),
        )
        self.image = pygame.transform.smoothscale(big, (size, size))

    def draw(self, surface):
        surface.blit(self.image, self.topleft)


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
             bar=None, bar_color=(30, 40, 70), bar_overhang=10, style=None):
        self.big.fill((0, 0, 0, 0))
        for seg in segs:
            if seg.dead:
                continue
            r_in, r_out = seg.radii(self.r_in, self.r_out, beat_amplitude)
            color = seg.color(c_start, c_end)

            if style is not None:
                draw_gloss_arc(
                    self.big, self.local, r_in * self.ss, r_out * self.ss,
                    seg.angle - seg.span / 2, seg.angle + seg.span / 2,
                    color, ss=self.ss, **style.kwargs(),
                )
            else:
                pts = seg.points(self.local, r_in * self.ss, r_out * self.ss)
                pygame.draw.polygon(self.big, color, pts)

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


class OneShot:
    """Plays a frame list once at a fixed position, then reports itself finished."""

    def __init__(self, frames, pos, fps=22, scale=1, hold=False):
        self.hold = hold          # freeze on the last frame instead of ending
        self.frames = frames
        self.pos = pos
        self.fps = fps
        self.scale = scale
        self.timer = 0.0
        self.index = 0

    @property
    def done(self):
        return not self.hold and self.index >= len(self.frames)

    def update(self, dt):
        self.timer += dt
        step = 1 / self.fps
        while self.timer >= step:
            self.timer -= step
            self.index += 1

    def draw(self, surface):
        if self.done:
            return
        image = self.frames[min(self.index, len(self.frames) - 1)]
        if self.scale != 1:
            size = (int(image.get_width() * self.scale), int(image.get_height() * self.scale))
            image = pygame.transform.scale(image, size)
        surface.blit(image, image.get_rect(center=self.pos))


class Effects:
    """Holds the one-shot effects currently playing and drops them when finished."""

    def __init__(self):
        self.active = []

    def spawn(self, frames, pos, fps=22, scale=1):
        self.active.append(OneShot(frames, pos, fps, scale))

    def update(self, dt):
        for effect in self.active:
            effect.update(dt)
        self.active = [e for e in self.active if not e.done]

    def draw(self, surface):
        for effect in self.active:
            effect.draw(surface)


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


class ReportCard:
    """
    End-of-semester panel. Sits on the left so the character animation has the
    right-hand side to itself -- in the middle of the screen the sprite was
    lost behind the ring and the text.
    """

    def __init__(self, title_text, row_text, small_text,
                 color=(232, 238, 230), pass_color=(150, 224, 150),
                 fail_color=(236, 92, 92)):
        self.title = title_text
        self.row = row_text
        self.small = small_text
        self.color = color
        self.pass_color = pass_color
        self.fail_color = fail_color

    def draw(self, surface, syllabus, anchor_x, top, dead=False, dim=205):
        rows, overall, letter, points, failed = syllabus.report()

        veil = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        veil.fill((6, 8, 14, dim))
        surface.blit(veil, (0, 0))

        if dead:
            head, head_color = "DROPPED OUT", self.fail_color
        elif failed:
            head, head_color = "SEMESTER FAILED", self.fail_color
        else:
            head, head_color = "SEMESTER PASSED", self.pass_color

        y = top
        self.title.draw(surface, head, head_color, topleft=(anchor_x, y))
        y += 52

        for course, score, row_letter, _ in rows:
            ok = course not in failed
            self.row.draw(surface, f"{course.upper():<5}{score:5.1f}%  {row_letter:<2}",
                          self.pass_color if ok else self.fail_color,
                          topleft=(anchor_x, y))
            y += 34

        y += 12
        pygame.draw.line(surface, (90, 98, 115), (anchor_x, y),
                         (anchor_x + 290, y), 2)
        y += 16

        self.row.draw(surface, f"SEM  {overall:5.1f}%  {letter}", self.color,
                      topleft=(anchor_x, y))
        y += 34
        self.small.draw(surface, f"gpa {points:.1f}", self.color,
                        topleft=(anchor_x, y))
        y += 28

        if dead:
            note = "out of health"
        elif failed:
            note = "failed " + ", ".join(failed)
        else:
            note = "all classes passed"
        self.small.draw(surface, note,
                        self.fail_color if (failed or dead) else self.pass_color,
                        topleft=(anchor_x, y))
        y += 34
        self.small.draw(surface, "press R to retry", self.color,
                        topleft=(anchor_x, y))


class PixelText:
    """
    Renders text small then scales it up with nearest-neighbour, so the glyphs
    come out chunky and hard-edged instead of smoothly antialiased -- the cheap
    way to get a retro look out of an ordinary system font.
    """

    def __init__(self, font, scale=3):
        self.font = font
        self.scale = scale
        self._cache = {}

    def render(self, text, color):
        key = (text, tuple(color[:3]))
        if key not in self._cache:
            small = self.font.render(text, False, color)      # no antialiasing
            size = (small.get_width() * self.scale, small.get_height() * self.scale)
            self._cache[key] = pygame.transform.scale(small, size)
        return self._cache[key]

    def draw(self, surface, text, color, **anchor):
        image = self.render(text, color)
        surface.blit(image, image.get_rect(**anchor))
        return image.get_rect(**anchor)


class HealthBar:
    """
    Retro segmented health. Each miss-press costs a cell, each catch refunds
    one. Runs out and the semester is over early.
    """

    def __init__(self, pixel_text, maximum=10, cell=(20, 26), pad=4, border=3):
        self.text = pixel_text
        self.maximum = maximum
        self.value = maximum
        self.cell_w, self.cell_h = cell
        self.pad = pad
        self.border = border
        self.flash = 0.0              # briefly reddens the frame after a hit

    @property
    def dead(self):
        return self.value <= 0

    def damage(self, amount=1):
        self.value = max(0, self.value - amount)
        self.flash = 0.35
        return self.dead

    def heal(self, amount=1):
        self.value = min(self.maximum, self.value + amount)

    def update(self, dt):
        self.flash = max(0.0, self.flash - dt)

    def width(self):
        return self.maximum * (self.cell_w + self.pad) - self.pad + self.border * 4

    def draw(self, surface, center_x, y):
        full = self.width()
        x0 = center_x - full / 2
        frame = pygame.Rect(x0, y, full, self.cell_h + self.border * 4)

        shell = (250, 120, 120) if self.flash > 0 else (232, 238, 230)
        pygame.draw.rect(surface, (12, 14, 22), frame)
        pygame.draw.rect(surface, shell, frame, self.border)

        for i in range(self.maximum):
            cx = x0 + self.border * 2 + i * (self.cell_w + self.pad)
            cell = pygame.Rect(cx, y + self.border * 2, self.cell_w, self.cell_h)
            if i < self.value:
                # green while healthy, amber, then red as it empties
                ratio = self.value / self.maximum
                color = ((236, 92, 92) if ratio <= 0.3 else
                         (245, 198, 96) if ratio <= 0.6 else (150, 224, 150))
                pygame.draw.rect(surface, color, cell)
                pygame.draw.rect(surface, shade(color, 1.35),
                                 pygame.Rect(cell.x, cell.y, cell.w, 4))
            else:
                pygame.draw.rect(surface, (44, 48, 60), cell)

        self.text.draw(surface, "HP", shell,
                       midright=(x0 - 12, y + frame.height / 2))


class GradePanel:
    """Running grade per class, stacked, with a pass/fail read at a glance."""

    GOOD = (150, 224, 150)
    OK = (245, 198, 96)
    BAD = (236, 92, 92)
    IDLE = (150, 158, 175)

    def __init__(self, pixel_text, courses, pos=(20, 18), row_h=52,
                 bar=(168, 11)):
        self.text = pixel_text
        self.courses = list(courses)
        self.pos = pos
        self.row_h = row_h
        self.bar_w, self.bar_h = bar

    @staticmethod
    def tint(score):
        if score is None:
            return GradePanel.IDLE
        if score >= 80:
            return GradePanel.GOOD
        if score >= 60:
            return GradePanel.OK
        return GradePanel.BAD

    def draw(self, surface, syllabus):
        x, y = self.pos
        for course in self.courses:
            score = syllabus.live_class_score(course)
            color = self.tint(score)
            label = f"{course.upper():<5}" + ("   --" if score is None
                                               else f"{score:5.1f}%")
            self.text.draw(surface, label, color, topleft=(x, y))

            track = pygame.Rect(x, y + self.row_h - 20, self.bar_w, self.bar_h)
            pygame.draw.rect(surface, (26, 30, 40), track)
            if score is not None:
                fill = pygame.Rect(track.x, track.y,
                                   track.w * max(0.0, min(1.0, score / 100)),
                                   track.h)
                pygame.draw.rect(surface, color, fill)
            pygame.draw.rect(surface, (90, 98, 115), track, 1)
            # the 60% pass mark, so "am I failing" is readable at a glance
            mark = track.x + track.w * 0.6
            pygame.draw.line(surface, (232, 238, 230),
                             (mark, track.y - 2), (mark, track.bottom + 2), 1)
            y += self.row_h
