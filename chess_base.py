import json
from pathlib import Path

class ChessGameBase:
    def __init__(self, game_type, channel_id):
        self.game_type = game_type
        self.channel_id = channel_id
        self.rooms = {} # 房间号 -> {game, players, 状态}
        self.user_room = {} # 这个表示用户当前在哪个房间活动。一个用户可以同时在多个room的players列表中，但至多只能在一个房间活动。
        self.data_dir = Path(f'data/{game_type}')
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # 读取房间号儿，如果文件不存在，则创建文件并设置房间号为1000
        if not (self.data_dir / 'room_id.txt').exists():
            with open(self.data_dir / 'room_id.txt', 'w', encoding='utf-8') as f:
                f.write('1000') 
        with open(self.data_dir / 'room_id.txt', 'r', encoding='utf-8') as f:
            self.room_id_counter = int(f.read())

    def new_room_id(self):
        while True:
            rid = str(self.room_id_counter)
            self.room_id_counter += 1
            if rid not in self.rooms:
                return rid

    def save_all_rooms(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        for room_id, room in self.rooms.items():
            if room.get('status') == 'finished':
                continue
            data = self.room_to_dict(room)
            with open(self.data_dir / f'{room_id}.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        # 保存房间号
        with open(self.data_dir / 'room_id.txt', 'w', encoding='utf-8') as f:
            f.write(str(self.room_id_counter))

    def load_all_rooms(self):
        # 读取房间号
        with open(self.data_dir / 'room_id.txt', 'r', encoding='utf-8') as f:
            self.room_id_counter = int(f.read())
        self.rooms = {}
        self.user_room = {}
        if not self.data_dir.exists():
            return
        for file in self.data_dir.glob('*.json'):
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get('status') == 'finished':
                    continue
                room = self.dict_to_room(data)
                room_id = file.stem
                self.rooms[room_id] = room
                for p in room['players']:
                    self.user_room[p['id']] = room_id

    def room_to_dict(self, room):
        """子类可覆盖，默认直接返回room（需可序列化）"""
        return room

    def dict_to_room(self, data):
        """子类可覆盖，默认直接返回data"""
        return data

    async def message_handler(self, msg):
        """每个子类都应实现自己的消息处理逻辑"""
        raise NotImplementedError('请在子类中实现message_handler') 