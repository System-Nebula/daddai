from langchain.llms import Ollama
from config.config import Config
from logger.logger import Logger
import requests
import json

ollama = Ollama(base_url=str(Config.get_ollama()),model=Config.get_model()) 
class Llama:
    def conn(msg, model):
        try:
            Logger.writter(f'Connecting to {Config.get_ollama()} and using the model {model}')
            ollama(msg)
            return ollama(msg)
        except requests.exceptions.ConnectionError:
            Logger.writter(f'Unable to access the ollama server')
            Llama.conn(msg)

    def list():
        response = requests.get(Config.get_ollama() + '/api/tags')
        models = response.json()
        names = [model["name"] for model in models["models"]]
        return names

