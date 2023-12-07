from langchain.llms import Ollama
from config.config import Config
from logger.logger import Logger
import requests

class Llama:
    def __init__(self):
        self.base_url = Config.get_ollama()
        self.model = Config.get_model()
        self.ollama = Ollama(base_url=self.base_url, model=self.model)

    def conn(self, msg):
        try:
            Logger.writter(f'Connecting to {self.base_url} and using the model {self.model}')
            return self.ollama(msg)
        except requests.exceptions.ConnectionError:
            Logger.writter('Unable to access the ollama server')
            sleep(10)
            conn(self,msg)
            # Handle the connection error appropriately, e.g., by retrying after a delay or raising an exception.

    def list(self):
        response = requests.get(f'{self.base_url}/api/tags')
        models = response.json()
        return [model["name"] for model in models["models"]]