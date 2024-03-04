from config.config import Config
from logger.logger import Logger
from PIL import Image
from ollama import AsyncClient

import re
import requests
import json
import ollama
import shutil
import asyncio


#set_debug(True)
#ollama = Ollama(base_url=str(Config.get_ollama()),model=Config.get_model()) 
class Llama: 
    async def promptGen(msg, model):
        Logger.writter(f'Using {Config.get_model()} to generate response')
        aimodel = Config.get_model()
        messages= {'role': 'user', 'content': re.sub(r'<(.*?)>', '', msg)}

        resp = await AsyncClient().chat(model, messages=[messages])

        Logger.writter("The response from the ollama ep is ~> {resp}")
        return resp['message']['content']
                      
    async def imgPrompt(msg, url):
        Logger.writter(f'url is {url}')
        response = requests.get(url, stream=True)
        MAGIC_STATIC_VAR = "insert_fn.png"
        leprompt = re.sub(r'<(.*?)>', '', msg)
        
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

