from dotenv import load_dotenv
import discord
import os

class Config:
    load_dotenv()
    
    @staticmethod
    def get_token():
        return os.getenv("DISCORD_TOKEN")
    
    @staticmethod
    def set_loglvl():
        return os.getenv("level")
    
    @staticmethod
    def get_ollama():
        return os.getenv("OLLAMA_URL")
    
    @staticmethod
    def get_model():
        return str(os.getenv("OLLAMA_MODEL"))
    
    @staticmethod
    def set_bot():
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        return intents
    
    @staticmethod
    def extensions():
        return ['commands.general']
