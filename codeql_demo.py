import subprocess

ALLOWED = {
    "list": ["dir"]
}

def execute_command(cmd):
    if cmd not in ALLOWED:
        raise ValueError("Command not allowed")

    return subprocess.run(
        ALLOWED[cmd],
        shell=False,
        capture_output=True,
        text=True
    )