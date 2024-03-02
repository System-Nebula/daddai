from dotenv import load_dotenv
import discord
import os

class Config:
    load_dotenv()
    def get_token():
        TOKEN = os.getenv("DISCORD_TOKEN")
        return TOKEN
    def set_loglvl():
        level = os.getenv("level")
        return level
    def get_ollama():
        ollamaSrv = os.getenv("OLLAMA_URL")
        return ollamaSrv
    def get_model():
        model = os.getenv("OLLAMA_MODEL")
        return str(model)
    def set_bot():
        itents = discord.Intents.default()
        itents.members = True
        itents.message_content = True
        return itents
    def extensions():
        initial_extensions = ['commands.general']
        return initial_extensions