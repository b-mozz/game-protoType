import os
import pygame


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
