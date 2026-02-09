from pathlib import Path
from fastmcp import FastMCP

# -----------------------------
# MCP INIT
# -----------------------------
mcp = FastMCP("ai-project-builder")

DESKTOP = Path.home() / "OneDrive" / "Desktop"

def safe_path(base: Path, relative: str) -> Path:
    target = (base / relative).resolve()
    if not str(target).startswith(str(base.resolve())):
        raise ValueError("Unsafe path access")
    return target

# -----------------------------
# FILESYSTEM TOOL
# -----------------------------
@mcp.tool()
def write_file(project_folder: str, relative_path: str, content: str) -> str:
    """
    Write a file inside Desktop/project_folder
    """
    base = DESKTOP / project_folder
    base.mkdir(parents=True, exist_ok=True)

    file_path = safe_path(base, relative_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")

    return f"✅ File written: {file_path}"

@mcp.tool()
def read_file(project_folder: str, relative_path: str) -> str:
    """
    Read a file from Desktop/project_folder
    """
    base = DESKTOP / project_folder
    file_path = safe_path(base, relative_path)

    return file_path.read_text(encoding="utf-8")

# -----------------------------
# CREWAI
# -----------------------------
@mcp.tool()
def create_crewai_project(project_folder: str) -> str:
    base = DESKTOP / project_folder
    base.mkdir(parents=True, exist_ok=True)

    for folder in ["agents", "tasks", "tools"]:
        (base / folder).mkdir(exist_ok=True)

    main_py = """
from crewai import Crew

crew = Crew(
    agents=[],
    tasks=[],
    verbose=True
)

if __name__ == "__main__":
    print(crew.kickoff())
"""
    (base / "main.py").write_text(main_py, encoding="utf-8")
    return f"✅ CrewAI project created at {base}"

@mcp.tool()
def create_crewai_agent(
    project_folder: str,
    agent_name: str,
    role: str,
    goal: str,
    backstory: str
) -> str:
    agent_code = f'''
from crewai import Agent

{agent_name} = Agent(
    role="{role}",
    goal="{goal}",
    backstory="{backstory}",
    verbose=True
)
'''
    base = DESKTOP / project_folder
    path = safe_path(base, f"agents/{agent_name}.py")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(agent_code, encoding="utf-8")

    return f"✅ CrewAI agent created: {path}"

# -----------------------------
# LANGCHAIN
# -----------------------------
@mcp.tool()
def create_langchain_chain(
    project_folder: str,
    chain_name: str,
    prompt_template: str
) -> str:
    chain_code = f'''
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

prompt = PromptTemplate(
    input_variables=["input"],
    template="{prompt_template}"
)

llm = ChatOpenAI(model="gpt-4o-mini")

{chain_name} = LLMChain(
    llm=llm,
    prompt=prompt
)
'''
    base = DESKTOP / project_folder
    path = safe_path(base, f"chains/{chain_name}.py")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(chain_code, encoding="utf-8")

    return f"✅ LangChain chain created: {path}"

# -----------------------------
# AG2 / AUTOGEN
# -----------------------------
@mcp.tool()
def create_ag2_setup(project_folder: str) -> str:
    ag2_code = """
from autogen import AssistantAgent, UserProxyAgent

assistant = AssistantAgent(
    name="assistant",
    llm_config={"model": "gpt-4o-mini"}
)

user_proxy = UserProxyAgent(
    name="user_proxy",
    human_input_mode="NEVER"
)

# user_proxy.initiate_chat(assistant, message="Your task here")
"""
    base = DESKTOP / project_folder
    path = safe_path(base, "ag2_setup.py")
    path.write_text(ag2_code, encoding="utf-8")

    return f"✅ AG2 setup created: {path}"

# -----------------------------
# RUN SERVER
# -----------------------------
if __name__ == "__main__":
    mcp.run()
