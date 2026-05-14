"""
replay_gui.py
Reads a trial JSONL log, writes actions to action.txt, then plays them back
in the GUI exactly like main.py does.

Usage (from BabaGUI/):
    python replay_gui.py <path_to_episode_log.jsonl>

Example (from archived experiment data):
    python replay_gui.py ../../../baba_is_you_old_cache_2/deepseek_chat/baba_is_you_20260509_221619/episode_001_log.jsonl
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
import json
import pygame
import pyBaba
import config
import sprites

DIR_MAP = {
    "up":    "Direction.UP",
    "down":  "Direction.DOWN",
    "left":  "Direction.LEFT",
    "right": "Direction.RIGHT",
}

ACTION_MAP = {
    "Direction.UP":    pyBaba.Direction.UP,
    "Direction.DOWN":  pyBaba.Direction.DOWN,
    "Direction.LEFT":  pyBaba.Direction.LEFT,
    "Direction.RIGHT": pyBaba.Direction.RIGHT,
    "Direction.NONE":  pyBaba.Direction.NONE,
}

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
    pyBaba.ObjectType.BABA:   'BABA',
    pyBaba.ObjectType.IS:     'IS',
    pyBaba.ObjectType.YOU:    'YOU',
    pyBaba.ObjectType.FLAG:   'FLAG',
    pyBaba.ObjectType.WIN:    'WIN',
    pyBaba.ObjectType.WALL:   'WALL',
    pyBaba.ObjectType.STOP:   'STOP',
    pyBaba.ObjectType.ROCK:   'ROCK',
    pyBaba.ObjectType.PUSH:   'PUSH',
    pyBaba.ObjectType.WATER:  'WATER',
    pyBaba.ObjectType.SINK:   'SINK',
    pyBaba.ObjectType.LAVA:   'LAVA',
    pyBaba.ObjectType.MELT:   'MELT',
    pyBaba.ObjectType.HOT:    'HOT',
    pyBaba.ObjectType.SKULL:  'SKULL',
    pyBaba.ObjectType.DEFEAT: 'DEFEAT',
}


def load_log(log_path):
    with open(log_path) as f:
        steps = [json.loads(line) for line in f if line.strip()]
    actions = []
    for step in steps:
        a = step.get("agent_action")
        actions.append(DIR_MAP.get(a, "Direction.NONE") if a else "Direction.NONE")
    return actions


def get_level_file(log_path):
    run_dir = os.path.dirname(log_path)
    config_path = os.path.join(run_dir, "agent_config.json")
    with open(config_path) as f:
        cfg = json.load(f)
    return cfg["level_file"]


def write_action_txt(actions):
    with open("action.txt", "w") as f:
        f.write("\n".join(actions))


def render_priority(obj_type, player_icon):
    if obj_type == pyBaba.ObjectType.ICON_TILE:
        return 0
    if pyBaba.IsTextType(obj_type) or obj_type == player_icon:
        return 2
    return 1


def draw(screen, game, map_sprite_group):
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


def main():
    if len(sys.argv) < 2:
        print("Usage: python replay_gui.py <path_to_episode_log.jsonl>")
        sys.exit(1)

    log_path = sys.argv[1]
    actions = load_log(log_path)
    level_file = get_level_file(log_path)
    write_action_txt(actions)

    print(f"Level:   {os.path.basename(level_file)}")
    print(f"Actions: {len(actions)} steps")
    print("Space to pause/resume, R to restart, Escape to quit.")

    pygame.init()
    screen_size = None

    def init_game():
        nonlocal screen_size
        g = pyBaba.Game(level_file)
        m = g.GetMap()
        screen_size = (m.GetWidth() * config.BLOCK_SIZE, m.GetHeight() * config.BLOCK_SIZE)
        return g

    game = init_game()
    screen = pygame.display.set_mode(screen_size, pygame.DOUBLEBUF)
    pygame.display.set_caption(f"Replay — {os.path.basename(level_file)}")

    map_sprite_group = pygame.sprite.Group()
    result_image = sprites.ResultImage()
    result_image_group = pygame.sprite.Group()
    result_image_group.add(result_image)

    clock = pygame.time.Clock()
    pygame.time.set_timer(pygame.USEREVENT, 200)

    time_step = 0
    paused = True
    game_over = False

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                if event.key == pygame.K_SPACE:
                    paused = not paused
                if event.key == pygame.K_r:
                    game = init_game()
                    time_step = 0
                    paused = True
                    game_over = False
                    print("Restarted.")

            if event.type == pygame.USEREVENT and not paused and not game_over:
                if time_step < len(actions):
                    game.MovePlayer(ACTION_MAP[actions[time_step]])
                    print(f"Step {time_step + 1}/{len(actions)}: {actions[time_step]}")
                    time_step += 1

        state = game.GetPlayState()
        if state in (pyBaba.PlayState.WON, pyBaba.PlayState.LOST):
            game_over = True

        draw(screen, game, map_sprite_group)

        if game_over:
            result_image_group.update(state, screen_size)
            result_image_group.draw(screen)

        pygame.display.flip()
        clock.tick(config.FPS)


if __name__ == "__main__":
    main()
