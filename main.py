import pygame
import config as cfg
from utils.helpers import load_frames, load_layers, Animation

W, H = cfg.WIDTH, cfg.HEIGHT # game width and height

IDLE_SHEET = "assets/char animation/Sprites/Idle.png"
SKY_DIR = "assets/coud_bg/Clouds/Clouds 5"
FRAME_SIZE = 250

def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    clock = pygame.time.Clock()
    running = True

    sky = load_layers(SKY_DIR, (W, H))
    idle_animation = Animation(load_frames(IDLE_SHEET, FRAME_SIZE, FRAME_SIZE), fps=8)

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        for layer in sky:
            screen.blit(layer, (0, 0))
        idle_animation.draw(screen, (W / 2, H / 2 - 30), 4)
        pygame.draw.circle(screen, "red", (W/ 2, H / 2), 180, 2)
        pygame.draw.circle(screen, "red", (W/2, H/2), 150, 2)

        

        pygame.display.flip()

        dt = clock.tick(60) / 1000
        idle_animation.update(dt)

    pygame.quit()

if __name__ == "__main__":
    main()

