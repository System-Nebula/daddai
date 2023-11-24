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

if __name__ == "__main__" :
    token = Config.get_token()
    itents = discord.Intents.default()
    itents.members = True
    itents.message_content = True
    bot = commands.Bot(command_prefix='?', description='Test', intents=itents)
    @bot.event
    async def on_ready():
       Logger.writter(f'Logged in as {bot.user} (ID: {bot.user.id})')
       
    @bot.event
    async def on_message(message):
      if bot.user.mention in message.content.split():
         try:
            msg = Llama.conn(message.content) #big brain llm messasges
            Logger.writter("ollama message length:" +  str(len(msg)) )
            await message.reply(msg)
         except discord.errors.HTTPException:
            msg="I cant reply to that"
            await message.reply(msg)
    bot.run(token)
        
