# nebula.ai

In order to run the bot you need the following settings: </br>
- *.env* file that contains the following info :
  - DISCORD_TOKEN -> The discord token for the bot to be running
  - level -> log level, so far the only accepted level is debug
  - OLLAMA_URL -> The ollama server url with the following format ```http://ollama_host:ollama_port ```
- A .log directory

It is also needed to run ```pip3 install -r deps/requirements.txt```

### Repo workflow

It would be good to work on a branch called dev </br>
When the work on the branch is done commit it to dev </br>
The gh workflow will automatically create a PR