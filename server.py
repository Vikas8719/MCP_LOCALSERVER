from pathlib import Path
from fastmcp import FastMCP
import os
import re
import subprocess
import json
import uuid
from datetime import datetime, timezone

# -----------------------------
# MCP INIT
# -----------------------------
mcp = FastMCP("ai-project-builder")

# PROJECTS_PATH env variable se path lo.
# Docker ke andar default "/projects" (volume mount point).
# Local Windows run ke liye env var explicitly set karo.
PROJECTS_BASE = Path(os.environ.get("PROJECTS_PATH", "/projects")).resolve()


def safe_path(base: Path, relative: str) -> Path:
    """Security check - path base ke bahar na jaye (path traversal se bachao)."""
    base = base.resolve()
    target = (base / relative).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise ValueError(f"Unsafe path access blocked: {target}")
    return target


def _ensure_base() -> str | None:
    """Return an error string if PROJECTS_BASE doesn't exist, else None."""
    if not PROJECTS_BASE.exists():
        return f"❌ Projects directory nahi mili: {PROJECTS_BASE}"
    return None


# -----------------------------
# FILESYSTEM TOOLS
# -----------------------------

@mcp.tool()
def list_projects() -> str:
    """
    PROJECTS_BASE directory mein saare available projects list karo.
    Koi argument nahi chahiye.
    """
    err = _ensure_base()
    if err:
        return err

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
        available = [d.name for d in PROJECTS_BASE.iterdir() if d.is_dir()] if PROJECTS_BASE.exists() else []
        return f"❌ Project '{project_folder}' nahi mila.\n💡 Available projects: {available}"

    try:
        target = safe_path(base, relative_path)
    except ValueError as e:
        return f"❌ {e}"

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
        available = [d.name for d in PROJECTS_BASE.iterdir() if d.is_dir()] if PROJECTS_BASE.exists() else []
        return f"❌ Project '{project_folder}' nahi mila in {PROJECTS_BASE}\n💡 Available: {available}"

    try:
        file_path = safe_path(base, relative_path)
    except ValueError as e:
        return f"❌ {e}"

    if not file_path.exists():
        return f"❌ File nahi mili: {file_path}"
    if file_path.is_dir():
        return f"❌ Ye file nahi, folder hai. list_files tool use karo."

    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"❌ File binary/non-utf8 hai, text ke roop mein nahi padh sakta: {file_path}"


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

    try:
        file_path = safe_path(base, relative_path)
    except ValueError as e:
        return f"❌ {e}"

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return f"✅ File likh di: {file_path}"


@mcp.tool()
def str_replace_in_file(
    project_folder: str,
    relative_path: str,
    old_str: str,
    new_str: str
) -> str:
    """
    File ke andar sirf ek specific hissa badlo — poori file overwrite nahi hogi.
    Claude Desktop ke str_replace tool jaisi kaam karta hai.

    project_folder: project naam (jaise 'ai-engine')
    relative_path:  file path project ke andar (jaise 'src/index.py')
    old_str:        woh exact text jo replace karna hai (file mein exactly ek baar hona chahiye)
    new_str:        naya text jo old_str ki jagah aayega (khali string se delete ho jaayega)

    Rules:
    - old_str file mein exactly ek baar milna chahiye, warna operation fail ho jaata hai.
    - old_str aur new_str dono leading/trailing whitespace preserve karte hain.
    - Agar old_str nahi mila to helpful error deta hai (first 200 chars of file dikhata hai for context).
    """
    base = PROJECTS_BASE / project_folder
    if not base.exists():
        available = [d.name for d in PROJECTS_BASE.iterdir() if d.is_dir()] if PROJECTS_BASE.exists() else []
        return f"❌ Project '{project_folder}' nahi mila in {PROJECTS_BASE}\n💡 Available: {available}"

    try:
        file_path = safe_path(base, relative_path)
    except ValueError as e:
        return f"❌ {e}"

    if not file_path.exists():
        return f"❌ File nahi mili: {file_path}"
    if file_path.is_dir():
        return f"❌ Ye file nahi, folder hai."

    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"❌ File binary/non-utf8 hai, text edit nahi ho sakti: {file_path}"

    count = content.count(old_str)

    if count == 0:
        preview = content[:300].replace("\n", "↵")
        return (
            f"❌ old_str file mein nahi mila — koi change nahi hua.\n"
            f"📄 File preview (first 300 chars):\n{preview}\n\n"
            f"💡 Tips:\n"
            f"  - Exact whitespace/indentation match karo\n"
            f"  - read_file se content verify karo pehle\n"
            f"  - Multiline text mein \\n newlines sahi hain?"
        )

    if count > 1:
        return (
            f"❌ old_str file mein {count} baar mila — ambiguous hai, koi change nahi hua.\n"
            f"💡 Zyada unique text include karo (surrounding lines bhi) taaki exactly ek match ho."
        )

    new_content = content.replace(old_str, new_str, 1)
    file_path.write_text(new_content, encoding="utf-8")

    lines_changed = new_str.count("\n") - old_str.count("\n")
    sign = "+" if lines_changed >= 0 else ""
    return (
        f"✅ str_replace successful: {file_path}\n"
        f"📊 Lines changed: {sign}{lines_changed}"
    )


@mcp.tool()
def delete_file(project_folder: str, relative_path: str) -> str:
    """
    Project ke andar se koi file delete karo.
    project_folder: project naam
    relative_path: delete karne wali file ka path
    """
    base = PROJECTS_BASE / project_folder

    try:
        file_path = safe_path(base, relative_path)
    except ValueError as e:
        return f"❌ {e}"

    if not file_path.exists():
        return f"❌ File nahi mili: {file_path}"
    file_path.unlink()
    return f"🗑️ File delete ho gayi: {file_path}"


def _wire_agent_into_main(base: Path, agent_name: str) -> str | None:
    """
    main.py mein naye agent ko auto-import karo aur agents=[] list mein add karo.
    Returns main.py ka path agar wiring hui, warna None (agar main.py exist nahi karta).
    """
    main_path = base / "main.py"
    if not main_path.exists():
        return None

    content = main_path.read_text(encoding="utf-8")

    import_line = f"from agents.{agent_name} import {agent_name}"
    if import_line not in content:
        if "from crewai import Crew" in content:
            content = content.replace(
                "from crewai import Crew",
                f"from crewai import Crew\n{import_line}",
                1
            )
        else:
            content = f"{import_line}\n{content}"

    match = re.search(r"agents\s*=\s*\[([^\]]*)\]", content)
    if match:
        existing = [n.strip() for n in match.group(1).split(",") if n.strip()]
        if agent_name not in existing:
            existing.append(agent_name)
            new_list = "agents=[" + ", ".join(existing) + "]"
            content = content[:match.start()] + new_list + content[match.end():]

    main_path.write_text(content, encoding="utf-8")
    return str(main_path)


# -----------------------------
# PROGRESS TRACKING (memory jaisa - naye chat mein poori file padhne se bachata hai)
# -----------------------------

PROGRESS_FILENAME = "_ai_progress.json"
MAX_HISTORY_ENTRIES = 25


def _progress_path(project_folder: str) -> Path:
    base = PROJECTS_BASE / project_folder
    base.mkdir(parents=True, exist_ok=True)
    return base / PROGRESS_FILENAME


def _load_progress(project_folder: str) -> dict:
    p = _progress_path(project_folder)
    if not p.exists():
        return {"summary": "", "status": "not_started", "next_steps": "", "history": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"summary": "", "status": "unknown", "next_steps": "", "history": []}


def _append_history_entry(project_folder: str, entry_text: str) -> None:
    """Internal helper - docker_build/docker_run jaise tools yahan se apna result auto-log kar sakte hain."""
    data = _load_progress(project_folder)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    data.setdefault("history", []).append(f"[{timestamp}] {entry_text}")
    data["history"] = data["history"][-MAX_HISTORY_ENTRIES:]
    _progress_path(project_folder).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


@mcp.tool()
def save_progress(project_folder: str, summary: str, next_steps: str = "", status: str = "in_progress") -> str:
    """
    Project ki current progress save karo - naya chat shuru hone par is se hi continue ho sakta hai,
    poori project files dobara padhne ki zaroorat nahi padti.
    project_folder: project naam
    summary: abhi tak kya ho chuka hai (short, clear)
    next_steps: aage kya karna hai
    status: 'in_progress' / 'blocked' / 'done' (default: in_progress)
    """
    data = _load_progress(project_folder)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    data["summary"] = summary
    data["next_steps"] = next_steps
    data["status"] = status
    data["last_updated"] = timestamp
    data.setdefault("history", []).append(f"[{timestamp}] {summary}")
    data["history"] = data["history"][-MAX_HISTORY_ENTRIES:]

    _progress_path(project_folder).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return f"✅ Progress save ho gayi ({project_folder}/{PROGRESS_FILENAME})"


@mcp.tool()
def get_progress(project_folder: str) -> str:
    """
    Project ki last saved progress padho - naye chat mein sabse pehle ye call karo
    poori files padhne ki jagah, taaki context turant mil jaaye.
    """
    data = _load_progress(project_folder)
    if not data.get("summary") and not data.get("history"):
        return f"📭 '{project_folder}' ke liye abhi tak koi progress save nahi hui."

    history_text = "\n".join(f"  {h}" for h in data.get("history", [])[-10:])
    return (
        f"📋 Progress report: {project_folder}\n"
        f"Status: {data.get('status', 'unknown')}\n"
        f"Last updated: {data.get('last_updated', 'N/A')}\n\n"
        f"Summary:\n{data.get('summary', '(khaali)')}\n\n"
        f"Next steps:\n{data.get('next_steps', '(khaali)')}\n\n"
        f"Recent history:\n{history_text}"
    )


# -----------------------------
# DOCKER - ASYNC/BACKGROUND BUILD (bade projects ke liye - 4 min client timeout se bachne ke liye)
# -----------------------------

# In-memory tracker - jab tak MCP server process zinda hai tab tak yaad rehta hai.
# Server restart hone par ye tracking khatam ho jaati hai (docker build khud chalti reh sakti hai,
# lekin build_id se status check karna tab possible nahi rahega).
_background_builds: dict = {}


@mcp.tool()
def docker_build_start(project_folder: str, dockerfile: str = "Dockerfile", image_tag: str = "") -> str:
    """
    Docker image ka build BACKGROUND mein shuru karo - turant return karta hai, block nahi karta.
    Bade/multi-service projects ke liye zaroori hai jinki build 4 minute se zyada le sakti hai
    (Claude Desktop ka tool-call timeout 4 min hai, isse bachne ke liye ye use karo).
    Build shuru hone ke baad Claude chat mein doosre kaam karta reh sakta hai, aur jab chaho
    docker_build_status(build_id) se progress check kar sakta hai.
    """
    base = PROJECTS_BASE / project_folder
    if not base.exists():
        return f"❌ Project '{project_folder}' nahi mila."

    try:
        dockerfile_path = safe_path(base, dockerfile)
    except ValueError as e:
        return f"❌ {e}"

    if not dockerfile_path.exists():
        return f"❌ Dockerfile nahi mila: {dockerfile_path}"

    tag = (image_tag or project_folder.replace("/", "-").replace("\\", "-")).lower().replace(" ", "-")
    build_id = f"{tag}-{uuid.uuid4().hex[:8]}"

    log_dir = base / ".docker_build_logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"{build_id}.log"
    log_file = open(log_path, "w", encoding="utf-8")

    try:
        proc = subprocess.Popen(
            ["docker", "build", "-t", tag, "-f", str(dockerfile_path), str(base)],
            stdout=log_file, stderr=subprocess.STDOUT
        )
    except FileNotFoundError:
        log_file.close()
        return "❌ 'docker' command nahi mila — Docker Desktop installed aur running hai check karo."

    _background_builds[build_id] = {
        "process": proc,
        "log_file_handle": log_file,
        "log_path": log_path,
        "image_tag": tag,
        "project_folder": project_folder,
        "started_at": datetime.now(timezone.utc),
    }

    _append_history_entry(
        project_folder, f"docker_build_start ({tag}): background build shuru, build_id={build_id}"
    )

    return (
        f"🚀 Build background mein shuru ho gaya (block nahi karega)\n"
        f"build_id: {build_id}\n"
        f"image_tag: {tag}\n\n"
        f"Status check karne ke liye: docker_build_status(build_id=\"{build_id}\")"
    )


@mcp.tool()
def docker_build_status(build_id: str) -> str:
    """
    docker_build_start se shuru kiye gaye background build ka current status check karo.
    build_id: docker_build_start ka response mein mila hua id
    Build abhi bhi chal raha ho to log ka latest hissa dikhata hai; khatam ho gaya ho to
    final result (success/fail) aur poora log dikhata hai.
    """
    entry = _background_builds.get(build_id)
    if not entry:
        return f"❌ build_id '{build_id}' nahi mila. Sahi id docker_build_start ke response se copy kiya?"

    proc = entry["process"]
    return_code = proc.poll()

    try:
        log_tail = entry["log_path"].read_text(encoding="utf-8", errors="replace")[-3000:]
    except OSError:
        log_tail = "(log file abhi padhi nahi ja saki)"

    if return_code is None:
        elapsed = int((datetime.now(timezone.utc) - entry["started_at"]).total_seconds())
        return (
            f"⏳ Abhi bhi chal raha hai (build_id: {build_id}, image: {entry['image_tag']})\n"
            f"{elapsed}s se chal raha hai\n\n"
            f"--- Log (last 3000 chars) ---\n{log_tail}"
        )

    # Build khatam ho gaya - cleanup aur final report
    entry["log_file_handle"].close()
    status = "✅ Build SUCCESSFUL" if return_code == 0 else "❌ Build FAILED"

    _append_history_entry(
        entry["project_folder"], f"docker_build_status ({entry['image_tag']}): {status}, exit code {return_code}"
    )

    try:
        subprocess.run(["docker", "image", "prune", "-f"], capture_output=True, text=True, timeout=30)
    except Exception:
        pass

    return (
        f"{status} (exit code {return_code}, image_tag: {entry['image_tag']})\n\n"
        f"--- Log (last 3000 chars) ---\n{log_tail}"
    )


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
    try:
        path = safe_path(base, f"agents/{agent_name}.py")
    except ValueError as e:
        return f"❌ {e}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(agent_code, encoding="utf-8")

    wired_path = _wire_agent_into_main(base, agent_name)
    if wired_path:
        return f"✅ Agent ban gaya: {path}\n🔗 main.py mein auto-wire ho gaya: {wired_path}"
    return f"✅ Agent ban gaya: {path}\n⚠️ main.py nahi mila is project mein, auto-wire skip ho gaya"


# -----------------------------
# LANGCHAIN
# -----------------------------

@mcp.tool()
def create_langchain_chain(
    project_folder: str,
    chain_name: str,
    prompt_template: str
) -> str:
    """LangChain chain file banao (modern LCEL syntax, no deprecated APIs)"""
    chain_code = f'''from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

prompt = PromptTemplate(
    input_variables=["input"],
    template="{prompt_template}"
)

llm = ChatOpenAI(model="gpt-4o-mini")

# LCEL syntax - LLMChain (deprecated) ki jagah pipe operator use karo
{chain_name} = prompt | llm | StrOutputParser()
'''
    base = PROJECTS_BASE / project_folder
    try:
        path = safe_path(base, f"chains/{chain_name}.py")
    except ValueError as e:
        return f"❌ {e}"
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
    try:
        path = safe_path(base, "ag2_setup.py")
    except ValueError as e:
        return f"❌ {e}"
    path.write_text(ag2_code, encoding="utf-8")
    return f"✅ AG2 setup ban gaya: {path}"


# -----------------------------
# DOCKER (scoped: sirf project folder ke andar, sirf docker command)
# -----------------------------

@mcp.tool()
def docker_build(project_folder: str, image_tag: str = "", dockerfile: str = "Dockerfile") -> str:
    """
    Project ke folder mein maujood Dockerfile se Docker image build karo.
    project_folder: project naam (isme Dockerfile hona chahiye)
    image_tag: image ka naam (default: project_folder ka lowercase naam)
    dockerfile: Dockerfile ka relative path (default 'Dockerfile')
    Build ka poora stdout/stderr aur exit code return karta hai taaki errors dikh sake.
    """
    base = PROJECTS_BASE / project_folder
    if not base.exists():
        return f"❌ Project '{project_folder}' nahi mila."

    try:
        dockerfile_path = safe_path(base, dockerfile)
    except ValueError as e:
        return f"❌ {e}"

    if not dockerfile_path.exists():
        return f"❌ Dockerfile nahi mila: {dockerfile_path}"

    tag = (image_tag or project_folder).lower().replace(" ", "-")

    try:
        result = subprocess.run(
            ["docker", "build", "-t", tag, "-f", str(dockerfile_path), str(base)],
            capture_output=True, text=True, timeout=600
        )
    except FileNotFoundError:
        return "❌ 'docker' command nahi mila — Docker Desktop installed aur running hai check karo."
    except subprocess.TimeoutExpired:
        return "❌ Build 10 minute se zyada le raha tha, timeout ho gaya."

    status = "✅ Build SUCCESSFUL" if result.returncode == 0 else "❌ Build FAILED"

    # Auto-log: progress history mein result likh do, Claude ko yaad rakhne ki zaroorat nahi
    _append_history_entry(
        project_folder,
        f"docker_build ({tag}): {status}, exit code {result.returncode}"
    )

    # Har rebuild purani <none> tag wali dangling image chhod jaata hai —
    # isse cleanup taaki fix-loop ke dauran disk space na bhare
    prune_note = ""
    try:
        prune_result = subprocess.run(
            ["docker", "image", "prune", "-f"],
            capture_output=True, text=True, timeout=30
        )
        prune_note = f"\n🧹 Dangling images cleanup: {prune_result.stdout.strip()}"
    except Exception:
        prune_note = "\n⚠️ Dangling images cleanup skip ho gaya (docker prune fail hua)"

    return (
        f"{status} (exit code {result.returncode}, image tag: {tag})\n\n"
        f"--- STDOUT (last 4000 chars) ---\n{result.stdout[-4000:]}\n\n"
        f"--- STDERR (last 4000 chars) ---\n{result.stderr[-4000:]}"
        f"{prune_note}"
    )


@mcp.tool()
def docker_run(project_folder: str, image_tag: str = "", volume_mount: str = "", timeout_seconds: int = 60) -> str:
    """
    Pehle se build ki hui Docker image ko run karo aur uska output/logs capture karo.
    project_folder: project naam (image_tag default isi se banega)
    image_tag: run karne wali image ka naam (default: project_folder ka lowercase naam)
    volume_mount: optional volume mount jaise 'E:\\Projects:/projects' (agar container ko project files chahiye)
    timeout_seconds: kitni der tak container ko chalne dena hai (default 60s, short-lived tasks ke liye)
    """
    tag = (image_tag or project_folder).lower().replace(" ", "-")
    args = ["docker", "run", "--rm"]
    if volume_mount:
        args += ["-v", volume_mount]
    args.append(tag)

    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout_seconds)
    except FileNotFoundError:
        return "❌ 'docker' command nahi mila — Docker Desktop installed aur running hai check karo."
    except subprocess.TimeoutExpired:
        return (
            f"⚠️ Container {timeout_seconds}s ke baad bhi chal raha tha (timeout). "
            f"Agar ye ek long-running server hai (jaise MCP stdio server), to ye normal ho sakta hai."
        )

    status = "✅ Run finished" if result.returncode == 0 else "❌ Run FAILED"

    _append_history_entry(
        project_folder,
        f"docker_run ({tag}): {status}, exit code {result.returncode}"
    )

    return (
        f"{status} (exit code {result.returncode}, image tag: {tag})\n\n"
        f"--- STDOUT (last 4000 chars) ---\n{result.stdout[-4000:]}\n\n"
        f"--- STDERR (last 4000 chars) ---\n{result.stderr[-4000:]}"
    )


@mcp.tool()
def docker_cleanup() -> str:
    """
    Docker ka disk space cleanup karo — SAFE cleanup, sirf ye hataega:
      - stopped/exited containers (running containers ko touch nahi karta)
      - dangling/untagged (<none>) images (aapki named/tagged images ko touch nahi karta)
    Naya build-test-fix loop chalane se pehle ya baad mein use karo taaki system na bhare.
    """
    try:
        containers = subprocess.run(
            ["docker", "container", "prune", "-f"],
            capture_output=True, text=True, timeout=30
        )
        images = subprocess.run(
            ["docker", "image", "prune", "-f"],
            capture_output=True, text=True, timeout=30
        )
    except FileNotFoundError:
        return "❌ 'docker' command nahi mila — Docker Desktop installed aur running hai check karo."
    except subprocess.TimeoutExpired:
        return "❌ Cleanup timeout ho gaya."

    return (
        f"🧹 Stopped containers cleanup:\n{containers.stdout.strip() or '(kuch nahi tha)'}\n\n"
        f"🧹 Dangling images cleanup:\n{images.stdout.strip() or '(kuch nahi tha)'}"
    )


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    mcp.run()