import asyncio
import discord
from discord.ext import commands
from config.config import Config
from logger.logger import Logger
from PIL import Image
from ollama_custom.ollama import Llama
import requests
import base64
import shutil
# This is going to fail somewhere else
# logging stuff
Logger.cfg(Config.set_loglvl())
bot = commands.Bot(command_prefix='?', description='Nebula AI interact with an LLM Model', intents=Config.set_bot())


if __name__ == "__main__" :

    @bot.event
    async def on_ready():
       Logger.writter(f'Logged in as {bot.user} (ID: {bot.user.id})')
       for extension in Config.extensions():
        print("loading extensions")
        await bot.load_extension(extension)
       
    @bot.event
    async def on_message(message):
      if bot.user.mention in message.content.split():
         try:
            await message.channel.typing() #I like this feature 
            if not message.attachments:
               msg = Llama.conn(message.content, Config.get_model()) #big brain llm messages
               Logger.writter("ollama message length:" +  str(len(msg)) )
               await message.reply(msg)
            elif "image" in message.attachments[0].content_type:
                  reply = Llama.imgPrompt(message.content, message.attachments[0])
                  await message.reply(reply)
            else: 
               pass
         except discord.errors.HTTPException: #EXCEPTIONSSSSSS
            await message.channel.typing()
            msg="I cant reply to that"
            await message.reply(msg)
      await bot.process_commands(message)
    async def main():
      async with bot:
         await bot.start(Config.get_token())
    asyncio.run(main())