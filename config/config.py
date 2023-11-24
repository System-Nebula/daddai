from dotenv import load_dotenv
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
#Super useful comment