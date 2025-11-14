import discord
from discord.ext import commands
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from src.clients.ollama_custom.ollama import Llama
from logger.logger import Logger

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
      await ctx.reply(self.bot.latency)

    @commands.command()
    async def query(self,ctx, model, q):
      if model in Llama.list():
        await ctx.reply(Llama.promptGen(q, model))
      else:
        Logger.writter("Invalid model")
        await ctx.reply("Please select a valid model")

    @commands.command()
    async def list(self, message):
      await message.channel.typing()
      msg = Llama.list()
      Logger.writter("Listing models")
      await message.reply(msg)
async def setup(bot):
    await bot.add_cog(General(bot))