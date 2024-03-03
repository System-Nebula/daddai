import asyncio
import discord
from discord.ext import commands
from config.config import Config
from logger.logger import Logger
from PIL import Image
import ollama
import requests
import base64
import shutil

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
            if "image" in message.attachments[0].content_type:
              Logger.writter(f'url is {message.attachments[0].url}')
              response = requests.get(message.attachments[0].url, stream=True) # download img??
              MAGIC_STATIC_VAR = "insert_fn.png"
              leprompt = message.content
              with open(MAGIC_STATIC_VAR, 'wb')  as out_file:
                shutil.copyfileobj(response.raw, out_file)

              del response
              
              img = Image.open(MAGIC_STATIC_VAR).convert("RGB")
              img.save(MAGIC_STATIC_VAR, "png")

              with open(MAGIC_STATIC_VAR, 'rb') as file:
                response = ollama.chat(
                  model='llava',
                  messages=[
                    {
                      'role': 'user',
                      'content': leprompt,
                      'images': [file.read()],
                    },
                  ],
                )
                await message.reply(response['message']['content'])
                print(response['message']['content'])    
            else: 
                msg = Llama.conn(message.content, Config.get_model()) #big brain llm messages
                Logger.writter("ollama message length:" +  str(len(msg)) )
                await message.reply(msg)
         except discord.errors.HTTPException: #EXCEPTIONSSSSSS
            await message.channel.typing()
            msg="I cant reply to that"
            await message.reply(msg)
      await bot.process_commands(message)
    async def main():
      async with bot:
         await bot.start(Config.get_token())
    asyncio.run(main())
