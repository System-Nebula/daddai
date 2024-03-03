from langchain.llms import Ollama
from langchain.globals import set_debug
from config.config import Config
from logger.logger import Logger
import re
import requests
import json

set_debug(True)
#ollama = Ollama(base_url=str(Config.get_ollama()),model=Config.get_model()) 
class Llama:
    def conn(msg, model, **kwargs):
        ollama = Ollama(base_url=str(Config.get_ollama()),model=model) 
        if model == Config.get_model():
            try:
                Logger.writter(f'Connecting to {Config.get_ollama()} and using the model {model}')
                ollama(msg)
                return ollama(msg) #main.py "i cant reply to that"
            except requests.exceptions.ConnectionError:
                Logger.writter(f'Unable to access the ollama server')
                Llama.conn(msg)
        if model == "llava:latest":
            img = kwargs['img'] 
            #img = kwargs.items()[0]
            Logger.writter(f'Connecting to llava using {img} with ctx {msg}') # just easier to debug later
            
            print(img)

            ollama.bind(images=[img]) 
            return ollama.invoke(re.sub(r'<(.*?)>', '', msg))



    def list():
        response = requests.get(Config.get_ollama() + '/api/tags')
        models = response.json()
        names = [model["name"] for model in models["models"]]
        return names

