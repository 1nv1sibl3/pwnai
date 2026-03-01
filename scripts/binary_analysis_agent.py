#!/usr/bin/env python3
"""Phase 2 binary analysis workflow."""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any, TypedDict


PLAYGROUND_PATH = Path("/workspace/playground")
ARTIFACT_PATH = PLAYGROUND_PATH / "artifacts" / "binary_analysis.json"


class BinaryAnalysisError(RuntimeError):
    pass


class BinaryAnalysisState(TypedDict):
    challengeDetails: dict[str, Any]
    manifestPath: str
    playgroundPath: str
    targetBinaryPath: str
    recon: dict[str, Any]
    idaFindingsText: str
    finalReport: dict[str, Any]


def status(message: str) -> None:
    print(message)


def requireEnv(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise BinaryAnalysisError(f"missing required environment variable: {name}")
    return value


def loadChallengeDetails(manifestPath: str) -> dict[str, Any]:
    data = json.loads(Path(manifestPath).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not str(data.get("source", "")).strip():
        raise BinaryAnalysisError("manifest must be a JSON object with non-empty 'source'")
    return data


def isExecutableElf(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK) and path.read_bytes()[:4] == b"\x7fELF"


def resolveTargetBinary(challengeDetails: dict[str, Any], playgroundPath: str, binaryName: str | None) -> str:
    root = Path(playgroundPath)
    sourcePath = root / Path(str(challengeDetails["source"])).name
    if sourcePath.is_file():
        return str(sourcePath)

    if binaryName:
        matches = [p for p in root.rglob(binaryName) if p.is_file()]
        if len(matches) != 1:
            raise BinaryAnalysisError(f"expected exactly one match for '{binaryName}', got {len(matches)}")
        return str(matches[0])

    candidates = [p for p in root.rglob("*") if isExecutableElf(p)]
    if len(candidates) != 1:
        raise BinaryAnalysisError(
            "multiple or zero executable ELF binaries found, use --binary-name. "
            f"candidates: {[str(p) for p in candidates]}"
        )
    return str(candidates[0])


def runCommand(command: str, cwd: str, allowNonZero: bool = False) -> dict[str, Any]:
    proc = subprocess.run(["bash", "-lc", command], cwd=cwd, text=True, capture_output=True)
    if proc.returncode != 0 and not allowNonZero:
        raise BinaryAnalysisError((proc.stderr or proc.stdout or f"command failed: {command}").strip())
    return {
        "command": command,
        "exitCode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def writeJson(path: str, payload: dict[str, Any]) -> None:
    outputPath = Path(path)
    outputPath.parent.mkdir(parents=True, exist_ok=True)
    outputPath.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def runReconNode(state: BinaryAnalysisState) -> dict[str, Any]:
    status("[binary-analysis] recon")
    target = shlex.quote(state["targetBinaryPath"])
    cwd = state["playgroundPath"]
    fileResult = runCommand(f"file {target}", cwd)
    headerResult = runCommand(f"readelf -h {target}", cwd)
    interpResult = runCommand(f"readelf -l {target} | grep interpreter || true", cwd, allowNonZero=True)
    return {
        "recon": {
            "commands": [fileResult, headerResult, interpResult],
            "file": fileResult["stdout"].strip(),
            "readelf_header": headerResult["stdout"].strip(),
            "interpreter": interpResult["stdout"].strip(),
        }
    }


def buildSystemPrompt(state: BinaryAnalysisState) -> str:
    recon = state["recon"]
    reconSummary = {
        "file": recon.get("file", ""),
        "readelf_header": recon.get("readelf_header", ""),
        "interpreter": recon.get("interpreter", ""),
    }
    return (
        "You are a binary exploitation analyst using IDA MCP tools.\n"
        "Find vulnerabilities for this binary exploitation CTF challenge only in the main function.\n"
        "Use tools only when needed, do not repeat the same tool calls.\n"
        "When you have enough evidence, stop calling tools and return final output.\n"
        "Return only JSON with keys: challenge, binary, recon, analysis.\n"
        "analysis must include: summary, vulnerabilities, exploitation_primitives, recommended_next_steps. Include exact details such as memory addresses,sizes,etc.\n\n"
        f"Challenge details:\n{json.dumps(state['challengeDetails'], indent=2, sort_keys=True)}\n\n"
        f"Playground path: {state['playgroundPath']}\n"
        f"Target binary path: {state['targetBinaryPath']} (Binary has been loaded in IDA)\n\n"
        f"Surface recon:\n{json.dumps(reconSummary, indent=2, sort_keys=True)}"
    )


def extractMessageText(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in content)
    return str(content)


async def runIdaAnalysisAsync(state: BinaryAnalysisState) -> str:
    try:
        from langchain.agents import create_agent
        from langchain_mcp_adapters.client import MultiServerMCPClient
        from langchain_openai import ChatOpenAI
    except ModuleNotFoundError as exc:
        raise BinaryAnalysisError("missing dependencies, rebuild container from updated Dockerfile") from exc

    client = MultiServerMCPClient({"ida": {"transport": "http", "url": requireEnv("IDA_MCP_URL")}})
    tools = await client.get_tools()
    model = ChatOpenAI(model=requireEnv("MODEL"), api_key=requireEnv("OPENAI_KEY"), temperature=0)
    agent = create_agent(model=model, tools=tools, system_prompt=buildSystemPrompt(state))
    try:
        result = agent.ainvoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                "Analyze the binary and return only valid JSON. "
                                "Do not call tools once you can fill the final schema."
                            ),
                        }
                    ]
                },
                config={"recursion_limit": 60},
            )
    except Exception as exc:
        raise BinaryAnalysisError(f"IDA analysis failed: {exc}") from exc
    messages = result.get("messages", [])
    if not messages:
        raise BinaryAnalysisError("agent returned no messages")
    return extractMessageText(getattr(messages[-1], "content", messages[-1])).strip()


def runIdaNode(state: BinaryAnalysisState) -> dict[str, Any]:
    status("[binary-analysis] ida agent")
    return {"idaFindingsText": asyncio.run(runIdaAnalysisAsync(state))}


def parseReport(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(line for line in cleaned.splitlines() if not line.startswith("```")).strip()
    report = json.loads(cleaned)
    for key in ["challenge", "binary", "recon", "analysis"]:
        if key not in report:
            raise BinaryAnalysisError(f"report missing key: {key}")
    analysis = report["analysis"]
    if not isinstance(analysis, dict):
        raise BinaryAnalysisError("report analysis must be an object")
    for key in ["summary", "vulnerabilities", "exploitation_primitives", "recommended_next_steps"]:
        if key not in analysis:
            raise BinaryAnalysisError(f"report analysis missing key: {key}")
    return report


def validateAndPersistNode(state: BinaryAnalysisState) -> dict[str, Any]:
    status("[binary-analysis] writing artifact")
    report = parseReport(state["idaFindingsText"])
    writeJson(str(ARTIFACT_PATH), report)
    return {"finalReport": report}


def buildGraph():
    from langgraph.graph import END, StateGraph

    graph = StateGraph(BinaryAnalysisState)
    graph.add_node("run_recon", runReconNode)
    graph.add_node("run_ida", runIdaNode)
    graph.add_node("validate_and_persist", validateAndPersistNode)
    graph.set_entry_point("run_recon")
    graph.add_edge("run_recon", "run_ida")
    graph.add_edge("run_ida", "validate_and_persist")
    graph.add_edge("validate_and_persist", END)
    return graph.compile()


def runBinaryAnalysisAgent(manifestPath: str, binaryName: str | None = None) -> dict[str, Any]:
    requireEnv("OPENAI_KEY")
    requireEnv("MODEL")
    requireEnv("IDA_MCP_URL")
    challengeDetails = loadChallengeDetails(manifestPath)
    targetBinaryPath = resolveTargetBinary(challengeDetails, str(PLAYGROUND_PATH), binaryName)
    status(f"[binary-analysis] target: {targetBinaryPath}")
    result = buildGraph().invoke(
        {
            "challengeDetails": challengeDetails,
            "manifestPath": manifestPath,
            "playgroundPath": str(PLAYGROUND_PATH),
            "targetBinaryPath": targetBinaryPath,
            "recon": {},
            "idaFindingsText": "",
            "finalReport": {},
        }
    )
    status(f"[binary-analysis] report: {ARTIFACT_PATH}")
    return result["finalReport"]
