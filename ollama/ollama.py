from langchain.llms import Ollama
from config.config import Config
from logger.logger import Logger

class Llama:
    def conn(msg):
        ollama = Ollama(base_url=str(Config.get_ollama()),model=Config.get_model()) 
        Logger.writter(f'Connecting to {Config.get_ollama()} and using the model {Config.get_model()}')
        ollama(msg)
        return ollama(msg)
