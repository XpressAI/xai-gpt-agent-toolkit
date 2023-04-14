# GPT Agent Toolkit

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/XpressAI/Xircuits)](https://github.com/XpressAI/Xircuits/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/XpressAI/Xircuits)](https://github.com/XpressAI/Xircuits/issues)
[![XpressAI Discord](https://img.shields.io/discord/906370139077881997)](https://discord.gg/vsSRC39b)

Welcome to the **GPT Agent Toolkit**! This toolkit provides a comprehensive set of Xircuits components that allow you to experiment with and create Collaborative Large Language Model-based automatons (Agents) in the style of [BabyAGI](https://github.com/yoheinakajima/babyagi) and [Auto-GPT](https://github.com/Torantulino/Auto-GPT). By default, the toolkit comes with BabyAGI agents, but it is designed to be easily customizable with your own prompts.

![BabyAGI demo](https://github.com/XpressAI/xai-gpt-agent-toolkit/blob/main/demo.gif)

## Table of Contents
- [Features](#features)
- [Ideas](#ideas)
- [Getting Started](#getting-started)
  - [Shameless Plug](#shameless-plug)
  - [Prerequisites](#prerequisites)
  - [Software Prerequisites](#software-prerequisites)
  - [API Prerequisites](#api-prerequisites)
  - [Create a project](#create-a-project)
  - [Installation](#installation)
- [Usage](#usage)
  - [Basic Usage](#basic-usage)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgements](#acknowledgements)

## Features
- Pre-built BabyAGI agents
- Support for both [Vecto](https://www.vecto.ai) and [Pinecone](https://www.pinecone.io) Memories
- Support for Tools such as Python Exec, and SQLLite
- Support for both OpenAI and LLAMA models
- Open-source and community-driven

## Ideas

Here are some ideas that you could try relatively easily with Xircuits.

1. Make a critic agent that updates the objective to be more effective.
2. Have the agents produce a status report on Slack and update the objective based on your reply.
3. Upload a large image dataset on Vecto with image descriptions giving your agent sight.
4. Connect to Whisper and have a daily standup meeting with the agent.
5. Make 2 BabyAGIs and have 1 critic decide which action to actually perform.

## Getting Started

These instructions will help you set up the GPT Agent Toolkit on your local machine.

This is a component library so you don't need to clone this directly. Instead install
Xircuits and install this component library into it.

### Shameless plug

If the following is too much work or too complicated.  Sign up to the Xpress AI Platform waistlist
to get access to a single app that has everything you need to get started.

[Join the Xpress AI Platform Waitlist](https://xpress.ai/join-waitlist)


### Software Prerequisites

Before you begin, make sure you have the following software installed on your system:

- Python 3.8 or higher
- pip (Python package installer)
- git 

### API Prerequisites

You will need an API key from Open AI to use GPT-3.5 and either a Vecto or Pinecone account for agent memory.

Create a .env file and put your API keys into the respective lines.

```
OPENAI_API_KEY=<Your OpenAI API Key here>
OPENAI_ORG=<Your OpenAI Org (if you have one)>
```

For Vecto users:
```
VECTO_API_KEY=<A ACCOUNT_MANAGEMENT Vecto key>
VECTO_USAGE_KEY=<A Usage Vecto key with access to the vector spaces you want to use>
```

For Pinecone users:
```
PINECONE_API_KEY=<Your Pinecone API key>
PINECONE_ENVIRONMENT=<Your Pinecone environment>
```


### Create a project

Windows:

```
mkdir project
cd project
python -m venv venv
venv\Scripts\activate
```

Linux of macOS:
```bash
mkdir project
cd project
python3 -m venv venv
source ./venv/bin/activate
```

### Installation

1. Install xircuits

```bash
pip install xircuits
```

2. Launch xircuits-components tool to install the base component library

```bash
xircuits-components
```


3. Install Vecto (if using vecto)

```bash
pip install git+https://github.com/XpressAI/vecto-python-sdk.git
```


4. Add the OpenAI and GPT Agent Toolkit component libraries

```bash

git init .
git submodule add https://github.com/XpressAI/xai-openai xai_components/xai_openai
git submodule add https://github.com/XpressAI/xai-gpt-agent-toolkit.git xai_components/xai_gpt_agent_toolkit

pip install -r xai_components/xai_openai/requirements.txt
pip install -r xai_components/xai_gpt_agent_toolkit/requirements.txt

```

## Usage

### Basic Usage

1. Copy the sample BabyAGI Xircuits file to your project folder.

```bash
cp xai_components/xai_gpt_agent_toolkit/babyagi.xircuits .
```

2. Start JupyterLab/Xircuits by running:

```bash
xircuits
```

3. Use the printed out URLs to browse to http://localhost:8888/lab and double click the babyagi.xiruits file.

4. Click play to watch it go and try to make the world a better place.


## Contributing

We appreciate your interest in contributing to the GPT Agent Toolkit! Any new tools or prompts are welcome.

## License

This project is licensed under the MIT License - see the LICENSE.md file for details.

## Acknowledgements

- The team behind Xircuits.  Give the project a star if it looks interesting!
- The developers of [BabyAGI](https://github.com/yoheinakajima/babyagi) and [AutoGPT](https://github.com/Torantulino/Auto-GPT) for their groundbreaking work on large language model-based agents
