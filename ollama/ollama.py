from langchain.llms import Ollama
from config.config import Config
from logger.logger import Logger
import requests
import json

class Llama:
    def conn(msg):
        try:
            ollama = Ollama(base_url=str(Config.get_ollama()),model=Config.get_model()) 
            Logger.writter(f'Connecting to {Config.get_ollama()} and using the model {Config.get_model()}')
            ollama(msg)
            return ollama(msg)
        except requests.exceptions.Connectionerror:
            Logger.writter(f'Unable to access the ollama server')
            Llama.conn(msg)

    def list():
        response = requests.get(Config.get_ollama() + '/api/tags')
        models = response.json()
        names = [model["name"] for model in models["models"]]
#        r = json.dumps(models, indent=4, sort_keys=True)
        return names

