#!/usr/bin/env python3
"""
M3 Agent - A Claude Code-style terminal agent powered by MiniMax M3 via NVIDIA NIM.
Usage: python3 m3agent.py [project_directory]
"""

import requests
import os
import sys
import subprocess
import json
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
API_KEY = os.environ.get("NVIDIA_API_KEY", "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")
API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL   = "minimaxai/minimax-m3"

# ── Tools M3 can call ─────────────────────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file in the project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file (relative to project root or absolute)"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and folders in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list (default: project root)"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or overwrite a file with given content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write into the file"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command in the project directory and return output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_files",
            "description": "Search for a string or pattern across files in the project (like grep).",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Text or regex pattern to search for"},
                    "file_glob": {"type": "string", "description": "File glob pattern e.g. '*.py' (default: all files)"}
                },
                "required": ["pattern"]
            }
        }
    }
]

# ── Tool executor ─────────────────────────────────────────────────────────────
def execute_tool(name: str, args: dict, project_root: Path) -> str:
    try:
        if name == "read_file":
            p = project_root / args["path"] if not os.path.isabs(args["path"]) else Path(args["path"])
            if not p.exists():
                return f"Error: File not found: {p}"
            return p.read_text(errors="replace")

        elif name == "list_directory":
            p = project_root / args.get("path", "") if args.get("path") else project_root
            if not p.exists():
                return f"Error: Directory not found: {p}"
            lines = []
            for item in sorted(p.iterdir()):
                prefix = "📁 " if item.is_dir() else "📄 "
                lines.append(f"{prefix}{item.name}")
            return "\n".join(lines) if lines else "(empty directory)"

        elif name == "write_file":
            p = project_root / args["path"] if not os.path.isabs(args["path"]) else Path(args["path"])
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(args["content"])
            return f"✅ Written: {p}"

        elif name == "run_command":
            result = subprocess.run(
                args["command"], shell=True, cwd=project_root,
                capture_output=True, text=True, timeout=30
            )
            out = result.stdout + result.stderr
            return out.strip() if out.strip() else "(no output)"

        elif name == "search_in_files":
            glob = args.get("file_glob", "*")
            pattern = args["pattern"]
            cmd = f'grep -rn "{pattern}" --include="{glob}" .'
            result = subprocess.run(cmd, shell=True, cwd=project_root, capture_output=True, text=True)
            return result.stdout.strip() or f"No matches found for '{pattern}'"

        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        return f"Tool error: {e}"

# ── Call M3 ───────────────────────────────────────────────────────────────────
def call_m3(messages: list) -> dict:
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "max_tokens": 4096,
        "temperature": 0.7,
        "top_p": 0.95,
        "stream": False,
    }
    resp = requests.post(API_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()

# ── Agent loop ────────────────────────────────────────────────────────────────
def agent_loop(user_prompt: str, messages: list, project_root: Path) -> str:
    messages.append({"role": "user", "content": user_prompt})

    while True:
        data = call_m3(messages)
        choice = data["choices"][0]
        msg = choice["message"]
        finish = choice["finish_reason"]

        messages.append(msg)

        # Done — return text reply
        if finish == "stop" or not msg.get("tool_calls"):
            return msg.get("content", "")

        # M3 wants to call tools
        tool_results = []
        for tc in msg["tool_calls"]:
            fn_name = tc["function"]["name"]
            fn_args = json.loads(tc["function"]["arguments"])

            print(f"\n  🔧 {fn_name}({', '.join(f'{k}={repr(v)}' for k,v in fn_args.items())})")
            result = execute_tool(fn_name, fn_args, project_root)
            print(f"  ↳ {result[:200]}{'...' if len(result) > 200 else ''}")

            tool_results.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result
            })

        messages.extend(tool_results)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    # Determine project root
    if len(sys.argv) > 1:
        project_root = Path(sys.argv[1]).resolve()
    else:
        project_root = Path.cwd()

    if not project_root.exists():
        print(f"❌ Directory not found: {project_root}")
        sys.exit(1)

    print(f"\n🤖 M3 Agent — MiniMax M3 via NVIDIA NIM")
    print(f"📂 Project: {project_root}")
    print(f"Type your prompt and press Enter. Type 'exit' or Ctrl+C to quit.\n")

    system_prompt = f"""You are an expert AI coding assistant (like Claude Code) running inside a software project.

Project root: {project_root}

You have access to tools to:
- Read files
- List directories  
- Write/edit files
- Run shell commands
- Search across the codebase

When the user asks about the codebase, explore it using your tools before answering.
Always read relevant files before making changes. Be concise but thorough.
When writing code, match the existing style of the project."""

    messages = [{"role": "system", "content": system_prompt}]

    while True:
        try:
            user_input = input("\n You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 Bye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("👋 Bye!")
            break

        print("\n⏳ M3 thinking...\n")
        try:
            reply = agent_loop(user_input, messages, project_root)
            print(f"\n🤖 M3: {reply}")
        except requests.HTTPError as e:
            print(f"❌ API error: {e.response.status_code} — {e.response.text}")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
