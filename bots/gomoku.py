import random
import re
import cv2
import numpy as np
import os
import json
from pathlib import Path
if __name__ == "__main__":
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chess_base import ChessGameBase

class GomokuGame:
    def __init__(self, forbidden_rule=False):
        self.board_size = (15, 15)
        self.board = [[0] * self.board_size[0] for _ in range(self.board_size[1])] # 0: 空, 1: 黑棋, 2: 白棋
        self.current_player = 1 # 1: 黑棋, 2: 白棋
        self.game_over = False
        self.winner = None
        self.last_move = None
        self.forbidden_rule = forbidden_rule
    
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
        # 禁手判断
        is_forbidden = False
        forbidden_type = ''
        win = False
        if self.forbidden_rule and player == 1:
            # 先假设落子
            self.board[x][y] = player
            win = self.check_win(player, x, y, exact_five=True)
            self.board[x][y] = 0
            forbidden_type = self.check_forbidden(x, y)
            if forbidden_type and not win:
                self.board[x][y] = 0
                return {'success': False, 'winner': 0, 'msg': f'黑方禁手[{forbidden_type}]，禁止落子！'}
        # 真正落子
        self.board[x][y] = player
        self.last_move = (player, x, y)
        if self.check_win(player, x, y):
            self.game_over = True
            self.winner = player
            return {'success': True, 'winner': player, 'msg': ''}
        elif self.is_full():
            self.game_over = True
            self.winner = 0
            return {'success': True, 'winner': 0, 'msg': '和棋，棋盘已满。'}
        else:
            self.current_player = 2 if player == 1 else 1
            return {'success': True, 'winner': 0, 'msg': ''}

    # 包含x,y，4个方向的最长连续个数，返回list，每个方向一个数
    def continuous_num(self, x, y, player):
        if self.board[x][y] != player:
            return [0, 0, 0, 0] # 如果x,y不是player，还连个锤子
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        counts = []
        for dx, dy in directions:
            count = 0
            for d in [1, -1]: # 1 正方向，-1 反方向
                nx, ny = x, y
                while True:
                    nx, ny = nx + dx * d, ny + dy * d
                    if 0 <= nx < self.board_size[0] and 0 <= ny < self.board_size[1] and self.board[nx][ny] == player:
                        count += 1
                    else:
                        break
            counts.append(count+1) # 包含x,y本身
        return counts
    
    def check_win(self, player, x, y, exact_five=False):
        # 检查8个方向，是否有连续5子
        counts = self.continuous_num(x, y, player)
        if exact_five:
            return 5 in counts
        else:
            return max(counts) >= 5
    
    def check_forbidden(self, x, y, depth=0): # False表示不禁手，否则返回禁手类型字符串
        # 检查禁手：双活三、双四、长连
        indent = '  ' * depth
        #print(f"{indent}check_forbidden: 检查({x},{y}) depth={depth}")
        temp = self.board[x][y]
        self.board[x][y] = 1 # 模拟落子
        counts = self.continuous_num(x, y, 1)
        if 5 in counts:
            result = False # 恰好成5，不禁手
            print(f"{indent}  -> 恰好成5，不禁手")
        elif max(counts) >= 6:
            result = '长连'
            print(f"{indent}  -> 长连")
        elif self.four_count(x, y) >= 2:
            print('four_count', self.four_count(x, y))
            result = '双四'
            print(f"{indent}  -> 双四")
        elif self.live_three_count(x, y, depth=depth+1) >= 2:
            result = '双活三'
            print(f"{indent}  -> 双活三")
        else:
            result = False
            print(f"{indent}  -> 非禁手")
        self.board[x][y] = temp # 恢复
        return result
    
    # 沿一条直线，判断黑棋在x,y落子后，能形成几个四
    def four_count_one_line(self, x, y, dx, dy):
        zero_position = None # 记录能成5的0的位置，最后再看一下是否有两个0间隔4，如果有则说明是活四，而不是双死四
        all_four_count = 0
        live_four_count = 0
        # 每个方向
        for d in [1, -1]:
            for i in range(1, 5): # 往前最多看4个，1, 2, 3, 4
                nx, ny = x + dx * i * d, y + dy * i * d
                if 0 <= nx < self.board_size[0] and 0 <= ny < self.board_size[1]:
                    if self.board[nx][ny] == 0:
                        # 找到空白，判断填上后是否恰好成5
                        temp = self.board[nx][ny]
                        self.board[nx][ny] = 1
                        counts = self.continuous_num(nx, ny, 1)
                        if 5 in counts:
                            all_four_count += 1
                            # 正方向记录0的位置，反方向时查找是否有记录且间隔4（距离5）
                            if d == 1:
                                zero_position = i
                            else:
                                if zero_position is not None and zero_position + i == 5:
                                    # 活四
                                    live_four_count += 1
                                    all_four_count -= 1 # 如果是活四，死四会被多算一次
                                else:
                                    pass # 无事发生
                        self.board[nx][ny] = temp # 恢复
                        break # 找到空白，可以停止
                    elif self.board[nx][ny] == 2:
                        break # 遇到白棋，可以停止
                else:
                    break # 越界，可以停止
        return all_four_count, live_four_count

    # 黑在x,y落子后成了几个四（all_four_count），几个活四（live_four_count）
    def four_count(self, x, y):
        # 8个方向查找，看到0则判断：如果把这个0填上，是否恰好成5，然后停止当前方向查找
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        all_four_count = 0
        live_four_count = 0
        for dx, dy in directions:
            all_four_count_one_line, live_four_count_one_line = self.four_count_one_line(x, y, dx, dy)
            all_four_count += all_four_count_one_line
            live_four_count += live_four_count_one_line
        # return all_four_count, live_four_count
        return all_four_count # 只返回all_four_count

    def live_three_count(self, x, y, depth=0):
        indent = '  ' * depth
        # print(f"{indent}live_three_count: 检查({x},{y}) depth={depth}")
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)] # 4条直线
        live_three_count = 0
        for dx, dy in directions:
            flag = False # 一个方向最多一个活三，找到就换下一个方向
            # 每个方向
            for d in [1, -1]:
                if flag:
                    break
                for i in range(1, 4): # 往前最多看3个，1, 2, 3
                    if flag:
                        break
                    nx, ny = x + dx * i * d, y + dy * i * d
                    if 0 <= nx < self.board_size[0] and 0 <= ny < self.board_size[1]:
                        if self.board[nx][ny] == 0:
                            # 找到空白，然后：
                            # 1.判断填上后是否恰好成活四，如果是，说明是形式活三
                            temp = self.board[nx][ny]
                            self.board[nx][ny] = 1
                            # 只需要live_four_count
                            _, live_four_count = self.four_count_one_line(nx, ny, dx, dy)
                            self.board[nx][ny] = temp # 恢复
                            if live_four_count >= 1:
                                # 2. 判断该点是否禁手
                                if not self.check_forbidden(nx, ny, depth=depth+1):
                                    live_three_count += 1
                                    flag = True
                                    print(f"{indent}  -> 方向({dx},{dy}) {d}步{i} 形成活三")
                            break # 找到空白，可以停止
                        elif self.board[nx][ny] == 2:
                            break # 遇到白棋，可以停止
                    else:
                        break # 越界，可以停止
        print(f"{indent}live_three_count: ({x},{y}) 结果={live_three_count}")
        return live_three_count
    
    def is_full(self):
        for row in self.board:
            if 0 in row:
                return False
        return True

    def get_board_str(self):
        # 横坐标1~15，纵坐标A~O
        numbers = [str(i+1) for i in range(self.board_size[1])]
        letters = [chr(ord('A') + i) for i in range(self.board_size[0])]
        board_str = '   ' + ' '.join(numbers) + '\n'
        for i in range(self.board_size[0]):
            board_str += f'{letters[i]:2s} ' + ' '.join([str(cell) for cell in self.board[i]]) + '\n'
        return board_str

    def draw_board(self, path=None):
        cell_size = 40
        margin = 40
        board_pixel = cell_size * (self.board_size[1] - 1) + margin * 2
        img = np.ones((board_pixel, board_pixel, 3), dtype=np.uint8) * 240
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        thickness = 1
        # 画网格线（交替颜色）
        for i in range(self.board_size[0]):
            color = (0, 0, 0) if i % 2 == 0 else (180, 180, 180)
            pt1 = (margin, margin + i * cell_size)
            pt2 = (margin + cell_size * (self.board_size[1] - 1), margin + i * cell_size)
            cv2.line(img, pt1, pt2, color, 1)
        for j in range(self.board_size[1]):
            color = (0, 0, 0) if j % 2 == 0 else (180, 180, 180)
            pt1 = (margin + j * cell_size, margin)
            pt2 = (margin + j * cell_size, margin + cell_size * (self.board_size[0] - 1))
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
        numbers = [str(i+1) for i in range(self.board_size[1])]
        letters = [chr(ord('A') + i) for i in range(self.board_size[0])]
        for j in range(self.board_size[1]):
            # 上
            cv2.putText(img, numbers[j], (margin + j * cell_size - 8, margin - 10), font, font_scale, (0, 0, 200), thickness, cv2.LINE_AA)
            # 下
            cv2.putText(img, numbers[j], (margin + j * cell_size - 8, board_pixel - margin + 25), font, font_scale, (0, 0, 200), thickness, cv2.LINE_AA)
        for i in range(self.board_size[0]):
            # 左
            cv2.putText(img, letters[i], (margin - 30, margin + i * cell_size + 8), font, font_scale, (0, 0, 200), thickness, cv2.LINE_AA)
            # 右
            cv2.putText(img, letters[i], (board_pixel - margin + 10, margin + i * cell_size + 8), font, font_scale, (0, 0, 200), thickness, cv2.LINE_AA)
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
            'forbidden_rule': self.forbidden_rule,
        }

    @classmethod
    def from_dict(cls, data):
        obj = cls(data.get('forbidden_rule', False))
        obj.board_size = tuple(data.get('board_size', (15, 15)))
        obj.board = data.get('board', [[0]*15 for _ in range(15)])
        obj.current_player = data.get('current_player', 1)
        obj.game_over = data.get('game_over', False)
        obj.winner = data.get('winner', None)
        obj.last_move = tuple(data.get('last_move')) if data.get('last_move') else None
        obj.forbidden_rule = data.get('forbidden_rule', False)
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
            forbidden = '禁' in text
            room_id = self.new_room_id()
            self.rooms[room_id] = {
                'game': GomokuGame(forbidden_rule=forbidden),
                'players': [{'id': user_id, 'name': msg.talker_name}],
                'status': 'waiting',
            }
            self.user_room[user_id] = room_id
            if forbidden:
                await msg.reply(f"房间已创建（带禁手），房间号: {room_id}，等待其他玩家加入。")
            else:
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
        elif re.match(r'^[A-Oa-o](1[0-5]|[1-9])$', text.strip()):
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
                row = text[0].upper()
                col = int(text[1:])
                x = ord(row) - ord('A')
                y = col - 1
            except Exception:
                await msg.reply("落子格式错误，应为: A1 ~ O15")
                return
            response = game.move(player, x, y)
            if not response['success']:
                await msg.reply(response['msg'])
                return
            # 落子成功
            await self.send_board_image(game, room_id, msg)
            if response['winner'] == 1 or response['winner'] == 2:
                winner = '黑棋' if response['winner'] == 1 else '白棋'
                response_msg = f"{winner}胜利！游戏结束。"
                room['status'] = 'finished'
                self.archive_game(room, room_id)
                await msg.reply(response_msg)
            elif response['winner'] == 0 and game.game_over:
                response_msg = "和棋，棋盘已满，游戏结束。"
                room['status'] = 'finished'
                self.archive_game(room, room_id)
                await msg.reply(response_msg)
            else:
                next_player = room['players'][game.current_player-1]
                color = '黑棋' if game.current_player == 1 else '白棋'
                await msg.reply(f"落子成功，轮到{next_player['name']}。")

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

if __name__ == "__main__":
    # 测试禁手规则
    # 0空1黑2白
    board = [[0]*15 for _ in range(15)]
    board[8][3] = 1
    board[7][1] = 1
    board[7][2] = 1
    board[7][5] = 0
    board[10][3] = 1
    board[9][0] = 1
    board[9][1] = 1
    board[9][2] = 1
    board[9][4] = 1
    board[9][5] = 1
    game = GomokuGame(forbidden_rule=True)
    game.board = board
    forbidden_points = []
    for x in range(15):
        for y in range(15):
            if game.board[x][y] == 0:
                # game.board[x][y] = 1
                # 检查黑方在(x, y)落子是否禁手
                forbidden_type = game.check_forbidden(x, y)
                if forbidden_type:
                    forbidden_points.append((x, y, forbidden_type))
    # 打印棋盘
    print("当前棋盘：")
    letters = [chr(ord('A') + i) for i in range(15)]
    print('   ' + ' '.join([str(i+1) for i in range(15)]))
    for i in range(15):
        print(f'{letters[i]:2s} ' + ' '.join(str(cell) for cell in board[i]))
    # 打印禁手点
    print("禁手点（行列/类型）：")
    for x, y, t in forbidden_points:
        print(f"{letters[x]}{y+1} : {t}")
