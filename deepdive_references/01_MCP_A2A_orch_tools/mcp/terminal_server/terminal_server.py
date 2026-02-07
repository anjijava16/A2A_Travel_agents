import os
from mcp.server.fastmcp import FastMCP
import subprocess


mcp = FastMCP("terminal_server")

DEFAULT_DIR = os.path.expanduser("/Users/welcome/Desktop/Tech_Repos")


@mcp.tool("terminal_server")
async def run_command(command: str) -> str:
    """
    Run a terminal command and return the output.

    Args:
        command (str): The terminal command to execute.
    Returns:
        str: The output of the command or an error message.

    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=DEFAULT_DIR,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout + result.stderr
        return output if output else "Command executed with no output."
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return f"Error executing command: {str(e)}"
    

if __name__ == "__main__":
    mcp.run(transport="stdio")
