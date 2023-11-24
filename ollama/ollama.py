from langchain.llms import Ollama
from config.config import Config
from logger.logger import Logger
import os
import requests
class Llama:
    def conn(msg):
        try:
            ollama = Ollama(base_url=str(Config.get_ollama()),model=Config.get_model()) 
            Logger.writter(f'Connecting to {Config.get_ollama()} and using the model {Config.get_model()}')
            ollama(msg)
            return ollama(msg)
        except requests.exceptions.Connectionerror:
            Logger.writter(f'Unable to access the ollama server')
            os.Exit(1)
