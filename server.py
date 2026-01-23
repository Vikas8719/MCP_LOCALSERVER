import os
import sys
import json
from fastmcp import FastMCP

# -----------------------------
# ROOT FOLDER (dynamic + safe fallback)
# -----------------------------
DEFAULT_FOLDER = r"E:\claude-bridge\dataset"
DATA_FOLDER = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FOLDER
DATA_FOLDER = os.path.abspath(DATA_FOLDER)

# -----------------------------
# HELPER: list files
# -----------------------------
def list_files():
    try:
        return [
            f for f in os.listdir(DATA_FOLDER)
            if os.path.isfile(os.path.join(DATA_FOLDER, f))
        ]
    except Exception:
        return []

# -----------------------------
# Initialize MCP server
# -----------------------------
mcp = FastMCP("claude-bridge")

# -----------------------------
# BASIC TOOLS
# -----------------------------
@mcp.tool()
def ping() -> str:
    """Check if server is running"""
    return "pong"

@mcp.tool()
def add_numbers(a: float, b: float) -> float:
    """Add two numbers"""
    return a + b

@mcp.tool()
def say_hello(name: str) -> str:
    """Say hello"""
    return f"Hello, {name}!"

# -----------------------------
# READ FILE (SAFE)
# -----------------------------
@mcp.tool()
def read_file(filename: str) -> str:
    """
    Read a file from the allowed root folder only.
    """
    try:
        full_path = os.path.abspath(os.path.join(DATA_FOLDER, filename))

        if not full_path.startswith(DATA_FOLDER):
            return "❌ Access denied: outside allowed folder"

        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    except FileNotFoundError:
        return "❌ File not found"
    except Exception as e:
        return f"❌ Error reading file: {str(e)}"

# -----------------------------
# LIST FILES
# -----------------------------
@mcp.tool()
def list_dataset_files() -> list:
    """List all files in the root folder"""
    return list_files()

# -----------------------------
# WRITE FILE (🔥 NEW POWER)
# -----------------------------
@mcp.tool()
def write_file(filename: str, content: str) -> str:
    """
    Create or overwrite a file inside the allowed root folder only.
    """
    try:
        full_path = os.path.abspath(os.path.join(DATA_FOLDER, filename))

        if not full_path.startswith(DATA_FOLDER):
            return "❌ Access denied: outside allowed folder"

        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        return f"✅ File written: {full_path}"

    except Exception as e:
        return f"❌ Write error: {str(e)}"

# -----------------------------
# RUN THE MCP SERVER
# -----------------------------
if __name__ == "__main__":
    mcp.run(transport="stdio", show_banner=True)
