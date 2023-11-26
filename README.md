# nebula.ai



[![Publish Docker image](https://github.com/System-Nebula/daddai/actions/workflows/imgBuilder.yaml/badge.svg?branch=main)](https://github.com/System-Nebula/daddai/actions/workflows/imgBuilder.yaml)
## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)

## Overview

[Your Bot's Name] is a Discord bot that provides a fun and interactive experience for users. With a wide range of features, users can engage in exciting conversations, play games, and much more.

[Add a brief description of your bot's unique features or any additional information that you want to include in the Overview section.]

## Installation

[Describe the installation process, including any dependencies that the user needs to install before running your bot. If your bot is available on PyPI, include a link to the PyPI page.]

In order to run the bot you need the following settings: </br>
- *.env* file that contains the following info :
  - DISCORD_TOKEN -> The discord token for the bot to be running
  - level -> log level, so far the only accepted level is debug
  - OLLAMA_URL -> The ollama server url with the following format ```http://ollama_host:ollama_port ```
- A .log directory

It is also needed to run ```pip3 install -r deps/requirements.txt```

Another way to have the bot running could be by running the docker-compose file ``` docker-compose up -d ``` </br>
Make sure you have a .env file in the current directory with the following structure </br>
```
DISCORD_TOKEN = YOUR_DISCORD_TOKEN
level = debug
OLLAMA_URL = http://ollama_host:ollama_port
OLLAMA_MODEL = llm_model
```
To check if the container is running ``` docker-compose ps ``` </br>

### Repo workflow

It would be good to work on a branch called dev </br>
When the work on the branch is done commit it to dev </br>
The gh workflow will automatically create a PR

### How to interact with the bot

In order to interact with the bot you just have to mention it in your message @bot_name text
