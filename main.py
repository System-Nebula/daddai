import asyncio
import discord
from discord.ext import commands
from config.config import Config
from logger.logger import Logger
from ollama.ollama import Llama
from model.model import Model

Logger.cfg(Config.set_loglvl())
bot = commands.Bot(command_prefix='?', description='Nebula AI interact with an LLM Model', intents=Config.set_bot())

if __name__ == "__main__":

    @bot.event
    async def on_ready():
        Logger.writter(f'Logged in as {bot.user} (ID: {bot.user.id})')
        for extension in Config.extensions():
            await bot.load_extension(extension)

    @bot.event
    async def on_message(message):
        if bot.user.mention in message.content.split():
            async with message.channel.typing():
                try:
                    msg = Model.modCon(message) + " testing by Frankie"
                    #msg = Llama.conn(message.content, Config.get_model())
                    Logger.writter(f'ollama message length:{len(msg)}')
                except discord.errors.HTTPException:
                    msg = "I can't reply to that"
                await message.reply(msg)
        await bot.process_commands(message)

    async def main():
        async with bot:
            await bot.start(Config.get_token())

    asyncio.run(main())
