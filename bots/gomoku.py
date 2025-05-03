import random
import re
import cv2
import numpy as np
import os
import json
from pathlib import Path
from chess_base import ChessGameBase

class GomokuGame:
    def __init__(self):
        self.board_size = (15, 15)
        self.board = [[0] * self.board_size[0] for _ in range(self.board_size[1])] # 0: 空, 1: 黑棋, 2: 白棋
        self.current_player = 1 # 1: 黑棋, 2: 白棋
        self.game_over = False
        self.winner = None
        self.last_move = None
    
    def move(self, player, x, y):
        # return: {'success': bool, 'winner': int-0/1/2, 'msg': str}
        # 是否越界
        if not (0 <= x < self.board_size[0] and 0 <= y < self.board_size[1]):
            return {'success': False, 'winner': 0, 'msg': '你聋啊？这都跑棋盘外边儿了！'}
        # 是否已有棋子
        if self.board[x][y] != 0:
            return {'success': False, 'winner': 0, 'msg': '你瞎呀？这儿已经有子儿了！'}
        # 是否轮到当前玩家
        if self.current_player != player:
            return {'success': False, 'winner': 0, 'msg': '你彪啊？还没轮到你下棋！'}
        self.board[x][y] = player
        self.last_move = (player, x, y)
        if self.check_win(player, x, y):
            self.game_over = True
            self.winner = player
            return {'success': True, 'winner': player, 'msg': ''}
        else:
            self.current_player = 2 if player == 1 else 1
            return {'success': True, 'winner': 0, 'msg': ''}
    
    def check_win(self, player, x, y):
        # 检查8个方向，是否有连续5子
        directions = [
            (1, 0), (0, 1), (1, 1), (1, -1)
        ]
        for dx, dy in directions:
            count = 1
            for d in [1, -1]:
                nx, ny = x, y
                while True:
                    nx += dx * d
                    ny += dy * d
                    if 0 <= nx < self.board_size[0] and 0 <= ny < self.board_size[1] and self.board[nx][ny] == player:
                        count += 1
                    else:
                        break
            if count >= 5:
                return True
        return False
    
    def get_board_str(self):
        # 两边加上坐标
        board_str = '   ' + ' '.join([str(i) for i in range(self.board_size[0])]) + '\n'
        for i in range(self.board_size[1]):
            board_str += str(i) + ' ' + ' '.join([str(cell) for cell in self.board[i]]) + '\n'
        return board_str

    def draw_board(self, path=None):
        cell_size = 40
        margin = 40
        board_pixel = cell_size * (self.board_size[0] - 1) + margin * 2
        img = np.ones((board_pixel, board_pixel, 3), dtype=np.uint8) * 240
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        thickness = 1
        # 画网格线（交替颜色）
        for i in range(self.board_size[0]):
            color = (0, 0, 0) if i % 2 == 0 else (180, 180, 180)
            pt1 = (margin, margin + i * cell_size)
            pt2 = (margin + cell_size * (self.board_size[0] - 1), margin + i * cell_size)
            cv2.line(img, pt1, pt2, color, 1)
            pt1 = (margin + i * cell_size, margin)
            pt2 = (margin + i * cell_size, margin + cell_size * (self.board_size[1] - 1))
            cv2.line(img, pt1, pt2, color, 1)
        # 画棋子
        for i in range(self.board_size[0]):
            for j in range(self.board_size[1]):
                if self.board[i][j] == 1:
                    center = (margin + j * cell_size, margin + i * cell_size)
                    cv2.circle(img, center, cell_size // 2 - 2, (0, 0, 0), -1)
                elif self.board[i][j] == 2:
                    center = (margin + j * cell_size, margin + i * cell_size)
                    cv2.circle(img, center, cell_size // 2 - 2, (255, 255, 255), -1)
                    cv2.circle(img, center, cell_size // 2 - 2, (0, 0, 0), 1)
        # 标记最后一步
        if self.last_move:
            player, x, y = self.last_move
            center = (margin + y * cell_size, margin + x * cell_size)
            cv2.circle(img, center, cell_size // 4, (0, 0, 255), 2)
        # 四周加坐标
        for i in range(self.board_size[0]):
            # 上
            cv2.putText(img, str(i), (margin + i * cell_size - 8, margin - 10), font, font_scale, (0, 0, 200), thickness, cv2.LINE_AA)
            # 下
            cv2.putText(img, str(i), (margin + i * cell_size - 8, board_pixel - margin + 25), font, font_scale, (0, 0, 200), thickness, cv2.LINE_AA)
            # 左
            cv2.putText(img, str(i), (margin - 30, margin + i * cell_size + 8), font, font_scale, (0, 0, 200), thickness, cv2.LINE_AA)
            # 右
            cv2.putText(img, str(i), (board_pixel - margin + 10, margin + i * cell_size + 8), font, font_scale, (0, 0, 200), thickness, cv2.LINE_AA)
        # 保存图片
        if path is None:
            path = '/tmp/gomoku_board.png'
        cv2.imwrite(path, img)
        return path

    def to_dict(self):
        return {
            'board_size': self.board_size,
            'board': self.board,
            'current_player': self.current_player,
            'game_over': self.game_over,
            'winner': self.winner,
            'last_move': self.last_move,
        }

    @classmethod
    def from_dict(cls, data):
        obj = cls()
        obj.board_size = tuple(data.get('board_size', (15, 15)))
        obj.board = data.get('board', [[0]*15 for _ in range(15)])
        obj.current_player = data.get('current_player', 1)
        obj.game_over = data.get('game_over', False)
        obj.winner = data.get('winner', None)
        obj.last_move = tuple(data.get('last_move')) if data.get('last_move') else None
        return obj


class GomokuBot(ChessGameBase):
    def __init__(self):
        super().__init__('gomoku', '6815cd855ebf6e703ce29395') # channel_id
    
    async def send_board_image(self, game, room_id, msg):
        img_path = f"tmp/gomoku_{room_id}.png"
        game.draw_board(img_path)
        if hasattr(msg, 'reply_image'):
            await msg.reply_image(img_path)
        else:
            await msg.reply("[图片功能未实现]")

    async def message_handler(self, msg):
        user_id = msg.talker_id
        text = msg.text.strip()
        # 开房
        if text.startswith('开房'):
            room_id = self.new_room_id()
            self.rooms[room_id] = {
                'game': GomokuGame(),
                'players': [{'id': user_id, 'name': msg.talker_name}],
                'status': 'waiting',
            }
            self.user_room[user_id] = room_id
            await msg.reply(f"房间已创建，房间号: {room_id}，等待其他玩家加入。")
        # 加入
        elif text.startswith('加入'):
            room_id = text[2:].strip()
            if not room_id:
                await msg.reply("加哪儿啊？发送【加入 房间号】，例如: 加入 1000")
                return
            if room_id not in self.rooms:
                await msg.reply("扯王八犊子呢？没这房儿。")
                return
            room = self.rooms[room_id]
            if user_id in [p['id'] for p in room['players']]:
                # 如果用户已经在房间里，则返回提示
                if room_id == self.user_room.get(user_id):
                    await msg.reply("你丫的已经在这儿了，别瞎折腾了！")
                else:
                    self.user_room[user_id] = room_id
                    await msg.reply("你蛄蛹到这儿了！")
                return
            if len(room['players']) >= 2:
                await msg.reply("没地儿咯！")
                return
            room['players'].append({'id': user_id, 'name': msg.talker_name})
            self.user_room[user_id] = room_id
            if len(room['players']) == 2:
                # 随机决定谁黑
                random.shuffle(room['players'])
                response = f"加入房间{room_id}成功。游戏开始！{room['players'][0]['name']}先手。"
                room['status'] = 'playing'
                await msg.reply(response)
                await self.send_board_image(room['game'], room_id, msg)
            else:
                await msg.reply(f"加入房间{room_id}成功，{len(room['players'])}={2-len(room['players'])}！")
        
            # 暂时不支持离开和退出
            """
            # 离开
            elif text == '离开':
                if user_id not in self.user_room:
                    await msg.reply("你当前不在任何房间。")
                room_id = self.user_room[user_id]
                await msg.reply(f"你已暂时离开房间{room_id}。发送'加入 {room_id}'可重新进入。")
            
            # 退出
            elif text == '退出':
                if user_id not in self.user_room:
                    await msg.reply("你当前不在任何房间。")
                room_id = self.user_room[user_id]
                room = self.rooms.get(room_id)
                if room:
                    if user_id in [p['id'] for p in room['players']]:
                        room['players'].remove({'id': user_id, 'name': msg.talker_name})
                    if not room['players']:
                        del self.rooms[room_id]
                del self.user_room[user_id]
                return f"你已退出房间{room_id}。"
            """

        # 落子
        elif re.match(r'^\d+\s+\d+$', text.strip()):
            # 应该是落子
            if user_id not in self.user_room:
                await msg.reply("你当前不在任何房间，请先'开房'或'加入 房间号'。")
                return
            room_id = self.user_room[user_id]
            room = self.rooms.get(room_id)
            if not room or room['status'] != 'playing':
                await msg.reply("房间未开始游戏。")
                return
            game = room['game']
            idx = [p['id'] for p in room['players']].index(user_id)
            player = idx + 1 # 玩家1/2
            if game.current_player != player:
                await msg.reply("还没轮到你下棋。")
                return
            try:
                x, y = map(int, text.split())
            except Exception:
                await msg.reply("落子格式错误，应为: x y")
                return
            response = game.move(player, x, y)
            if not response['success']:
                await msg.reply(response['msg'])
                return
            # 落子成功
            if response['winner'] != 0:
                winner = '黑棋' if response['winner'] == 1 else '白棋'
                response = f"{winner}胜利！游戏结束。"
                room['status'] = 'finished'
                await msg.reply(response)
            else:
                next_player = room['players'][game.current_player-1]
                color = '黑棋' if game.current_player == 1 else '白棋'
                await msg.reply(f"落子成功，轮到{next_player['name']}。")
                await self.send_board_image(game, room_id, msg)

    def room_to_dict(self, room):
        return {
            'game': room['game'].to_dict(),
            'players': room['players'],
            'status': room['status']
        }

    def dict_to_room(self, data):
        return {
            'game': GomokuGame.from_dict(data['game']),
            'players': data['players'],
            'status': data['status']
        }
