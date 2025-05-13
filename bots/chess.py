import random
import re
import cv2
import numpy as np
import os
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from chess_base import ChessGameBase
import hashlib

# 棋子中文名
PIECE_NAMES = {
    'K': '皇', 'Q': '厚', 'R': '車', 'B': '相', 'N': '馬', 'P': '兵',
    'k': '王', 'q': '后', 'r': '车', 'b': '象', 'n': '马', 'p': '卒',
}
PIECE_COLORS = {
    'w': '白',
    'b': '黑',
}

# 棋子初始布局
START_BOARD = [
    ['bR', 'bN', 'bB', 'bQ', 'bK', 'bB', 'bN', 'bR'],
    ['bP'] * 8,
    [None] * 8,
    [None] * 8,
    [None] * 8,
    [None] * 8,
    ['wP'] * 8,
    ['wR', 'wN', 'wB', 'wQ', 'wK', 'wB', 'wN', 'wR'],
]

class ChessGame:
    def __init__(self, must_capture=False):
        self.board = [row[:] for row in START_BOARD]
        self.current_player = 'w'  # 'w' or 'b'
        self.game_over = False
        self.winner = None
        self.last_move = None  # move dict
        self.move_history = []
        # 王侧/后侧易位权，考虑自定义初始局面可能没车/王车不在原位的情况
        # 白王e1(7,4)，白车a1(7,0)、h1(7,7)
        # 黑王e8(0,4)，黑车a8(0,0)、h8(0,7)
        self.castling_rights = {
            'wK': self.get_piece(7, 4) == 'wK' and self.get_piece(7, 7) == 'wR',
            'wQ': self.get_piece(7, 4) == 'wK' and self.get_piece(7, 0) == 'wR',
            'bK': self.get_piece(0, 4) == 'bK' and self.get_piece(0, 7) == 'bR',
            'bQ': self.get_piece(0, 4) == 'bK' and self.get_piece(0, 0) == 'bR',
        }
        self.en_passant = None  # (x, y) 可吃过路兵目标格
        self.must_capture = must_capture
        self.position_history = []

    def in_board(self, x, y):
        return 0 <= x < 8 and 0 <= y < 8

    def get_piece(self, x, y):
        return self.board[x][y]

    def get_position_hash(self):
        # 只考虑棋盘、当前方、易位权、过路兵
        board_str = json.dumps(self.board, sort_keys=True)
        cr_str = json.dumps(self.castling_rights, sort_keys=True)
        ep_str = str(self.en_passant)
        s = f'{board_str}|{self.current_player}|{cr_str}|{ep_str}'
        return hashlib.md5(s.encode()).hexdigest()

    def move(self, move):
        # 兼容外部传入list格式
        if isinstance(move, list) and len(move) == 2:
            move = {'from': tuple(move[0]), 'to': tuple(move[1])}
        player = self.current_player
        if not self.is_legal_move(move):
            msg = '走法不合法！正确示例：\n正常走棋：a2a4\n升变：a7a8Q\n王车易位：e1g1\n吃过路兵：a5b6'
            if self.must_capture:
                msg += '\n当前是有吃必吃模式，请确保有吃必吃！'
            return {'success': False, 'msg': msg}
        fx, fy = move['from']
        tx, ty = move['to']
        piece = self.get_piece(fx, fy)
        # 判断王车易位
        if piece and piece[1] == 'K' and fx == tx and abs(fy - ty) == 2:
            # 王侧易位
            if ty > fy:
                self.board[fx][fy] = None
                self.board[fx][fy+2] = piece
                self.board[fx][fy+1] = self.board[fx][fy+3]
                self.board[fx][fy+3] = None
            # 后侧易位
            else:
                self.board[fx][fy] = None
                self.board[fx][fy-2] = piece
                self.board[fx][fy-1] = self.board[fx][fy-4]
                self.board[fx][fy-4] = None
            self.castling_rights[player+'K'] = False
            self.castling_rights[player+'Q'] = False
        # 判断吃过路兵
        elif piece and piece[1] == 'P' and self.en_passant and (tx, ty) == self.en_passant and abs(fy - ty) == 1 and abs(fx - tx) == 1 and self.get_piece(tx, ty) is None:
            self.board[tx][ty] = piece
            self.board[fx][fy] = None
            self.board[fx][ty] = None  # 吃掉对方兵
        # 升变
        elif move.get('promotion'):
            self.board[tx][ty] = player + move['promotion']
            self.board[fx][fy] = None
        # 普通走法
        else:
            self.board[tx][ty] = piece
            self.board[fx][fy] = None
        self.last_move = move
        self.move_history.append(move)
        # 更新易位权
        if piece[1] == 'K':
            self.castling_rights[player+'K'] = False
            self.castling_rights[player+'Q'] = False
        if piece[1] == 'R':
            if fy == 0:
                self.castling_rights[player+'Q'] = False
            elif fy == 7:
                self.castling_rights[player+'K'] = False
        # 更新en_passant
        if piece[1] == 'P' and abs(tx - fx) == 2:
            self.en_passant = ((fx + tx)//2, fy)
        else:
            self.en_passant = None
        # 有吃必吃模式下，谁先无子谁赢
        if self.must_capture:
            w_count = sum(1 for x in range(8) for y in range(8) if self.get_piece(x, y) and self.get_piece(x, y)[0] == 'w')
            b_count = sum(1 for x in range(8) for y in range(8) if self.get_piece(x, y) and self.get_piece(x, y)[0] == 'b')
            if w_count == 0:
                self.game_over = True
                self.winner = 'w'
            elif b_count == 0:
                self.game_over = True
                self.winner = 'b'
        else:
            # 走完后判断对方是否被将死或无子可动
            next_player = 'b' if player == 'w' else 'w'
            legal_moves = self.generate_legal_moves(next_player)
            # 可选缓存下一步合法走法
            # self.next_legal_moves = legal_moves
            if not legal_moves:
                if self.is_in_check(next_player):
                    self.game_over = True
                    self.winner = player
                else:
                    self.game_over = True
                    self.winner = None  # 和棋
        if not self.game_over:
            self.current_player = 'b' if player == 'w' else 'w'
        # 走棋后记录局面哈希
        pos_hash = self.get_position_hash()
        self.position_history.append(pos_hash)
        repeat_count = self.position_history.count(pos_hash)
        repeat_draw = False
        if repeat_count >= 3:
            self.game_over = True
            self.winner = None
            repeat_draw = True
        return {
            'success': True,
            'msg': '',
            'repeat_count': repeat_count,
            'repeat_draw': repeat_draw,
            'game_over': self.game_over,
            'winner': self.winner,
            'is_draw': self.game_over and self.winner is None
        }

    def is_legal_move(self, move):
        return any(self._move_eq(move, m) for m in self.generate_legal_moves(self.current_player))

    def _move_eq(self, m1, m2):
        keys = ['from', 'to', 'promotion']
        return all(m1.get(k) == m2.get(k) for k in keys)

    def is_path_clear(self, from_x, from_y, to_x, to_y):
        # 检查(from_x, from_y)到(to_x, to_y)之间是否无阻挡
        dx = to_x - from_x
        dy = to_y - from_y
        step_x = (dx > 0) - (dx < 0)
        step_y = (dy > 0) - (dy < 0)
        x, y = from_x + step_x, from_y + step_y
        while (x, y) != (to_x, to_y):
            if self.get_piece(x, y):
                return False
            x += step_x
            y += step_y
        return True

    def is_checkmate(self, player):
        # 简化：只判定王是否被吃
        for i in range(8):
            for j in range(8):
                p = self.get_piece(i, j)
                if p == player + 'K':
                    return False
        return True

    def to_dict(self):
        return {
            'board': self.board,
            'current_player': self.current_player,
            'game_over': self.game_over,
            'winner': self.winner,
            'last_move': self.last_move,
            'move_history': self.move_history,
            'castling_rights': self.castling_rights,
            'en_passant': self.en_passant,
            'must_capture': self.must_capture,
            'position_history': self.position_history,
        }

    @classmethod
    def from_dict(cls, data):
        obj = cls(must_capture=data.get('must_capture', False))
        obj.board = data.get('board', [row[:] for row in START_BOARD])
        obj.current_player = data.get('current_player', 'w')
        obj.game_over = data.get('game_over', False)
        obj.winner = data.get('winner', None)
        lm = data.get('last_move')
        if isinstance(lm, dict) and 'from' in lm and 'to' in lm:
            obj.last_move = {
                'from': tuple(int(x) for x in lm['from']),
                'to': tuple(int(x) for x in lm['to']),
                **{k: v for k, v in lm.items() if k not in ('from', 'to')}
            }
        elif isinstance(lm, list) and len(lm) == 2:
            obj.last_move = {'from': tuple(int(x) for x in lm[0]), 'to': tuple(int(x) for x in lm[1])}
        else:
            obj.last_move = None
        obj.move_history = []
        for m in data.get('move_history', []):
            if isinstance(m, dict) and 'from' in m and 'to' in m:
                obj.move_history.append({
                    'from': tuple(int(x) for x in m['from']),
                    'to': tuple(int(x) for x in m['to']),
                    **{k: v for k, v in m.items() if k not in ('from', 'to')}
                })
            elif isinstance(m, list) and len(m) == 2:
                obj.move_history.append({'from': tuple(int(x) for x in m[0]), 'to': tuple(int(x) for x in m[1])})
        obj.castling_rights = data.get('castling_rights', {'wK': True, 'wQ': True, 'bK': True, 'bQ': True})
        obj.en_passant = tuple(data.get('en_passant')) if data.get('en_passant') else None
        obj.position_history = data.get('position_history', [])
        return obj

    def draw_board(self, path=None):
        cell_size = 60
        margin = 40
        board_pixel = cell_size * 8 + margin * 2
        img = Image.new('RGB', (board_pixel, board_pixel), (240, 217, 181))
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype('fonts/SourceHanSerif-VF.ttf.ttc', 32)
        small_font = ImageFont.truetype('fonts/SourceHanSerif-VF.ttf.ttc', 18)
        # 画格子
        for i in range(8):
            for j in range(8):
                color = (181, 136, 99) if (i + j) % 2 == 1 else (200, 177, 141)
                x0 = margin + j * cell_size
                y0 = margin + i * cell_size
                x1 = x0 + cell_size
                y1 = y0 + cell_size
                draw.rectangle([x0, y0, x1, y1], fill=color)
        # 画棋子
        for i in range(8):
            for j in range(8):
                piece = self.get_piece(i, j)
                if piece:
                    if piece[0] == 'w':
                        text = PIECE_NAMES[piece[1].upper()]
                        color = (255, 255, 255)
                    else:
                        text = PIECE_NAMES[piece[1].lower()]
                        color = (0, 0, 0)
                    x = margin + j * cell_size + cell_size // 2
                    y = margin + i * cell_size + cell_size // 2
                    draw.text((x-16, y-20), text, fill=color, font=font)
                    draw.text((x-16, y-20), text, fill=color, font=font) # 画两次，加粗

        # 标记最后一步
        if self.last_move:
            to_x, to_y = self.last_move['to']
            x = margin + to_y * cell_size + cell_size // 2
            y = margin + to_x * cell_size + cell_size // 2
            r = cell_size // 3
            draw.ellipse([x - r, y - r, x + r, y + r], outline=(255, 0, 0), width=3)
        # 画坐标
        for i in range(8):
            # 上下
            draw.text((margin + i * cell_size + 20, margin - 30), chr(ord('a') + i), fill=(0, 0, 0), font=small_font)
            draw.text((margin + i * cell_size + 20, board_pixel - margin + 10), chr(ord('a') + i), fill=(0, 0, 0), font=small_font)
            # 左右
            draw.text((margin - 30, margin + i * cell_size + 20), str(8 - i), fill=(0, 0, 0), font=small_font)
            draw.text((board_pixel - margin + 10, margin + i * cell_size + 20), str(8 - i), fill=(0, 0, 0), font=small_font)
        if path is None:
            path = '/tmp/chess_board.png'
        img.save(path)
        return path

    def is_capture_move(self, move, player):
        tx, ty = move['to']
        fx, fy = move['from']
        piece = self.get_piece(fx, fy)
        target = self.get_piece(tx, ty)
        # 普通吃子
        if target and target[0] != player:
            return True
        # 吃过路兵
        if piece and piece[1] == 'P' and self.en_passant and (tx, ty) == self.en_passant and abs(fy - ty) == 1 and abs(fx - tx) == 1 and target is None:
            return True
        return False

    def is_in_check(self, player):
        # 判断player是否被将军
        # 找到王的位置
        king_pos = None
        for i in range(8):
            for j in range(8):
                if self.get_piece(i, j) == player + 'K':
                    king_pos = (i, j)
                    break
            if king_pos:
                break
        if not king_pos:
            return True  # 王已被吃
        # 检查对方所有走法是否能吃到王
        opp = 'b' if player == 'w' else 'w'
        for i in range(8):
            for j in range(8):
                piece = self.get_piece(i, j)
                if piece and piece[0] == opp:
                    moves = self._piece_moves(i, j, opp, piece[1])
                    for m in moves:
                        if m['to'] == king_pos:
                            return True
        return False

    def _piece_moves(self, i, j, player, kind):
        # 只生成(i,j)这个棋子的所有伪合法走法（不考虑送王）
        moves = []
        if kind == 'P':
            direction = -1 if player == 'w' else 1
            start_row = 6 if player == 'w' else 1
            # 前进一步
            x, y = i + direction, j
            if self.in_board(x, y) and not self.get_piece(x, y):
                # 升变
                if x == 0 or x == 7:
                    for promo in ['Q', 'R', 'B', 'N']:
                        moves.append({'from': (i, j), 'to': (x, y), 'promotion': promo})
                else:
                    moves.append({'from': (i, j), 'to': (x, y)})
                # 首次前进两步
                if i == start_row:
                    x2 = i + 2 * direction
                    if self.in_board(x2, y) and not self.get_piece(x2, y):
                        moves.append({'from': (i, j), 'to': (x2, y)})
            # 吃子
            for dy in [-1, 1]:
                x, y2 = i + direction, j + dy
                if self.in_board(x, y2):
                    target = self.get_piece(x, y2)
                    if target and target[0] != player:
                        if x == 0 or x == 7:
                            for promo in ['Q', 'R', 'B', 'N']:
                                moves.append({'from': (i, j), 'to': (x, y2), 'promotion': promo})
                        else:
                            moves.append({'from': (i, j), 'to': (x, y2)})
            # 吃过路兵
            if self.en_passant:
                ep_x, ep_y = self.en_passant
                if abs(ep_y - j) == 1 and ep_x == i + direction:
                    moves.append({'from': (i, j), 'to': (ep_x, ep_y)})
        elif kind == 'N':  # 马
            for dx, dy in [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]:
                x, y = i + dx, j + dy
                if self.in_board(x, y):
                    target = self.get_piece(x, y)
                    if not target or target[0] != player:
                        moves.append({'from': (i, j), 'to': (x, y)})
        elif kind == 'B':  # 象
            for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                for step in range(1, 8):
                    x, y = i + dx * step, j + dy * step
                    if not self.in_board(x, y):
                        break
                    target = self.get_piece(x, y)
                    if not target:
                        moves.append({'from': (i, j), 'to': (x, y)})
                    elif target[0] != player:
                        moves.append({'from': (i, j), 'to': (x, y)})
                        break
                    else:
                        break
        elif kind == 'R':  # 车
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                for step in range(1, 8):
                    x, y = i + dx * step, j + dy * step
                    if not self.in_board(x, y):
                        break
                    target = self.get_piece(x, y)
                    if not target:
                        moves.append({'from': (i, j), 'to': (x, y)})
                    elif target[0] != player:
                        moves.append({'from': (i, j), 'to': (x, y)})
                        break
                    else:
                        break
        elif kind == 'Q':  # 后
            for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                for step in range(1, 8):
                    x, y = i + dx * step, j + dy * step
                    if not self.in_board(x, y):
                        break
                    target = self.get_piece(x, y)
                    if not target:
                        moves.append({'from': (i, j), 'to': (x, y)})
                    elif target[0] != player:
                        moves.append({'from': (i, j), 'to': (x, y)})
                        break
                    else:
                        break
        elif kind == 'K':  # 王
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    x, y = i + dx, j + dy
                    if self.in_board(x, y):
                        target = self.get_piece(x, y)
                        if not target or target[0] != player:
                            moves.append({'from': (i, j), 'to': (x, y)})
            # 王车易位
            if self.castling_rights[player+'K']:
                if all(self.get_piece(i, y) is None for y in range(j+1, 7)):
                    moves.append({'from': (i, j), 'to': (i, j+2)})
            if self.castling_rights[player+'Q']:
                if all(self.get_piece(i, y) is None for y in range(1, j)):
                    moves.append({'from': (i, j), 'to': (i, j-2)})
        return moves

    def _would_be_in_check(self, player, move):
        # 判断执行move后player是否被将军
        import copy
        tmp = copy.deepcopy(self)
        fx, fy = move['from']
        tx, ty = move['to']
        piece = tmp.get_piece(fx, fy)
        tmp.board[tx][ty] = piece
        tmp.board[fx][fy] = None
        if 'promotion' in move:
            tmp.board[tx][ty] = player + move['promotion']
        return tmp.is_in_check(player)

    def generate_legal_moves(self, player):
        # 生成所有合法走法
        all_moves = []
        for i in range(8):
            for j in range(8):
                piece = self.get_piece(i, j)
                if piece and piece[0] == player:
                    kind = piece[1]
                    pseudo_moves = self._piece_moves(i, j, player, kind)
                    if self.must_capture:
                        # 有吃必吃模式下，后续过滤吃子
                        all_moves.extend(pseudo_moves)
                    else:
                        # 普通模式下，过滤送王
                        for move in pseudo_moves:
                            if not self._would_be_in_check(player, move):
                                all_moves.append(move)
        if self.must_capture:
            capture_moves = [m for m in all_moves if self.is_capture_move(m, player)]
            if capture_moves:
                # 有吃必吃模式下，如果有得吃，则只返回吃子走法
                return capture_moves
        return all_moves

class ChessBot(ChessGameBase):
    def __init__(self):
        super().__init__('chess', '681710445ebf6e703ce2a0ed')

    async def send_board_image(self, game, room_id, msg):
        img_path = f"tmp/chess_{room_id}.png"
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
            must_capture = False
            if len(text.split()) > 1:
                config = text[2:].strip()
                if '吃' in config:
                    must_capture = True
            room_id = self.new_room_id()
            self.rooms[room_id] = {
                'game': ChessGame(must_capture=must_capture),
                'players': [{'id': user_id, 'name': msg.talker_name}],
                'status': 'waiting',
                'draw_offer': None
            }
            self.user_room[user_id] = room_id
            if must_capture:
                await msg.reply(f"房间已创建（有吃必吃模式），房间号: {room_id}，等待其他玩家加入。")
            else:
                await msg.reply(f"房间已创建，房间号: {room_id}，等待其他玩家加入。")
        # 加入
        elif text.startswith('加入'):
            room_id = text[2:].strip()
            if not room_id:
                await msg.reply("加哪儿啊？发送【加入 房间号】，例如: 加入 1000")
                return
            if room_id not in self.rooms:
                await msg.reply("没有这个房间号。")
                return
            room = self.rooms[room_id]
            if user_id in [p['id'] for p in room['players']]:
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
                # 随机决定谁白
                random.shuffle(room['players'])
                response = f"加入房间{room_id}成功。游戏开始！{room['players'][0]['name']}先手。"
                room['status'] = 'playing'
                await msg.reply(response)
                await self.send_board_image(room['game'], room_id, msg)
            else:
                await msg.reply(f"加入房间{room_id}成功，等待对手加入！")
        # 求和
        elif text == '求和':
            if user_id not in self.user_room:
                await msg.reply("你当前不在任何房间。"); return
            room_id = self.user_room[user_id]
            room = self.rooms.get(room_id)
            if not room or room['status'] != 'playing':
                await msg.reply("房间未开始游戏。"); return
            idx = [p['id'] for p in room['players']].index(user_id)
            player = 'w' if idx == 0 else 'b'
            if room['game'].current_player != player:
                await msg.reply("还没轮到你下棋。"); return
            if room.get('draw_offer'):
                await msg.reply("你已经提出过和棋申请，等待对方回应。"); return
            room['draw_offer'] = player
            await msg.reply(f"你已向对方提出和棋申请，请对方回复【同意】或【拒绝】。"); return
        # 同意
        elif text == '同意':
            if user_id not in self.user_room:
                await msg.reply("你当前不在任何房间。"); return
            room_id = self.user_room[user_id]
            room = self.rooms.get(room_id)
            if not room or room['status'] != 'playing':
                await msg.reply("房间未开始游戏。"); return
            idx = [p['id'] for p in room['players']].index(user_id)
            player = 'w' if idx == 0 else 'b'
            if not room.get('draw_offer') or room['draw_offer'] == player:
                await msg.reply("当前没有对方提出的和棋申请。"); return
            room['status'] = 'finished'
            room['game'].game_over = True
            room['game'].winner = None
            await msg.reply("双方同意和棋，游戏结束。")
            self.archive_game(room, room_id)
            return
        # 拒绝
        elif text == '拒绝':
            if user_id not in self.user_room:
                await msg.reply("你当前不在任何房间。"); return
            room_id = self.user_room[user_id]
            room = self.rooms.get(room_id)
            if not room or room['status'] != 'playing':
                await msg.reply("房间未开始游戏。"); return
            idx = [p['id'] for p in room['players']].index(user_id)
            player = 'w' if idx == 0 else 'b'
            if not room.get('draw_offer') or room['draw_offer'] == player:
                await msg.reply("当前没有对方提出的和棋申请。"); return
            room['draw_offer'] = None
            await msg.reply("你已拒绝和棋申请，继续游戏。"); return
        # 落子
        elif re.match(r'^[a-h][1-8][a-h][1-8][qrbn]?$', text.replace(' ', '').lower()):
            if user_id not in self.user_room:
                await msg.reply("你当前不在任何房间，请先'开房'或'加入 房间号'。")
                return
            room_id = self.user_room[user_id]
            room = self.rooms.get(room_id)
            if not room or room['status'] != 'playing':
                await msg.reply("房间未开始游戏。"); return
            # 如果有和棋申请，且不是自己提出的，不能走棋
            if room.get('draw_offer') and [p['id'] for p in room['players']].index(user_id) != (0 if room['draw_offer']=='w' else 1):
                await msg.reply("对方提出了和棋申请，请先回复【同意】或【拒绝】。"); return
            game = room['game']
            idx = [p['id'] for p in room['players']].index(user_id)
            player = 'w' if idx == 0 else 'b'
            if game.current_player != player:
                await msg.reply("还没轮到你下棋。"); return
            move = parse_move_from_text(text, game)
            if not move:
                await msg.reply("落子格式错误，应为: a2a4 或 a7a8Q")
                return
            # 走棋前清除和棋申请
            room['draw_offer'] = None
            response = game.move(move)
            if not response['success']:
                await msg.reply(response['msg'])
                return
            if response.get('repeat_count') == 2:
                await msg.reply("警告：当前局面已出现两次，再次出现将自动判和！")
            if response.get('repeat_draw'):
                await msg.reply("三次重复局面，自动判和，游戏结束。")
                await self.send_board_image(game, room_id, msg)
                room['status'] = 'finished'
                self.archive_game(room, room_id)
                return
            if game.game_over:
                winner = '白方' if game.winner == 'w' else '黑方' if game.winner else '和棋'
                await msg.reply(f"{winner}胜利！游戏结束。" if game.winner else "和棋，游戏结束。")
                await self.send_board_image(game, room_id, msg)
                room['status'] = 'finished'
                self.archive_game(room, room_id)
            else:
                next_player = room['players'][0 if game.current_player == 'w' else 1]
                color = '白方' if game.current_player == 'w' else '黑方'
                await msg.reply(f"落子成功，轮到{next_player['name']}（{color}）。")
                await self.send_board_image(game, room_id, msg)
        # 查看棋盘
        elif text in ['棋盘', 'board']:
            if user_id not in self.user_room:
                await msg.reply("你当前不在任何房间。"); return
            room_id = self.user_room[user_id]
            room = self.rooms.get(room_id)
            if not room:
                await msg.reply("房间不存在。"); return
            await self.send_board_image(room['game'], room_id, msg)
        elif text.lower() in ['说明', 'help', '帮助']:
            await msg.reply("【开房】\n【开房 吃】有吃必吃\n【加入 xxxx】加入某个房间\n【棋盘】查看当前棋盘\n【求和】向对方提出和棋申请\n【同意/拒绝】同意/拒绝和棋\n走棋用起点终点坐标，例如a2a4\n升变：a7a8Q\n王车易位：直接指定王的起点终点坐标")
        else:
            pass
            # await msg.reply("指令无效。支持：\n开房\n加入 房间号\n[a2 a4]走法\n棋盘 查看棋盘")

    def room_to_dict(self, room):
        # 兼容新老格式，序列化draw_offer
        d = {
            'game': room['game'].to_dict(),
            'players': room['players'],
            'status': room['status'],
            'draw_offer': room.get('draw_offer', None)
        }
        return d

    def dict_to_room(self, data):
        # 兼容新老格式，反序列化draw_offer
        room = {
            'game': ChessGame.from_dict(data['game']),
            'players': data['players'],
            'status': data['status'],
            'draw_offer': data.get('draw_offer', None)
        }
        return room

def parse_move_from_text(text, game):
    # 支持 a7a8Q, a7a8, a7 a8 Q, a7 a8q, a7a8q 等格式
    text = text.replace(' ', '').lower()
    m = re.match(r'^([a-h][1-8])([a-h][1-8])([qrbn])?$', text)
    if not m:
        return None
    from_sq, to_sq, promo = m.groups()
    from_x, from_y = 8 - int(from_sq[1]), ord(from_sq[0]) - ord('a')
    to_x, to_y = 8 - int(to_sq[1]), ord(to_sq[0]) - ord('a')
    move = {'from': (from_x, from_y), 'to': (to_x, to_y)}
    if promo:
        move['promotion'] = promo.upper()
    return move
