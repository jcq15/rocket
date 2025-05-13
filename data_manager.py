import os
import datetime
from logger import logger

class DataManager:
    def __init__(self):
        self.games = {}

    def register_game(self, game_type, game_instance):
        self.games[game_type] = game_instance

    def save_all(self):
        for game in self.games.values():
            game.save_all_rooms()
        logger.info('已保存所有房间')

    def load_all(self):
        for game in self.games.values():
            game.load_all_rooms()
        logger.info('已加载所有房间')

    def backup_all(self):
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        for game_type, game in self.games.items():
            src_dir = game.data_dir
            backup_dir = src_dir.parent / (src_dir.name + '_backup') / today
            backup_dir.mkdir(parents=True, exist_ok=True)
            for file in src_dir.glob('*.json'):
                os.system(f'cp "{file}" "{backup_dir / file.name}"') 