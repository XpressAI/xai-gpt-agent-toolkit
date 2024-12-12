<p align="center">
  <a href="https://github.com/XpressAI/xircuits/tree/master/xai_components#xircuits-component-library-list">Component Libraries</a> •
  <a href="https://github.com/XpressAI/xircuits/tree/master/project-templates#xircuits-project-templates-list">Project Templates</a>
  <br>
  <a href="https://xircuits.io/">Docs</a> •
  <a href="https://xircuits.io/docs/Installation">Install</a> •
  <a href="https://xircuits.io/docs/category/tutorials">Tutorials</a> •
  <a href="https://xircuits.io/docs/category/developer-guide">Developer Guides</a> •
  <a href="https://github.com/XpressAI/xircuits/blob/master/CONTRIBUTING.md">Contribute</a> •
  <a href="https://www.xpress.ai/blog/">Blog</a> •
  <a href="https://discord.com/invite/vgEg2ZtxCw">Discord</a>
</p>





<p align="center"><i>Xircuits Component Library for GPT Agent Toolkit – Empower your workflows with intelligent task management and execution tools.</i></p>

---
## Xircuits Component Library for GPT Agent Toolkit

Effortlessly integrate GPT-powered agents into Xircuits workflows. This library enables dynamic task creation, prioritization, execution, and critique, alongside tools for interaction, memory management, and contextual understanding.

## Table of Contents

- [Preview](#preview)
- [Prerequisites](#prerequisites)
- [Main Xircuits Components](#main-xircuits-components)
- [Try the Examples](#try-the-examples)
- [Installation](#installation)

## Preview

### The Example:

<img src="https://github.com/user-attachments/assets/bf4fc849-477f-4ec7-af18-a94cb39c6186" alt="baby_agi" />

### The Result:

<img src="https://github.com/user-attachments/assets/4c7bcb59-6864-4bd9-992b-ff0ebb44331b" alt="baby_agi_result"/>

## Prerequisites

Before you begin, you will need the following:

1. Python3.9+.
2. Xircuits.
3. API key for OpenAI



## Main Xircuits Components

### TaskCreatorAgent Component:
Creates new tasks dynamically based on objectives, previous results, and the list of incomplete tasks.

<img src="https://github.com/user-attachments/assets/72d5c946-e5f4-4497-804f-4cb3713f181b" alt="TaskCreatorAgent" width="200" height="200" />

### ToolRunner Component:
Executes tools specified within tasks and stores the results in memory for future reference.

<img src="https://github.com/user-attachments/assets/a5a88220-0d61-4ea9-aeb6-fb3b552f5de0" alt="ToolRunner" width="200" height="150" />

### TaskPrioritizerAgent Component:
Reorders and prioritizes tasks to align with the overall objective efficiently.

### TaskExecutorAgent Component:
Executes tasks using specified tools, memory, and context to achieve desired outcomes.

### TaskCriticAgent Component:
Reviews and critiques executed actions to ensure accuracy and alignment with the task objective.

### CreateTaskList Component:
Initializes a task list with a default or user-defined initial task.

### ScratchPadTool Component:
Provides a scratch pad for storing and summarizing intermediate thoughts or insights.

### PromptUserTool Component:
Prompts the user for input and captures their responses for use in workflows.

### BrowserTool Component:
Automates browser interactions for tasks like navigation and data extraction.

### SqliteTool Component:
Executes SQL queries on an SQLite database and returns the results for further processing.

## Try the Examples

We have provided an example workflow to help you get started with the GPT Agent Toolkit component library. Give it a try and see how you can create custom GPT Agent Toolkit components for your applications.

### BabyAGI Example  
Explore the babyagi.xircuits workflow. This example demonstrates an iterative approach to task management, utilizing AI to execute, create, and prioritize tasks dynamically in a loop.

## Installation
To use this component library, ensure that you have an existing [Xircuits setup](https://xircuits.io/docs/main/Installation). You can then install the GPT Agent Toolkit library using the [component library interface](https://xircuits.io/docs/component-library/installation#installation-using-the-xircuits-library-interface), or through the CLI using:

```
xircuits install gpt-agent-toolkit
```
You can also do it manually by cloning and installing it:
```
# base Xircuits directory
git clone https://github.com/XpressAI/xai-gpt-agent-toolkit xai_components/xai_gpt_agent_toolkit
pip install -r xai_components/xai_gpt_agent_toolkit/requirements.txt
```