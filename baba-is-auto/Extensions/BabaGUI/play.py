"""
Interactive Baba Is You player using pyBaba + pygame.
Arrow keys to move, R to restart, Escape to quit.

Usage (from BabaGUI/):
    python play.py
    python play.py ../../Resources/Maps/baba_is_you.txt
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
import pygame
import pyBaba
import config
import sprites

LEVEL = sys.argv[1] if len(sys.argv) > 1 else "../../Resources/Maps/out_of_reach.txt"

icon_images = {
    pyBaba.ObjectType.ICON_BABA:   'BABA',
    pyBaba.ObjectType.ICON_FLAG:   'FLAG',
    pyBaba.ObjectType.ICON_WALL:   'WALL',
    pyBaba.ObjectType.ICON_ROCK:   'ROCK',
    pyBaba.ObjectType.ICON_TILE:   'TILE',
    pyBaba.ObjectType.ICON_WATER:  'WATER',
    pyBaba.ObjectType.ICON_GRASS:  'GRASS',
    pyBaba.ObjectType.ICON_LAVA:   'LAVA',
    pyBaba.ObjectType.ICON_SKULL:  'SKULL',
    pyBaba.ObjectType.ICON_FLOWER: 'FLOWER',
}

text_images = {
    pyBaba.ObjectType.BABA:    'BABA',
    pyBaba.ObjectType.IS:      'IS',
    pyBaba.ObjectType.YOU:     'YOU',
    pyBaba.ObjectType.FLAG:    'FLAG',
    pyBaba.ObjectType.WIN:     'WIN',
    pyBaba.ObjectType.WALL:    'WALL',
    pyBaba.ObjectType.STOP:    'STOP',
    pyBaba.ObjectType.ROCK:    'ROCK',
    pyBaba.ObjectType.PUSH:    'PUSH',
    pyBaba.ObjectType.WATER:   'WATER',
    pyBaba.ObjectType.SINK:    'SINK',
    pyBaba.ObjectType.LAVA:    'LAVA',
    pyBaba.ObjectType.MELT:    'MELT',
    pyBaba.ObjectType.HOT:     'HOT',
    pyBaba.ObjectType.SKULL:   'SKULL',
    pyBaba.ObjectType.DEFEAT:  'DEFEAT',
}

KEY_DIR = {
    pygame.K_UP:    pyBaba.Direction.UP,
    pygame.K_DOWN:  pyBaba.Direction.DOWN,
    pygame.K_LEFT:  pyBaba.Direction.LEFT,
    pygame.K_RIGHT: pyBaba.Direction.RIGHT,
}


def make_game():
    return pyBaba.Game(LEVEL)


def render_priority(obj_type, player_icon):
    if obj_type == pyBaba.ObjectType.ICON_TILE:
        return 0
    if pyBaba.IsTextType(obj_type) or obj_type == player_icon:
        return 2
    return 1


def draw(screen, game, map_sprite_group, result_image_group):
    map_sprite_group.empty()
    m = game.GetMap()
    player_icon = game.GetPlayerIcon()
    for pass_num in range(3):
        for y in range(m.GetHeight()):
            for x in range(m.GetWidth()):
                cell = m.At(x, y)
                for obj_type in cell.GetTypes():
                    if render_priority(obj_type, player_icon) != pass_num:
                        continue
                    if pyBaba.IsTextType(obj_type):
                        img = text_images.get(obj_type)
                        is_icon = False
                    else:
                        if obj_type == pyBaba.ObjectType.ICON_EMPTY:
                            continue
                        img = icon_images.get(obj_type)
                        is_icon = True
                    if img:
                        map_sprite_group.add(
                            sprites.MapSprite(img, x * config.BLOCK_SIZE, y * config.BLOCK_SIZE, is_icon)
                        )
    screen.fill(config.COLOR_BACKGROUND)
    map_sprite_group.draw(screen)

    state = game.GetPlayState()
    if state in (pyBaba.PlayState.WON, pyBaba.PlayState.LOST):
        screen_size = (m.GetWidth() * config.BLOCK_SIZE, m.GetHeight() * config.BLOCK_SIZE)
        result_image_group.update(state, screen_size)
        result_image_group.draw(screen)

    pygame.display.flip()


def main():
    pygame.init()
    game = make_game()
    m = game.GetMap()
    screen_size = (m.GetWidth() * config.BLOCK_SIZE, m.GetHeight() * config.BLOCK_SIZE)
    screen = pygame.display.set_mode(screen_size, pygame.DOUBLEBUF)
    pygame.display.set_caption(f"Baba Is You — {LEVEL.split('/')[-1]}")

    map_sprite_group = pygame.sprite.Group()
    result_image = sprites.ResultImage()
    result_image_group = pygame.sprite.Group()
    result_image_group.add(result_image)

    clock = pygame.time.Clock()
    steps = 0

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                if event.key == pygame.K_r:
                    game = make_game()
                    steps = 0
                    print("Restarted.")
                direction = KEY_DIR.get(event.key)
                if direction and game.GetPlayState() == pyBaba.PlayState.PLAYING:
                    game.MovePlayer(direction)
                    steps += 1
                    state = game.GetPlayState()
                    print(f"Step {steps}: {event.key} -> {state}")

        draw(screen, game, map_sprite_group, result_image_group)
        clock.tick(config.FPS)


if __name__ == '__main__':
    main()
