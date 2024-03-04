from langchain.llms import Ollama
from langchain.globals import set_debug
from config.config import Config
from logger.logger import Logger
from PIL import Image

import re
import requests
import json
import ollama
import shutil


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

    def imgPrompt(msg, url):
        Logger.writter(f'url is {url}')
        response = requests.get(url, stream=True)
        MAGIC_STATIC_VAR = "insert_fn.png"
        leprompt = msg
        
        with open(MAGIC_STATIC_VAR, 'wb')  as out_file:
            shutil.copyfileobj(response.raw, out_file)

            del response

            img = Image.open(MAGIC_STATIC_VAR).convert("RGB")
            img.save(MAGIC_STATIC_VAR, "png")

            with open(MAGIC_STATIC_VAR, 'rb') as file:
                response = ollama.chat(
                  model='llava',
                  messages=[
                    {
                      'role': 'user',
                      'content': leprompt,
                      'images': [file.read()],
                    },
                  ],
                )
        resp = response['message']['content']
        Logger.writter("The response from the ollama ep is ~> {resp}")
        return response['message']['content']

    def list():
        response = requests.get(Config.get_ollama() + '/api/tags')
        models = response.json()
        names = [model["name"] for model in models["models"]]
        return names

