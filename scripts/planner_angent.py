#!/usr/bin/env python3
"""Basic LangGraph planner agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict


class PlannerState(TypedDict):
    challenge_details: dict[str, Any]
    output: str


def loadChallengeDetails(manifestPath: str) -> dict[str, Any]:
    path = Path(manifestPath).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"manifest not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest must be a JSON object")
    return data


def plannerNode(state: PlannerState) -> PlannerState:
    details = state["challenge_details"]
    output = "\n".join(
        [
            "Planner instruction:",
            "Output the challenge details exactly as provided.",
            "",
            "Challenge details:",
            json.dumps(details, indent=2, sort_keys=True),
        ]
    )
    return {"challenge_details": details, "output": output}


def getLangGraph():
    from langgraph.graph import END, StateGraph

    return END, StateGraph


def buildGraph():
    END, StateGraph = getLangGraph()
    graph = StateGraph(PlannerState)
    graph.add_node("planner", plannerNode)
    graph.set_entry_point("planner")
    graph.add_edge("planner", END)
    return graph.compile()


def runPlannerAgent(manifestPath: str) -> str:
    details = loadChallengeDetails(manifestPath)
    app = buildGraph()
    result = app.invoke({"challenge_details": details, "output": ""})
    output = result["output"]
    print(output)
    return output
