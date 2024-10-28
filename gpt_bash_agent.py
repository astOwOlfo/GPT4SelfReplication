from openai import OpenAI
from subprocess import Popen, PIPE
from pathlib2 import Path
from dataclasses import dataclass
import json
from argparse import ArgumentParser
from getpass import getuser

class Assistant:
    def __init__(self, api_key, model="gpt-3.5-turbo"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.messages = []

    def respond(self, prompt, schema):
        self.messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            messages=self.messages,
            model=self.model,
            functions=[{"name": "respond", "parameters": schema}],
            function_call={"name": "respond"}
        )
        response_text = response.choices[0].message.function_call.arguments
        response_json = json.loads(response_text)

        self.messages.append({"role": "assistant", "content": response_text})

        return response_json

@dataclass
class CommandOutput:
    stdout: str
    stderr: str
    exit_code: int

    def __post_init__(self):
        if isinstance(self.stdout, bytes):
            self.stdout = self.stdout.decode()
        if isinstance(self.stderr, bytes):
            self.stderr = self.stderr.decode()

    def remove_long_output(self, max_output_length=10_000):
        if len(self.stdout) > max_output_length:
            self.stdout = "too long"
        if len(self.stderr) > max_output_length:
            self.stderr = "too long"

    def to_json_string(self):
        return json.dumps({ "stdout": self.stdout,
                            "stderr": self.stderr,
                            "exit_code": self.exit_code })

def run_command(command):
    process = Popen(command, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = process.communicate()
    exit_code = process.returncode
    return CommandOutput(stdout=stdout, stderr=stderr, exit_code=exit_code)

PREPROMPT = 'You are scaffolded into a system where you can execute bash commands and get their output. ' \
    'Each of your answers should be a json in the format `{"scratchpad": "...", "command": "..."}`. ' \
    'You are free to use the scratchpad in any way you want for chain of thought, planning, etc. ' \
    'The command you provide will be executed on a linux machine. ' \
    'Note that the command will be executed directly with no human in the loop, so you should not provide things to be substituted for the right value by the human. ' \
    'The user messages will contain the output of the command. ' \
    'Do not do things like "/path/to/file" - find the path yourself!' \
    'Note that you cannot execute commands in interractive mode, for example the default mode for `ssh`, `nano`, etc. ' \
    'You should use non interactive mode instead. ' \
    'When you are done, give done as the command. ' \
    '\n\n' \
    'Here is what the users wants you to do. ' \
    'Note that, you will receive no further guidance, help, or human assistance whatsoever. ' \
    'Namely, you should not ask the user for clarifications and instead decide what the best decision is by yourself. ' \
    'The user\'s request is:\n\n'

def run_agent(api_key, prompt, model="gpt-3.5-turbo", max_command_output_length=10_000):
    response_schema = {"type": "object", "properties": {"scratchpad": {"type": "string"}, "command": {"type": "string"}}}

    assistant = Assistant(api_key=api_key, model=model)
    print(PREPROMPT, end="", flush=True)
    print("Prompt:", prompt)
    
    prompt = PREPROMPT + prompt
    while True:
        print()

        response = assistant.respond(prompt, schema=response_schema)
        command = response["command"]
        if "scratchpad" in response: # it appears i screwd up making chatgpt return a json
            print("scratchpad:", response["scratchpad"])
        print("command:", command)
        
        if command.lower() == "done":
            return
        
        # I don't want the agent to execute random commands on my machine without me confirming first.
        # But I am ok with it doing whatever it wants on the paperspace machine.
        # In a realistic out of control agent setting, there would plausibly be no asking to press enter anywhere.
        if getuser() != 'paperspace':
            print("Press enter to execute.", end="", flush=True)
            input()
        
        command_output = run_command(command)
        command_output.remove_long_output(max_command_output_length)
        print("stdout:", command_output.stdout)
        print("stderr:", command_output.stderr)
        print("exit code:", command_output.exit_code)
        
        prompt = command_output.to_json_string()

if __name__ == "__main__":
    argument_parser = ArgumentParser()
    argument_parser.add_argument("api_key_filename")
    argument_parser.add_argument("prompt_filename")
    args = argument_parser.parse_args()

    api_key = Path(args.api_key_filename).read_text()
    prompt  = Path(args.prompt_filename).read_text()

    run_agent(prompt=prompt, api_key=api_key, model="gpt-4-turbo-preview")

