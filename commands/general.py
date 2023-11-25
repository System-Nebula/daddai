import discord
from discord.ext import commands
from ollama.ollama import Llama
from logger.logger import Logger

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
      await ctx.reply(self.bot.latency)

    @commands.command()
    async def list(self, message):
      await message.channel.typing()
      msg = Llama.list()
      Logger.writter("Listing models")
      await message.reply(msg)
async def setup(bot):
    await bot.add_cog(General(bot))