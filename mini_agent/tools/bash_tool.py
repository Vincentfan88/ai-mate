"""Bash command execution tool."""

import asyncio
from typing import Any, Dict

from .base import Tool, ToolResult


class BashTool(Tool):
    """Execute bash commands."""

    @property
    def name(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return """Execute a bash command and return the output.

IMPORTANT RESTRICTIONS:
- DO NOT run long-running/blocking commands like: web servers (python -m http.server, npm start, etc.), 
  interactive programs (nano, vim, less, top, htop, etc.), or any command that waits for user input.
- DO NOT run commands that stream output continuously (tail -f, watch, etc.)
- For services/servers, use background mode by adding '&' at the end: 'python3 -m http.server 8080 &'
- Timeout is set to 60 seconds by default. Commands running longer will be killed.
- If you need to start a server, run it in background mode and inform the user how to access it.

GOOD examples:
  - ls -la
  - cat file.txt
  - grep "pattern" file.txt
  - python3 script.py
  - python3 -m http.server 8080 &  (with & for background)
  
BAD examples (will timeout/block):
  - python3 -m http.server 8080  (without &)
  - npm start
  - node server.js
  - tail -f logfile
  - vim file.txt"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute. MUST NOT be a long-running/blocking command (web servers, interactive programs, etc.). Add '&' for background execution if needed.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 60)",
                    "default": 60,
                },
            },
            "required": ["command"],
        }

    async def execute(self, command: str, timeout: int = 60) -> ToolResult:
        """Execute bash command.

        Automatically detects and handles background commands (ending with &).
        Background commands will have their output redirected to avoid blocking.
        """
        try:
            # Check if this is a background command
            is_background = command.strip().endswith("&")

            if is_background:
                # For background commands, redirect output to avoid pipe blocking
                # Remove trailing &, add output redirection, then add & back
                base_command = command.strip().rstrip("&").strip()
                # Use nohup and redirect to temp file, capture PID
                command = f"nohup {base_command} > /tmp/bg_output_$$.log 2>&1 & echo $!"

            # Run command with timeout
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(
                    success=False,
                    content="",
                    error=f"Command timed out after {timeout} seconds",
                )

            # Decode output
            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")

            # Special handling for background commands
            if is_background:
                pid = stdout_text.strip()
                if pid and pid.isdigit():
                    return ToolResult(
                        success=True,
                        content=f"✓ Background process started with PID: {pid}\nOutput redirected to: /tmp/bg_output_{pid}.log\n\nTo check status: ps -p {pid}\nTo view logs: tail -f /tmp/bg_output_{pid}.log\nTo stop: kill {pid}",
                    )
                else:
                    # Fallback if we couldn't get PID
                    return ToolResult(
                        success=True,
                        content=f"✓ Background process started\n{stdout_text}",
                    )

            # Combine stdout and stderr for regular commands
            output = stdout_text
            if stderr_text:
                output += f"\n[stderr]:\n{stderr_text}"

            # Check return code
            if process.returncode == 0:
                return ToolResult(success=True, content=output or "(no output)")
            else:
                # Build detailed error message
                error_msg = f"Command failed with exit code {process.returncode}"
                if stderr_text:
                    error_msg += f"\nStderr: {stderr_text.strip()}"

                return ToolResult(
                    success=False,
                    content=output,
                    error=error_msg,
                )

        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))
