import asyncio
import discord
from discord.ext import commands
from config.config import Config
from logger.logger import Logger
from ollama.ollama import Llama

# logging stuff
file = '.log/discord.log'
msg = 'The discord bot has started'
Logger.cfg(file, Config.set_loglvl())
Logger.writter(msg)

token = Config.get_token()
itents = discord.Intents.default()
itents.members = True
itents.message_content = True
initial_extensions = ['commands.general']
bot = commands.Bot(command_prefix='?', description='Nebula AI interact with an LLM Model', intents=itents)

if __name__ == "__main__" :

    @bot.event
    async def on_ready():
       Logger.writter(f'Logged in as {bot.user} (ID: {bot.user.id})')
       for extension in initial_extensions:
        print("loading extensions")
        await bot.load_extension(extension)
       
    @bot.event
    async def on_message(message):
      if bot.user.mention in message.content.split():
         try:
            await message.channel.typing()
            msg = Llama.conn(message.content) #big brain llm messasges
            Logger.writter("ollama message length:" +  str(len(msg)) )
            await message.reply(msg)
         except discord.errors.HTTPException:
            await message.channel.typing()
            msg="I cant reply to that"
            await message.reply(msg)
      await bot.process_commands(message)
    async def main():
      async with bot:
         await bot.start(token)
    asyncio.run(main())
    