import asyncio
import json
import logging
import traceback
from typing import Optional, Dict, Any
import aiohttp
import websockets
import os

from message import Message
# import bots
from bots.gomoku import GomokuBot
# 未来可以 from bots.chess import ChessBot 等

# 初始化bot们
gomoku_bot = GomokuBot()
# chess_bot = ChessBot()  # 未来可拓展

# 维护 channel_id 到 bot 的映射
channel_bot_map = {
    '6815cd855ebf6e703ce29395': gomoku_bot,
    # 'chess': chess_bot,
}

# 设置日志格式
log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')

# 控制台处理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

# 文件处理器
file_handler = logging.FileHandler('rocket.log', encoding='utf-8')
file_handler.setFormatter(log_formatter)

# 获取 logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(console_handler)
logger.addHandler(file_handler)


class RocketChatBot:
    def __init__(self, user: str, password: str, server_url: str):
        self.user = user
        self.password = password
        self.server_url = server_url
        # HTTP URL 用于 REST API
        self.api_url = server_url
        # WebSocket URL
        self.ws_url = server_url.replace('http://', 'ws://').replace('https://', 'wss://') + '/websocket'
        self.token: Optional[str] = None
        self.user_id: Optional[str] = None
        
        logger.debug(f"API URL: {self.api_url}")
        logger.debug(f"WebSocket URL: {self.ws_url}")


    async def login(self) -> None:
        """登录获取 token"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'{self.api_url}/api/v1/login',  # 使用 api_url
                    json={'username': self.user, 'password': self.password}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.token = data['data']['authToken']
                        self.user_id = data['data']['userId']
                        logger.info(f'Login successful. Token: {self.token[:10]}...')
                    else:
                        text = await response.text()
                        logger.error(f'Login failed: {text}')
                        raise Exception(f'Login failed: {text}')
        except Exception as e:
            logger.error(f'Login error: {e}')
            raise

    async def send_message(self, room_id: str, text: str) -> None:
        """发送消息"""
        async with aiohttp.ClientSession() as session:
            headers = {
                'X-Auth-Token': self.token,
                'X-User-Id': self.user_id
            }
            async with session.post(
                f'{self.api_url}/api/v1/chat.postMessage',  # 使用 api_url
                headers=headers,
                json={'roomId': room_id, 'text': text}
            ) as response:
                if response.status != 200:
                    logger.error(f'Failed to send message: {await response.text()}')

    async def send_image(self, room_id: str, image_path: str, description: str = None) -> None:
        """发送图片消息到指定房间"""
        # 1. 上传图片
        async with aiohttp.ClientSession() as session:
            headers = {
                'X-Auth-Token': self.token,
                'X-User-Id': self.user_id
            }
            files = {'file': open(image_path, 'rb')}
            data = aiohttp.FormData()
            data.add_field('file', open(image_path, 'rb'), filename=os.path.basename(image_path), content_type='image/png')
            async with session.post(
                f'{self.api_url}/api/v1/rooms.upload/{room_id}',
                headers=headers,
                data=data
            ) as response:
                if response.status != 200:
                    logger.error(f'Failed to upload image: {await response.text()}')
                    return
                res_json = await response.json()
                if description:
                    # 2. 发送一条带描述的消息
                    await self.send_message(room_id, description)

    async def handle_message(self, message: Dict[str, Any]) -> None:
        """处理收到的消息"""
        try:
            # 忽略自己发的
            if message.get('u', {}).get('username') == self.user:
                return
            logger.info(f"Received message: {message}")
            msg = Message(message, self)

            # 测试ding-dong
            if msg.text == 'ding':
                async def send_ding():
                    await msg.reply('野猪开始拉屎')
                    await asyncio.sleep(5)
                    await msg.reply('野猪拉屎结束')
                asyncio.create_task(send_ding())

            # 分发到对应bot
            bot = channel_bot_map.get(msg.room_id)
            if bot:
                await bot.message_handler(msg)

        except Exception as e:
            logger.error(f'Error handling message: {e}')
            print(traceback.format_exc())

    async def connect(self) -> None:
        """建立 WebSocket 连接并处理消息"""
        try:
            await self.login()
            logger.debug(f"Attempting to connect to WebSocket at: {self.ws_url}")
            
            async with websockets.connect(
                self.ws_url,
                extra_headers={
                    'Origin': self.server_url,
                },
                subprotocols=['websocket']
            ) as websocket:
                logger.info("WebSocket connection established")

                # 发送连接消息
                connect_msg = {
                    "msg": "connect",
                    "version": "1",
                    "support": ["1"]
                }
                logger.debug(f"Sending connect message: {connect_msg}")
                await websocket.send(json.dumps(connect_msg))

                # 等待连接确认
                response = await websocket.recv()
                logger.debug(f"Received initial response: {response}")

                # 发送登录消息
                login_msg = {
                    "msg": "method",
                    "method": "login",
                    "id": "1",
                    "params": [
                        {"resume": self.token}
                    ]
                }
                logger.debug(f"Sending login message: {login_msg}")
                await websocket.send(json.dumps(login_msg))

                # 等待登录响应
                response = await websocket.recv()
                logger.debug(f"Received login response: {response}")

                # 订阅消息
                sub_msg = {
                    "msg": "sub",
                    "id": "2",
                    "name": "stream-room-messages",
                    "params": ["__my_messages__", False]
                }
                logger.debug(f"Sending subscription message: {sub_msg}")
                await websocket.send(json.dumps(sub_msg))

                # 持续接收消息
                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        logger.debug(f"Received message: {data}")
                        if data.get('msg') == 'changed' and data.get('collection') == 'stream-room-messages':
                            asyncio.create_task(self.handle_message(data['fields']['args'][0]))
                    except websockets.ConnectionClosed:
                        logger.warning("WebSocket connection closed")
                        break
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")

        except Exception as e:
            logger.error(f"Connection error: {e}")
            await asyncio.sleep(5)

    async def run(self) -> None:
        """运行机器人"""
        while True:
            try:
                await self.connect()
            except Exception as e:
                logger.error(f'Connection error: {e}')
                await asyncio.sleep(5)  # 出错后等待重连

def main():
    # 使用容器内部地址进行测试
    bot = RocketChatBot(
        user='rocket.cat',
        password='123456',
        server_url='http://localhost:3000'  # 这里保持 http://，构造函数会自动转换为 ws:// 
        # server_url='https://rocket.shadiao.win'
    )
    
    # 运行机器人
    asyncio.run(bot.run())

if __name__ == '__main__':
    main()