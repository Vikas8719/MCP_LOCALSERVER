from pathlib import Path
from fastmcp import FastMCP
import os

# -----------------------------
# MCP INIT
# -----------------------------
mcp = FastMCP("ai-project-builder")

# PROJECT_FOLDER env variable se path lo, default E:/Projects
PROJECTS_BASE = Path(os.environ.get("PROJECT_FOLDER", "E:/Projects"))

def safe_path(base: Path, relative: str) -> Path:
    """Security check - path base ke bahar na jaye"""
    target = (base / relative).resolve()
    if not str(target).startswith(str(base.resolve())):
        raise ValueError(f"Unsafe path access: {target}")
    return target

# -----------------------------
# FILESYSTEM TOOLS
# -----------------------------

@mcp.tool()
def list_projects() -> str:
    """
    E:/Projects directory mein saare available projects list karo.
    Koi argument nahi chahiye.
    """
    if not PROJECTS_BASE.exists():
        return f"❌ Projects directory nahi mili: {PROJECTS_BASE}"

    items = [d.name for d in PROJECTS_BASE.iterdir() if d.is_dir()]
    if not items:
        return f"📂 Koi project nahi mila: {PROJECTS_BASE}"

    return f"📂 Projects in {PROJECTS_BASE}:\n" + "\n".join(f"  - {p}" for p in sorted(items))


@mcp.tool()
def list_files(project_folder: str, relative_path: str = ".") -> str:
    """
    Kisi project ke andar files aur folders list karo.
    project_folder: project ka naam (jaise 'ai-engine')
    relative_path: subfolder path, root ke liye '.' use karo (default: '.')
    """
    base = PROJECTS_BASE / project_folder
    if not base.exists():
        available = [d.name for d in PROJECTS_BASE.iterdir() if d.is_dir()]
        return f"❌ Project '{project_folder}' nahi mila.\n💡 Available projects: {available}"

    target = safe_path(base, relative_path)
    if not target.exists():
        return f"❌ Path nahi mila: {target}"
    if not target.is_dir():
        return f"❌ Ye directory nahi hai: {target}"

    lines = [f"📁 {target} ka content:\n"]
    for item in sorted(target.iterdir()):
        icon = "📁" if item.is_dir() else "📄"
        size = f"  ({item.stat().st_size} bytes)" if item.is_file() else ""
        lines.append(f"  {icon} {item.name}{size}")

    return "\n".join(lines) if len(lines) > 1 else f"📂 Folder khali hai: {target}"


@mcp.tool()
def read_file(project_folder: str, relative_path: str) -> str:
    """
    Project ke andar se koi file padho.
    project_folder: project naam (jaise 'ai-engine')
    relative_path: file ka path project ke andar (jaise 'src/server.js')
    """
    base = PROJECTS_BASE / project_folder
    if not base.exists():
        available = [d.name for d in PROJECTS_BASE.iterdir() if d.is_dir()]
        return f"❌ Project '{project_folder}' nahi mila in {PROJECTS_BASE}\n💡 Available: {available}"

    file_path = safe_path(base, relative_path)
    if not file_path.exists():
        return f"❌ File nahi mili: {file_path}"
    if file_path.is_dir():
        return f"❌ Ye file nahi, folder hai. list_files tool use karo."

    return file_path.read_text(encoding="utf-8")


@mcp.tool()
def write_file(project_folder: str, relative_path: str, content: str) -> str:
    """
    Project ke andar koi file likho ya create karo.
    project_folder: project naam (jaise 'ai-engine')
    relative_path: file path project ke andar (jaise 'src/index.py')
    content: file mein likhne wala content
    """
    base = PROJECTS_BASE / project_folder
    base.mkdir(parents=True, exist_ok=True)
    file_path = safe_path(base, relative_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return f"✅ File likh di: {file_path}"


@mcp.tool()
def delete_file(project_folder: str, relative_path: str) -> str:
    """
    Project ke andar se koi file delete karo.
    project_folder: project naam
    relative_path: delete karne wali file ka path
    """
    base = PROJECTS_BASE / project_folder
    file_path = safe_path(base, relative_path)
    if not file_path.exists():
        return f"❌ File nahi mili: {file_path}"
    file_path.unlink()
    return f"🗑️ File delete ho gayi: {file_path}"


# -----------------------------
# CREWAI
# -----------------------------

@mcp.tool()
def create_crewai_project(project_folder: str) -> str:
    """CrewAI project structure banao"""
    base = PROJECTS_BASE / project_folder
    base.mkdir(parents=True, exist_ok=True)
    for folder in ["agents", "tasks", "tools"]:
        (base / folder).mkdir(exist_ok=True)
    main_py = """from crewai import Crew

crew = Crew(
    agents=[],
    tasks=[],
    verbose=True
)

if __name__ == "__main__":
    print(crew.kickoff())
"""
    (base / "main.py").write_text(main_py, encoding="utf-8")
    return f"✅ CrewAI project ban gaya: {base}"


@mcp.tool()
def create_crewai_agent(
    project_folder: str,
    agent_name: str,
    role: str,
    goal: str,
    backstory: str
) -> str:
    """CrewAI agent file banao"""
    agent_code = f'''from crewai import Agent

{agent_name} = Agent(
    role="{role}",
    goal="{goal}",
    backstory="{backstory}",
    verbose=True
)
'''
    base = PROJECTS_BASE / project_folder
    path = safe_path(base, f"agents/{agent_name}.py")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(agent_code, encoding="utf-8")
    return f"✅ Agent ban gaya: {path}"


# -----------------------------
# LANGCHAIN
# -----------------------------

@mcp.tool()
def create_langchain_chain(
    project_folder: str,
    chain_name: str,
    prompt_template: str
) -> str:
    """LangChain chain file banao"""
    chain_code = f'''from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

prompt = PromptTemplate(
    input_variables=["input"],
    template="{prompt_template}"
)

llm = ChatOpenAI(model="gpt-4o-mini")

{chain_name} = LLMChain(llm=llm, prompt=prompt)
'''
    base = PROJECTS_BASE / project_folder
    path = safe_path(base, f"chains/{chain_name}.py")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(chain_code, encoding="utf-8")
    return f"✅ LangChain chain ban gayi: {path}"


# -----------------------------
# AG2 / AUTOGEN
# -----------------------------

@mcp.tool()
def create_ag2_setup(project_folder: str) -> str:
    """AG2/AutoGen setup file banao"""
    ag2_code = """from autogen import AssistantAgent, UserProxyAgent

assistant = AssistantAgent(
    name="assistant",
    llm_config={"model": "gpt-4o-mini"}
)

user_proxy = UserProxyAgent(
    name="user_proxy",
    human_input_mode="NEVER"
)

# user_proxy.initiate_chat(assistant, message="Apna kaam yahan likhein")
"""
    base = PROJECTS_BASE / project_folder
    path = safe_path(base, "ag2_setup.py")
    path.write_text(ag2_code, encoding="utf-8")
    return f"✅ AG2 setup ban gaya: {path}"


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    mcp.run()
