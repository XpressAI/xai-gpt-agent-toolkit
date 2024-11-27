import sys
import abc
from collections import deque
import re
from typing import NamedTuple

import json
from dotenv import load_dotenv
import numpy as np
import os
import openai
from openai import OpenAI
import requests
import sqlite3
import subprocess
import time
from xai_components.base import InArg, OutArg, InCompArg, Component, xai_component

load_dotenv()

DEFAULT_EXECUTOR_PROMPT = """
You are an AI who performs one task based on the following objective: {objective}.
Take into account these previously completed tasks: {context}
*Your thoughts*: {scratch_pad}
*Your task*: {task}
*Your tools*: {tools}
You can use a tool by writing TOOL: TOOL_NAME in a single line. then the arguments of the tool (if any) For example, to use the python-exec tool, write
TOOL: python-exec
```
print('Hello world!')
```
Response:
"""

DEFAULT_CRITIC_PROMPT = """
You are an AI who checks and improves that the action about to be performed is correct given the information you have. 
If it is the optimal solution you should respond with the action as-is.

The task should help achieve the following objective: {objective}.
Take into account these previously completed tasks: {context}
The task: {task}
The action: {action}
Response:
"""

DEFAULT_TASK_CREATOR_PROMPT = """
You are an task creation AI that uses the result of an execution agent
to create new tasks with the following objective: {objective},
The last completed task has the result: {result}.
This result was based on this task description: {task_name}.
These are incomplete tasks: {task_list}.
Based on the result, create new tasks to be completed by the AI system that do not overlap with incomplete tasks.
Return the tasks as an array.
"""

DEFAULT_TASK_PRIORITIZER_PROMPT = """
You are a task prioritization AI tasked with cleaning the formatting of and reprioritizing the following tasks:
{task_names}.
Consider the ultimate objective of your team:{objective}. Do not remove any tasks.
Return the result as a numbered list, like:
#. First task
#. Second task
Start the task list with number {next_task_id}.
"""


class Memory(abc.ABC):
    def query(self, query: str, n: int) -> list:
        pass

    def add(self, id: str, text: str, metadata: dict) -> None:
        pass


def run_tool(tool_code: str, tools: list) -> str:
    if tool_code is None:
        return ""
    
    ret = ""

    for tool in tools:
        if tool_code.startswith(tool["name"]):
            if tool["instance"]:
                ret += tool["instance"].run_tool(tool_code)
                #tool["instance"] = None

    return ret


def llm_call(model: str, prompt: str, temperature: float = 0.5, max_tokens: int = 500):
    #print("**** LLM_CALL ****")
    #print(prompt)
    
    while True:
        try:
            if model == 'gpt-3.5-turbo' or model == 'gpt-4o-mini':
                client = OpenAI()
                messages = [{"role": "system", "content": prompt}]
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    n=1,
                    stop=["OUTPUT", ],
                )
                return response.choices[0].message.content.strip()
            elif model.startswith("rwkv"):
                # Use proxy.
                if not openai.proxies: raise Exception("No proxy set")
                messages = [{"role": "system", "content": prompt}]
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    n=1,
                    stop=["OUTPUT", ],
                )
                return response.choices[0].message.content.strip()
            elif model.startswith("llama"):
                # Spawn a subprocess to run llama.cpp
                cmd = ["llama/main", "-p", prompt]
                result = subprocess.run(cmd, shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True)
                return result.stdout.strip()
            else:
                raise Exception(f"Unknown model {model}")
        except openai.RateLimitError:
            print("Rate limit error, sleeping for 10 seconds...")
            time.sleep(10)
        except openai.APIError:
            print("Service unavailable error, sleeping for 10 seconds...")
            time.sleep(10)
        else:
            break


def get_sorted_context(memory: Memory, query: str, n: int):
    results = memory.query(query, n)
    sorted_results = sorted(
        results,
        key=lambda x: x.similarity if getattr(x, 'similarity', None) else x.score,
        reverse=True
    )
    return [(str(item.attributes['task']) + ":" + str(item.attributes['result'])) for item in sorted_results]


def extract_task_number(task_id, task_list):
    if isinstance(task_id, int):
        return task_id
    
    matches = re.findall(r'\d+', task_id)
    if matches:
        return int(matches[0])
    else:
        # fallback if we match nothing.
        return len(task_list) + 1


@xai_component
class TaskCreatorAgent(Component):
    """Creates new tasks based on given model, prompt, and objectives.

    #### inPorts:
    - objective: Objective for task creation.
    - prompt: Prompt string for the AI model.
    - model: AI model used for task creation.
    - result: Result of the previous tasks.
    - task: Current task information.
    - task_list: List of all tasks.

    #### outPorts:
    - new_tasks: list of newly created tasks.
    """

    objective: InCompArg[str]
    prompt: InArg[str]
    model: InArg[str]
    result: InArg[str]
    task: InArg[dict]
    task_list: InArg[str]
    new_tasks: OutArg[list]

    def execute(self, ctx) -> None:
        text = self.prompt.value if self.prompt.value is not None else DEFAULT_TASK_CREATOR_PROMPT

        prompt = text.format(**{
            "objective": self.objective.value,
            "result": self.result.value,
            "task": self.task.value,
            "task_name": self.task.value["task_name"],
            "task_list": self.task_list.value
        })

        response = llm_call(self.model.value, prompt)
        new_tasks = response.split('\n')
        print("New tasks: ", new_tasks)

        task_id = self.task.value["task_id"]
        task_id_counter = extract_task_number(task_id, self.task_list)
        ret = []
        for task_name in new_tasks:
            task_id_counter += 1
            ret.append({"task_id": task_id_counter, "task_name": task_name})

        self.new_tasks.value = ret

@xai_component
class TaskPrioritizerAgent(Component):
    """Prioritizes tasks based on given model, prompt, and objectives.

    #### inPorts:
    - objective: Objective for task prioritization.
    - prompt: Prompt string for the AI model.
    - model: AI model used for task prioritization.
    - task_list: List of all tasks.

    #### outPorts:
    - prioritized_tasks: Prioritized list of tasks.
    """

    objective: InCompArg[str]
    prompt: InArg[str]
    model: InArg[str]
    task_list: InArg[list]
    prioritized_tasks: OutArg[deque]

    def execute(self, ctx) -> None:
        text = self.prompt.value if self.prompt.value is not None else DEFAULT_TASK_PRIORITIZER_PROMPT
        prompt = text.format(**{
            "objective": self.objective.value,
            "task_list": self.task_list.value,
            "task_names": [t["task_name"] for t in self.task_list.value],
            "next_task_id": max([int(t["task_id"]) for t in self.task_list.value]) + 1
        })
        response = llm_call(self.model.value, prompt)
        new_tasks = response.split('\n')
        task_list = deque()
        for task_string in new_tasks:
            task_parts = task_string.strip().split(".", 1)
            if len(task_parts) == 2:
                task_id = task_parts[0].strip()
                task_name = task_parts[1].strip()
                task_list.append({"task_id": task_id, "task_name": task_name})

        print(f"New tasks: {new_tasks}")
        self.prioritized_tasks.value = task_list


@xai_component
class TaskExecutorAgent(Component):
    """Executes tasks based on given model, prompt, tools, and memory.

    #### inPorts:
    - objective: Objective for task execution.
    - prompt: Prompt string for the AI model.
    - model: AI model used for task execution.
    - tasks: Queue of tasks to be executed.
    - tools: List of tools available for task execution.
    - memory: Memory context for task execution.

    #### outPorts:
    - action: Executed action.
    - task: Task information.
    """

    objective: InCompArg[str]
    prompt: InArg[str]
    model: InArg[str]
    tasks: InArg[deque]
    tools: InArg[list]
    memory: InArg[any]
    action: OutArg[str]
    task: OutArg[dict]

    def execute(self, ctx) -> None:
        text = self.prompt.value if self.prompt.value is not None else DEFAULT_EXECUTOR_PROMPT

        task = self.tasks.value.popleft()
        print(f"Next Task: {task}")
        context = get_sorted_context(self.memory.value, query=self.objective.value, n=5)

        print("\n*******RELEVANT CONTEXT******\n")
        print(context)

        scratch_pad = ""

        for tool in self.tools.value:
            if tool['name'] == 'scratch-pad':
                file_name = tool['instance'].file_name.value
                with open(file_name, "r") as f:
                    scratch_pad += f.read()

        print("\n*******SCRATCH PAD******\n")
        print(scratch_pad)

        prompt = text.format(**{
            "scratch_pad": scratch_pad,
            "objective": self.objective.value,
            "context": context,
            "task": self.task.value,
            "tools": [tool['spec'] for tool in self.tools.value]
        })
        result = llm_call(self.model.value, prompt, 0.7, 2000)

        print(f"Result:\n{result}")

        self.action.value = result
        self.task.value = task


@xai_component
class TaskCriticAgent(Component):
    """Critiques an executed task's action using an AI model.

    #### inPorts:
    - prompt: The base string that the AI model uses to critique the task action.
    - objective: The overall objective that should guide task critique.
    - model: The AI model that generates the critique.
    - memory: The current context memory, used for retrieving relevant information for task critique.
    - tools: The list of tools available for task critique.
    - action: The executed action that is to be critiqued.
    - task: The current task information.

    #### outPorts:
    - updated_action: The updated action after the model's critique.
    """

    prompt: InArg[str]
    objective: InArg[str]
    model: InArg[str]
    memory: InArg[any]
    tools: InArg[list]
    action: InArg[str]
    task: InArg[dict]
    updated_action: OutArg[str]

    def execute(self, ctx) -> None:
        text = self.prompt.value if self.prompt.value is not None else DEFAULT_CRITIC_PROMPT

        print(f"Task: {self.task.value}")

        context = get_sorted_context(self.memory.value, query=self.objective.value, n=5)
        print("Context: ", context)

        prompt = text.format(**{
            "objective": self.objective.value,
            "context": context,
            "action": self.action.value,
            "task": self.task.value
        })
        new_action = llm_call(self.model.value, prompt, 0.7, 2000)

        print(f"New action: {new_action}")

        # If the model responds without a new TOOL prompt use the original.
        if "TOOL" not in new_action:
            new_action = self.action.value

        self.updated_action.value = new_action

@xai_component
class ToolRunner(Component):
    """Executes a tool based on the given action.

    #### inPorts:
    - action: The action that determines which tool should be executed.
    - memory: The current context memory, used for updating the result of tool execution.
    - task: The current task information.
    - tools: The list of tools available for execution.

    #### outPorts:
    - result: The result after running the tool.
    """

    action: InArg[str]
    memory: InCompArg[Memory]
    task: InArg[dict]
    tools: InArg[list]
    result: OutArg[str]

    def execute(self, ctx) -> None:
        tools = self.action.value.split("TOOL: ")
        result = self.action.value + "\n"
        for tool in tools:
            result += run_tool(tool, self.tools.value.copy())

        task = self.task.value
        self.memory.value.add(
            f"result_{task['task_id']}",
            result,
            {
                "task_id": task['task_id'],
                "task": task['task_name'],
                "result": result
            }
        )

        self.result.value = result


@xai_component
class CreateTaskList(Component):
    """Component that creates an task list based on `initial_task`. 
    If no initial task provided, the first task would be "Develop a task list".

    #### inPorts:
    - initial_task: The first task to be added to the task list.

    #### outPorts:
    - task_list: The created task list with the initial task.
    """
    initial_task: InArg[str]
    task_list: OutArg[deque]

    def execute(self, ctx) -> None:
        task_list = deque([])

        # Add the first task
        first_task = {
            "task_id": 1,
            "task_name": self.initial_task.value if self.initial_task.value else "Develop a task list"
        }

        task_list.append(first_task)
        self.task_list.value = task_list


TOOL_SPEC_SQLITE = """
Perform SQL queries against an sqlite database.  
Use by writing the SQL within markdown code blocks. 
Example: TOOL: sqlite
```
CREATE TABLE IF NOT EXISTS points (x int, y int);
INSERT INTO points (x, y) VALUES (783, 848);
SELECT * FROM points;
```
sqlite OUTPUT:
[(783, 848)]
"""

@xai_component
class SqliteTool(Component):
    """Component that performs SQL queries against an SQLite database.

    #### inPorts:
    - path: The path to the SQLite database.

    #### outPorts:
    - tool_spec: The specification of the SQLite tool, including its capabilities and requirements.
    """

    path: InArg[str]
    tool_spec: OutArg[dict]

    def execute(self, ctx) -> None:
        if not 'tools' in ctx:
            ctx['tools'] = {}
        spec = {
            'name': 'sqlite',
            'spec': TOOL_SPEC_SQLITE,
            'instance': self
        }

        self.tool_spec.value = spec

    def run_tool(self, tool_code) -> str:
        print(f"Running tool sqlite")
        lines = tool_code.splitlines()
        code = []
        include = False
        any = False
        for line in lines[1:]:
            if "```" in line and include == False:
                include = True
                any = True
                continue
            elif "```" in line and include == True:
                include = False
                continue
            elif "TOOL: sql" in line:
                continue
            elif "OUTPUT" in line:
                break
            elif include:
                code.append(line + "\n")
        if not any:
            for line in lines[1:]:
                code.append(line + "\n")
        conn = sqlite3.connect(self.path.value)
        
        all_queries = "\n".join(code)
        queries = all_queries.split(";")
        res = ""
        try:
            for query in queries:
                res += str(conn.execute(query).fetchall())
                res += "\n"
                conn.commit()
        except Exception as e:
            res += str(e)
        
        return res

    
TOOL_SPEC_BROWSER = """
Shows the user which step to perform in a browser and outputs the resulting HTML. Use by writing the commands within markdown code blocks. Do not assume that elements are on the page, use the tool to discover the correct selectors. Perform only the action related to the task. You cannot define variables with the browser tool. only write_file(filename, selector)

Example: TOOL: browser
```
goto("http://google.com")
fill('[title="search"]', 'my search query')
click('input[value="Google Search"]')
```
browser OUTPUT:
<html ....>
"""

@xai_component
class BrowserTool(Component):
    """A component that implements a browser tool.
    Uses the Playwright library to interact with the browser.
    Capable of saving screenshots and writing to files directly from the browser context.

    #### inPorts:
    - cdp_address: The address to the Chrome DevTools Protocol (CDP), allowing interaction with a Chrome instance.

    #### outPorts:
    - tool_spec: The specification of the browser tool.
    """

    cdp_address: InArg[str]
    tool_spec: OutArg[dict]

    def execute(self, ctx) -> None:
        if not 'tools' in ctx:
            ctx['tools'] = {}
        spec = {
            'name': 'browser',
            'spec': TOOL_SPEC_BROWSER,
            'instance': self
        }

        self.chrome = None
        self.playwright = None
        self.page = None
        self.tool_spec.value = spec

    def run_tool(self, tool_code) -> str:
        print(f"Running tool browser")
        lines = tool_code.splitlines()
        code = []
        include = False
        any = False
        for line in lines[1:]:
            if "```" in line and include == False:
                include = True
                any = True
                continue
            elif "```" in line and include == True:
                include = False
                continue
            elif "TOOL: browser" in line:
                continue
            elif "OUTPUT" in line:
                break
            elif include:
                code.append(line + "\n")
        if not any:
            for line in lines[1:]:
                code.append(line + "\n")
        
        res = ""
        try:
            import playwright
            from playwright.sync_api import sync_playwright
            
            if not self.chrome:
                self.playwright = sync_playwright().__enter__()
                self.chrome = self.playwright.chromium.connect_over_cdp(self.cdp_address.value)

            if not self.page:
                if len(self.chrome.contexts) > 0:
                    self.page = self.chrome.contexts[0].new_page()
                    self.page.set_default_timeout(3000)
                else:
                    self.page = self.chrome.new_context().new_page()
                    self.page.set_default_timeout(3000)

            self.page.save_screenshot = self.page.screenshot
            def write_file(file, selector):
                with open(file, "w") as f:
                    f.write(self.page.inner_text(selector))
            
            self.page.write_file = write_file
            self.page.save_text = write_file
            self.page.save_to_file = write_file
            for action in code:
                if not action.startswith("#"):
                    eval("self.page." + action)
                    
            res += self.page.content()[:4000]
            #browser.close()
        except Exception as e:
            res += str(e)
        
        print("*** PAGE CONTENT ***")
        print(res)
        
        return res

TOOL_SPEC_NLP = """
NLP tool provides methods to summarize, extract, classify, ner or translate informtaion on the current page.
To use use one of the words above followed by any arguments and finally a CSS selector.
TOOL: NLP, summarize div[id="foo"]
NLP OUTPUT:
Summary appears here.
"""

@xai_component
class NlpTool(Component):
    """Natural Language Processing (NLP) tool. Perform NLP operations within the browser context. 
    Enables the extraction of webpage content and further NLP analysis via a language model,
    in this case, gpt-3.5-turbo.    

    #### inPorts:
    - cdp_address: The address to the Chrome DevTools Protocol (CDP).

    #### outPorts:
    - tool_spec: The specification of the NLP tool.
    """
    cdp_address: InArg[str]
    tool_spec: OutArg[dict]

    def execute(self, ctx) -> None:
        if not 'tools' in ctx:
            ctx['tools'] = {}
        spec = {
            'name': 'browser',
            'spec': TOOL_SPEC_BROWSER,
            'instance': self
        }

        self.chrome = None
        self.playwright = None
        self.page = None
        self.tool_spec.value = spec

    def run_tool(self, tool_code) -> str:
        print(f"Running tool browser")
        lines = tool_code.splitlines()
        code = []
        include = False
        any = False
        for line in lines[1:]:
            if "```" in line and include == False:
                include = True
                any = True
                continue
            elif "```" in line and include == True:
                include = False
                continue
            elif "TOOL: browser" in line:
                continue
            elif "OUTPUT" in line:
                break
            elif include:
                code.append(line + "\n")
        if not any:
            for line in lines[1:]:
                code.append(line + "\n")
        
        res = ""
        try:
            import playwright
            from playwright.sync_api import sync_playwright
            
            if not self.chrome:
                self.playwright = sync_playwright().__enter__()
                self.chrome = self.playwright.chromium.connect_over_cdp(self.cdp_address.value)

            if not self.page:
                if len(self.chrome.contexts) > 0:
                    self.page = self.chrome.contexts[0].pages[0]
                    self.page.set_default_timeout(3000)
                else:
                    self.page = self.chrome.new_context().new_page()
                    self.page.set_default_timeout(3000)

            
            for action in code:
                if not action.startswith("#"):
                    content = self.page.inner_text(action.split(" ")[-1])
                    prompt = action + "\n" + action.split(" ")[-1] + " is: \n---\n"
                    res += action + "OUTPUT:\n"
                    res += llm_call("gpt-3.5-turbo", prompt, 0.0, 100)
                    res += "\n"

        except Exception as e:
            res += str(e)
        
        print("*** PAGE CONTENT ***")
        print(res)
        
        return res

TOOL_SPEC_PYTHON = """
Execute python code in a virtual environment.  
Use by writing the code within markdown code blocks. 
Automate the browser with playwright.
The environment has the following pip libraries installed: {packages}
Example: TOOL: python-exec
```
import pyautogui
pyautogui.PAUSE = 1.0 # Minimum recommended
print(pyautogui.position())
```
python-exec OUTPUT:
STDOUT:Point(x=783, y=848)
STDERR:
"""

@xai_component
class ExecutePythonTool(Component):
    """
    Executes Python code and pip operations that are supplied as a string. 
    It extracts the Python code and pip commands, runs them, and returns their output or errors. 

    #### inPorts:
    - path: The path to the python sciprt.

    #### outPorts:
    - tool_spec: The specification of the Python tool, including its capabilities and requirements.
    """
    
    file_name: InArg[str]
    tool_spec: OutArg[dict]

    def execute(self, ctx) -> None:
        spec = {
            'name': 'python-exec',
            'spec': TOOL_SPEC_PYTHON,
            'instance': self
        }

        self.tool_spec.value = spec
    
    def run_tool(self, tool_code) -> str:
        print(f"Running tool python-exec")

        lines = tool_code.splitlines()
        code = []
        pip_operations = []
        include = False
        any = False
        for line in lines[1:]:
            if "```" in line and include == False:
                include = True
                any = True
                continue
            elif "```" in line and include == True:
                include = False
                continue
            elif "!pip" in line:
                pip_operations.append(line.replace("!pip", "pip"))
                continue
            elif include:
                code.append(line + "\n")
        if not any:
            for line in lines[1:]:
                code.append(line + "\n")
        
        print(f"Will run pip operations: {pip_operations}")
        tool_code = '\n'.join(code)
        print(f"Will run the code: {tool_code}")
        
        
        try:
            for pip_operation in pip_operations:
                result = subprocess.run(pip_operation, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True, cwd=os.getcwd())
                print(f"pip operation {pip_operation} returned: {result}")
            with open(self.file_name.value, "w") as f:
                f.writelines(code)
            result = subprocess.run(["python", self.file_name.value], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True, cwd=os.getcwd())
            output = "python-exec OUTPUT:\nSTDOUT: \n" + result.stdout + "\n" + "STDERR:" + "\n" + result.stderr
        except Exception as e:
            print(f"Exception running tool python-exec: {e}")
            output = str(e)
        print(f"Done running tool python-exec: Returned {output}")
        
        return output


TOOL_SPEC_PROMPT_USER = """
Prompt the user for input with this tool.
Example: TOOL: prompt-user
Hello would you like to play a game?

prompt-user OUTPUT:
Yes I would.
"""


@xai_component
class PromptUserTool(Component):
    """A component that enables interaction with a user by prompting for inputs.
    Prints a prompt message to the user and waits for input. 
    The user's response is then returned by the function.
    **Note**: If you use this component, run the compiled script from a terminal.

    #### outPorts:
    - tool_spec: The specification of the PromptUser tool.
    """

    tool_spec: OutArg[dict]

    def execute(self, ctx) -> None:
        spec = {
            'name': 'prompt-user',
            'spec': TOOL_SPEC_PROMPT_USER,
            'instance': self
        }

        self.tool_spec.value = spec
        
    def run_tool(self, tool_code) -> str:
        print("PROMPTING USER:")
        print(f"{tool_code}")
        res = input(">")
        return res


    
TOOL_SPEC_SCRATCH_PAD = """
Your internal monologue. Written to yourself in second-person. Write out any notes that should help you with the progress of your task.
Example: TOOL: scratch-pad
Thoughts go here.
"""


@xai_component
class ScratchPadTool(Component):
    """A component that creates and manages a 'scratch pad' for storing and summarizing information within the xai framework.
    The component is initialized with a file name to use as the scratch pad. During execution, 
    it writes to this file and provides a method `run_tool` that updates the contents of the file and 
    generates a summary of the current contents using the gpt-3.5-turbo language model.

    #### inPorts:
    - file_name: The name of the file that will be used as the scratch pad.

    #### outPorts:
    - tool_spec: The specification of the ScratchPad tool.
    """

    file_name: InArg[str]
    tool_spec: OutArg[dict]
            
    def execute(self, ctx) -> None:
        spec = {
            'name': 'scratch-pad',
            'spec': TOOL_SPEC_SCRATCH_PAD,
            'instance': self
        }
        
        with open(self.file_name.value, "w") as f:
            f.write("")
        
        self.tool_spec.value = spec
        
    def run_tool(self, tool_code) -> str:
        current_scratch = ""
        with open(self.file_name.value, "r") as f:
            current_scratch = f.read().strip()
        
        summary = None
        if len(current_scratch) > 0:
            summary = llm_call(
                "gpt-3.5-turbo",
                f"Summarize the following text with bullet points using a second person perspective. " +
                "Keep only the salient points.\n---\n {current_scratch}",
                0.0,
                1000
            )
        
        with open(self.file_name.value, "w") as f:
            if summary:
                f.write(summary)
                f.write("\n")
            f.write(tool_code[len('scratch-pad'):])
            
        return ""


class VectoMemoryImpl(Memory):
    def __init__(self, vs):
        self.vs = vs

    def query(self, query: str, n: int) -> list:
        return self.vs.lookup(query, 'TEXT', n).results
    def add(self, id: str, text: str, metadata: dict) -> None:
        from vecto import vecto_toolbelt

        vecto_toolbelt.ingest_text(self.vs, [text], [metadata])


def get_ada_embedding(text):
    s = text.replace("\n", " ")
    return openai.embeddings.create(input=[s], model="text-embedding-ada-002").data[0].embedding


class PineconeMemoryImpl(Memory):
    def __init__(self, index, namespace):
        self.index = index
        self.namespace = namespace

    def query(self, query: str, n: int) -> list:
        return self.index.query(get_ada_embedding(query), top_k=n, include_metadata=True, namespace=self.namespace)

    def add(self, vector_id: str, text: str, metadata: dict) -> None:
        self.index.upsert([(vector_id, get_ada_embedding(text), metadata)], namespace=self.namespace)


class NumpyQueryResult(NamedTuple):
    id: str
    similarity: float
    attributes: dict


class NumpyMemoryImpl(Memory):
    def __init__(self, vectors=None, ids=None, metadata=None):
        self.vectors = vectors
        self.ids = ids
        self.metadata = metadata

    def query(self, query: str, n: int) -> list:
        if self.vectors is None:
            return []
        if isinstance(self.vectors, list) and len(self.vectors) > 1:
            self.vectors = np.vstack(self.vectors)

        top_k = min(self.vectors.shape[0], n)
        query_vector = get_ada_embedding(query)
        similarities = self.vectors @ query_vector
        indices = np.argpartition(similarities, -top_k)[-top_k:]
        return [
            NumpyQueryResult(
                self.ids[i],
                similarities[i],
                self.metadata[i]
            )
            for i in indices
        ]

    def add(self, vector_id: str, text: str, metadata: dict) -> None:
        if isinstance(self.vectors, list) and len(self.vectors) > 1:
            self.vectors = np.vstack(self.vectors)

        if self.vectors is None:
            self.vectors = np.array(get_ada_embedding(text)).reshape((1, -1))
            self.ids = [vector_id]
            self.metadata = [metadata]
        else:
            self.ids.append(vector_id)
            self.vectors = np.vstack([self.vectors, np.array(get_ada_embedding(text))])
            self.metadata.append(metadata)


@xai_component
class NumpyMemory(Component):
    memory: OutArg[Memory]

    def execute(self, ctx) -> None:
        self.memory.value = NumpyMemoryImpl()


@xai_component
class VectoMemory(Component):
    api_key: InArg[str]
    vector_space: InCompArg[str]
    initialize: InCompArg[bool]
    memory: OutArg[Memory]

    def execute(self, ctx) -> None:
        from vecto import Vecto

        api_key = os.getenv("VECTO_API_KEY") if self.api_key.value is None else self.api_key.value

        headers = {'Authorization': 'Bearer ' + api_key}
        response = requests.get("https://api.vecto.ai/api/v0/account/space", headers=headers)
        if response.status_code != 200:
            raise Exception(f"Failed to get vector space list: {response.text}")
        for space in response.json():
            if space['name'] == self.vector_space.value:
                vs = Vecto(api_key, space['id'])
                if self.initialize.value:
                    vs.delete_vector_space_entries()
                self.memory.value = VectoMemoryImpl(vs)
                break
        if not self.memory.value:
            raise Exception(f"Could not find vector space with name {self.vector_space.value}")


@xai_component
class PineconeMemory(Component):
    api_key: InArg[str]
    environment: InArg[str]
    index_name: InCompArg[str]
    namespace: InCompArg[str]
    initialize: InCompArg[bool]
    memory: OutArg[Memory]

    def execute(self, ctx) -> None:
        import pinecone

        api_key = os.getenv("PINECONE_API_KEY") if self.api_key.value is None else self.api_key.value
        environment = os.getenv("PINECONE_ENVIRONMENT") if self.environment.value is None else self.environment.value

        pinecone.init(api_key=api_key, environment=environment)

        if self.index_name.value not in pinecone.list_indexes():
            pinecone.create_index(self.index_name.value, dimension=1536, metric='cosine', pod_type='p1')

        index = pinecone.Index(self.index_name.value)

        if self.initialize.value:
            pinecone.delete(deleteAll='true', namespace=self.namespace.value)

        self.memory.value = PineconeMemoryImpl(index, self.namespace.value)


@xai_component
class Toolbelt(Component):
    """A component that aggregates various GPT Agent tool specifications into a unified toolbelt.
    You can add more tools if needed by simply adding it as an additional `InArg`. Ensure to reload node after.

    #### inPorts:
    - tool1, tool2, tool3, tool4, tool5: Specifications for up to five tools to be included in the toolbelt.
    
    #### outPorts:
    - toolbelt_spec: The unified specification for the toolbelt, including the specifications for all included tools.
    """

    tool1: InArg[dict]
    tool2: InArg[dict]
    tool3: InArg[dict]
    tool4: InArg[dict]
    tool5: InArg[dict]
    toolbelt_spec: OutArg[list]

    def execute(self, ctx) -> None:
        spec = []

        if self.tool1.value:
            spec.append(self.tool1.value)
        if self.tool2.value:
            spec.append(self.tool2.value)
        if self.tool3.value:
            spec.append(self.tool3.value)
        if self.tool4.value:
            spec.append(self.tool4.value)
        if self.tool5.value:
            spec.append(self.tool5.value)

        self.toolbelt_spec.value = spec


@xai_component
class Sleep(Component):
    """A simple component that pauses execution for a specified number of seconds.

    #### inPorts:
    - seconds: The number of seconds to pause execution.
    """

    seconds: InArg[int]

    def execute(self, ctx) -> None:
        time.sleep(self.seconds.value)

@xai_component
class ReadFile(Component):
    """A component that reads the contents of a file.

    #### inPorts:
    - file_name: The name of the file to read.

    #### outPorts:
    - content: The contents of the file as a string.
    """

    file_name: InCompArg[str]
    content: OutArg[str]
    
    def execute(self, ctx) -> None:
        s = ""
        with open(self.file_name.value, "r") as f:
            s = "\n".join(f.readlines())
        self.content.value = s


class OutputAgentStatus(Component):
    """A component that generates a status output for an agent.

    #### inPorts:
    - task_list: A list of tasks.
    - text: The text input.
    - results: The result of task execution.

    #### outPorts:
    - content: The JSON-encoded status of the agent.
    """

    task_list: InCompArg[deque]
    text: InArg[str]
    results: InArg[str]
    content: OutArg[str]
    
    def execute(self, ctx) -> None:
        out = {
            'task_list': list(self.task_list.value),
            'result': self.results.value,
            'text': self.text.value
        }
        self.content.value = json.dumps(out)

        
@xai_component
class Confirm(Component):
    """Pauses the python process and asks the user to enter Y/N to continue.
    **Note**: If you use this component, run the compiled script from a terminal.
    """

    prompt: InArg[str]
    decision: OutArg[bool]

    def execute(self, ctx) -> None:
        prompt = self.prompt.value if self.prompt.value else 'Continue?'
        response = input(prompt + '(y/N)')
        if response == 'y' or response == 'Y':
            self.decision.value = True
        else:
            self.decision.value = False



@xai_component
class TestCounter(Component):
    
    def execute(self, ctx) -> None:
        
        if ctx.get("count") == None:
            ctx["count"] = 1 
        else:
            count = ctx.get("count")
            count += 1
            print(count)
            ctx["count"] = count
            if count == 3:
                sys.exit(0)
    
