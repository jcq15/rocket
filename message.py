class Message:
    def __init__(self, message, bot):
        self.message = message
        self.bot = bot

        self.text = message.get('msg', '')
        self.room_id = message.get('rid')
        self.talker_id = message.get('u', {}).get('username')
        self.talker_name = message.get('u', {}).get('name')
        
    async def reply(self, text):
        await self.bot.send_message(self.room_id, text)
    
    async def reply_image(self, image_path, description=None):
        await self.bot.send_image(self.room_id, image_path, description)