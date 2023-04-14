import abc
from collections import deque
import re
from dotenv import load_dotenv
import os
import openai
import requests
import sqlite3
import subprocess
import time
from xai_components.base import InArg, OutArg, InCompArg, Component, BaseComponent, xai_component

load_dotenv()

DEFAULT_EXECUTOR_PROMPT = """
You are an AI who performs one task based on the following objective: {objective}.
Take into account these previously completed tasks: {context}
Scratch Path:
{scratch_pad}
Your task: {task}
Your tools: {tools}
You can use a tool by writing TOOL: TOOL_NAME in a single line. then the arguments of the tool (if any)
For example, to use the python-exec tool, write
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
            ret += tool["instance"].run_tool(tool_code)

    return ret


def llm_call(model: str, prompt: str, temperature: float = 0.5, max_tokens: int = 100):
    while True:
        try:
            if model == 'gpt-3.5-turbo' or model == 'gpt-4':
                messages = [{"role": "system", "content": prompt}]
                response = openai.ChatCompletion.create(
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
        except openai.error.RateLimitError:
            print("Rate limit error, sleeping for 10 seconds...")
            time.sleep(10)
        except openai.error.ServiceUnavailableError:
            print("Service unavailable error, sleeping for 10 seconds...")
            time.sleep(10)
        else:
            break

def get_sorted_context(memory: Memory, query: str, n: int):
    results = memory.query(query, n)
    sorted_results = sorted(results.results, key=lambda x: x.similarity, reverse=True)
    return [(str(item.attributes['task'])) for item in sorted_results]


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
            "tools": self.tools.value
        })
        result = llm_call(self.model.value, prompt, 0.7, 2000)

        print(f"Result:\n{result}")

        self.action.value = result
        self.task.value = task


@xai_component
class TaskCriticAgent(Component):
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
    action: InArg[str]
    memory: InCompArg[Memory]
    task: InArg[dict]
    tools: InArg[list]
    result: OutArg[str]

    def execute(self, ctx) -> None:
        tools = self.action.value.split("TOOL: ")
        result = self.action.value + "\n"
        for tool in tools:
            result += run_tool(tool, self.tools.value)

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


TOOL_SPEC_PYTHON = """
Execute python code in a virtual environment.  
Use by writing the code within markdown code blocks. 
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
        print(f"Will run the code: {tool_code}")
        time.sleep(3)
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
Your internal monologue. Written to yourself in second-person. 
Write out any notes that should help you with the progress of your task.
Example: TOOL: scratch-pad
Thoughts go here.
"""


@xai_component
class ScratchPadTool(Component):
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
        return self.vs.lookup(query, 'TEXT', n)
    def add(self, id: str, text: str, metadata: dict) -> None:
        from vecto import vecto_toolbelt

        vecto_toolbelt.ingest_text(self.vs, [text], [metadata])


class PineconeMemoryImpl(Memory):
    def __init__(self, index, namespace):
        self.index = index
        self.namespace = namespace

    def get_ada_embedding(text):
        text = text.replace("\n", " ")
        return openai.Embedding.create(input=[text], model="text-embedding-ada-002")[
            "data"
        ][0]["embedding"]

    def query(self, query: str, n: int) -> list:
        return self.index.query(self.get_ada_embedding(query), top_k=n, include_metadata=True, namespace=self.namespace)

    def add(self, id: str, text: str, metadata: dict) -> None:
        self.index.upsert([(id, self.get_ada_embedding(text), metadata)], namespace=self.namespace)


@xai_component
class VectoMemory(Component):
    api_key: InArg[str]
    vector_space: InCompArg[str]
    initialize: InCompArg[bool]
    memory: OutArg[object]

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
    seconds: InArg[int]

    def execute(self, ctx) -> None:
        time.sleep(self.seconds.value)
