import subprocess


def run_command(cmd):
    """
    Execute a command safely without using shell=True.
    """
    result = subprocess.run(
        cmd.split(),
        capture_output=True,
        text=True,
        check=False
    )

    return result.stdout


if __name__ == "__main__":
    output = run_command("echo Hello")
    print(output)