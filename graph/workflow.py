"""
LangGraph StateGraph Workflow
Orchestrates: START → researcher → writer → fact_checker → editor → END
With conditional looping if > 2 disputed claims found.
"""
from typing import TypedDict, Optional, Any, Callable
from langgraph.graph import StateGraph, END, START

from agents.researcher import researcher_agent
from agents.writer import writer_agent
from agents.fact_checker import fact_checker_agent
from agents.editor import editor_agent


# ─── State Definition ───────────────────────────────────────────────────────

class ResearchState(TypedDict):
    """Complete state object carried through the workflow."""
    topic: str
    depth: str                          # "quick" | "deep"
    sources: list                       # List of source dicts
    research_summary: str               # Brief research overview
    key_themes: list                    # Key themes identified
    draft_report: str                   # Markdown report draft
    fact_check_results: list            # List of verification results
    disputed_count: int                 # Number of disputed claims
    final_report: str                   # Final polished report
    iteration_count: int                # Loop iteration counter
    max_iterations: int                 # Max allowed iterations
    _progress_callback: Optional[Any]  # Callback for streaming progress


# ─── Node Functions ──────────────────────────────────────────────────────────

def run_researcher(state: ResearchState) -> ResearchState:
    """Wrapper node for researcher agent."""
    depth = state.get("depth", "quick")
    return researcher_agent(state, depth=depth)


def run_writer(state: ResearchState) -> ResearchState:
    """Wrapper node for writer agent."""
    return writer_agent(state)


def run_fact_checker(state: ResearchState) -> ResearchState:
    """Wrapper node for fact checker agent."""
    return fact_checker_agent(state)


def run_editor(state: ResearchState) -> ResearchState:
    """Wrapper node for editor agent."""
    return editor_agent(state)


# ─── Conditional Edge ────────────────────────────────────────────────────────

def should_loop_back(state: ResearchState) -> str:
    """
    After fact checking: if > 2 disputed claims AND within iteration limit,
    loop back to researcher for more sources. Otherwise proceed to editor.
    """
    disputed = state.get("disputed_count", 0)
    iteration = state.get("iteration_count", 1)
    max_iter = state.get("max_iterations", 2)
    
    progress_callback = state.get("_progress_callback")
    
    if disputed > 2 and iteration < max_iter:
        if progress_callback:
            progress_callback(
                "workflow",
                f"🔄 {disputed} disputed claims found. Looping back to researcher (iteration {iteration + 1}/{max_iter})..."
            )
        return "researcher"
    else:
        if disputed > 0 and progress_callback:
            progress_callback(
                "workflow",
                f"📋 Sending to editor with {disputed} disputed claim(s) to fix..."
            )
        return "editor"


# ─── Build Graph ─────────────────────────────────────────────────────────────

def build_research_graph() -> StateGraph:
    """
    Build and compile the LangGraph StateGraph.
    
    Flow:
        START
          ↓
        researcher
          ↓
        writer
          ↓
        fact_checker
          ↓ (conditional)
        ┌─────────────┐
        │ > 2 disputed│──→ researcher (loop, max 2x)
        │ ≤ 2 disputed│──→ editor
        └─────────────┘
          ↓
        editor
          ↓
        END
    """
    workflow = StateGraph(ResearchState)
    
    # Add nodes
    workflow.add_node("researcher", run_researcher)
    workflow.add_node("writer", run_writer)
    workflow.add_node("fact_checker", run_fact_checker)
    workflow.add_node("editor", run_editor)
    
    # Add edges
    workflow.add_edge(START, "researcher")
    workflow.add_edge("researcher", "writer")
    workflow.add_edge("writer", "fact_checker")
    
    # Conditional edge: loop or proceed
    workflow.add_conditional_edges(
        "fact_checker",
        should_loop_back,
        {
            "researcher": "researcher",
            "editor": "editor",
        }
    )
    
    workflow.add_edge("editor", END)
    
    return workflow.compile()


# ─── Run Helper ──────────────────────────────────────────────────────────────

def run_research(
    topic: str,
    depth: str = "quick",
    progress_callback: Optional[Callable] = None,
) -> dict:
    """
    Execute the full research workflow.
    
    Args:
        topic: Research topic
        depth: "quick" or "deep"
        progress_callback: Optional fn(agent_name, message) for streaming updates
    
    Returns:
        Final state dict with all outputs
    """
    graph = build_research_graph()
    
    initial_state: ResearchState = {
        "topic": topic,
        "depth": depth,
        "sources": [],
        "research_summary": "",
        "key_themes": [],
        "draft_report": "",
        "fact_check_results": [],
        "disputed_count": 0,
        "final_report": "",
        "iteration_count": 0,
        "max_iterations": 2 if depth == "deep" else 2,
        "_progress_callback": progress_callback,
    }
    
    if progress_callback:
        progress_callback("workflow", f"🚀 Starting research pipeline for: {topic}")
    
    final_state = graph.invoke(initial_state)
    
    if progress_callback:
        progress_callback("workflow", "🎉 Research pipeline complete!")
    
    return final_state
