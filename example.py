
import requests
import json

def list():
    response = requests.get('http://localhost:11434/api/tags')
    models = response.json()
    names = [model["name"] for model in models["models"]]
    for name in len(names):
        #name += f'{name} ' + '\n'
        print(names[name])
#    print(name)
#    return name

list()

