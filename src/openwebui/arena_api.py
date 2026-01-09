from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime
import uuid

from src.openwebui.voting_system import default_storage, ArenaComparison

app = FastAPI(
    title="KI-Campus Arena API (Light)",
    description="Leichte API nur für Arena-Endpunkte, ohne LLM-Imports",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "online", "service": "KI-Campus Arena (Light)"}


@app.get("/health")
def health():
    return {"status": "healthy"}


class SaveComparisonRequest(BaseModel):
    question: str
    model_a: str
    answer_a: str
    model_b: str
    answer_b: str


class VoteRequest(BaseModel):
    comparison_id: str
    vote: Literal["A", "B", "tie", "both_bad"]
    comment: Optional[str] = None


@app.post("/arena/save-comparison")
def save_comparison(request: SaveComparisonRequest):
    comparison = ArenaComparison(
        id=str(uuid.uuid4()),
        question=request.question,
        timestamp=datetime.utcnow().isoformat(),
        model_a=request.model_a,
        answer_a=request.answer_a,
        model_b=request.model_b,
        answer_b=request.answer_b,
    )
    default_storage.save_comparison(comparison)
    return {"success": True, "comparison_id": comparison.id}


@app.post("/arena/vote")
def submit_vote(request: VoteRequest):
    success = default_storage.update_vote(
        comparison_id=request.comparison_id,
        vote=request.vote,
        comment=request.comment,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Comparison ID not found")
    return {"success": True}


@app.get("/arena/comparisons")
def get_all_comparisons(subset: Optional[int] = None):
    if subset is not None:
        comparisons = default_storage.get_comparisons_by_subset(subset)
    else:
        comparisons = default_storage.load_all_comparisons()
    return {"total": len(comparisons), "comparisons": [c.model_dump() for c in comparisons]}


@app.get("/arena/statistics")
def get_statistics():
    stats = default_storage.get_statistics()
    # Ensure both_bad fields are included even if not in response
    if 'votes_both_bad' not in stats:
        stats['votes_both_bad'] = 0
    if 'both_bad_rate' not in stats:
        stats['both_bad_rate'] = 0
    return stats


@app.get("/arena/comparison/{comparison_id}")
def get_comparison(comparison_id: str):
    c = default_storage.get_comparison_by_id(comparison_id)
    if not c:
        raise HTTPException(status_code=404, detail="Comparison not found")
    return c.model_dump()


@app.get("/arena/assign-subset")
def assign_subset():
    """Weist dem User ein Subset zu (Round-Robin basierend auf Vote-Counts)."""
    subset_id = default_storage.assign_subset_round_robin()
    return {"subset_id": subset_id, "message": f"Du wurdest Subset {subset_id} zugewiesen"}
