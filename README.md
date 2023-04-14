# GPT Agent Toolkit

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/XpressAI/Xircuits)](https://github.com/XpressAI/Xircuits/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/XpressAI/Xircuits)](https://github.com/XpressAI/Xircuits/issues)

Welcome to the **GPT Agent Toolkit**! This toolkit provides a comprehensive set of Xircuits components that allow you to experiment with and create Collaborative Large Language Model-based automatons (Agents) in the style of BabyAGI and AutoGPT. By default, the toolkit comes with BabyAGI agents, but it is designed to be easily customizable with your own prompts.

## Table of Contents
- [Features](#features)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Usage](#usage)
  - [Basic Usage](#basic-usage)
  - [Customizing Prompts](#customizing-prompts)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgements](#acknowledgements)

## Features
- Pre-built BabyAGI agents
- Support for both Vecto and Pinecone Memories
- Support for Tools such as Python Exec, and SQLLite
- Support for both OpenAI and LLAMA models
- Open-source and community-driven

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
