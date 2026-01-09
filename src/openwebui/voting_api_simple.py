"""Simplified FastAPI for Voting Arena - ohne LLM Dependencies"""
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="KI Campus Voting Arena API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database file
DB_FILE = Path(__file__).parent / "arena_comparisons.json"


class Comparison(BaseModel):
    id: str
    question: str
    timestamp: str
    model_a: str
    answer_a: str
    model_b: str
    answer_b: str
    vote: Optional[str] = None
    vote_timestamp: Optional[str] = None
    comment: Optional[str] = None


class ComparisonUpdate(BaseModel):
    question: str
    answer_a: str
    answer_b: str


class VoteRequest(BaseModel):
    comparison_id: str
    vote: str  # "A" | "B" | "tie" | "both_bad"
    comment: Optional[str] = None


def load_db():
    if not DB_FILE.exists():
        return {"comparisons": []}
    with open(DB_FILE) as f:
        return json.load(f)


def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/arena/comparisons")
def get_comparisons():
    data = load_db()
    return {"total": len(data["comparisons"]), "comparisons": data["comparisons"]}


@app.post("/arena/save-comparison")
def save_comparison(comparison: Comparison):
    data = load_db()
    
    # Check if comparison with this ID exists
    existing_idx = None
    for idx, comp in enumerate(data["comparisons"]):
        if comp["id"] == comparison.id:
            existing_idx = idx
            break
    
    comp_dict = comparison.dict()
    
    if existing_idx is not None:
        # Update existing
        data["comparisons"][existing_idx] = comp_dict
    else:
        # Add new
        data["comparisons"].append(comp_dict)
    
    save_db(data)
    return {"status": "success", "id": comparison.id}


@app.patch("/arena/comparisons/{comparison_id}")
def update_comparison(comparison_id: str, update: ComparisonUpdate):
    data = load_db()
    
    for comp in data["comparisons"]:
        if comp["id"] == comparison_id:
            comp["question"] = update.question
            comp["answer_a"] = update.answer_a
            comp["answer_b"] = update.answer_b
            save_db(data)
            return {"status": "updated", "id": comparison_id}
    
    raise HTTPException(status_code=404, detail="Comparison not found")


@app.post("/arena/vote")
def vote(req: VoteRequest):
    """Record a vote for a comparison.
    Updates `vote`, optional `comment`, and sets `vote_timestamp` (ISO 8601).
    """
    data = load_db()
    for comp in data["comparisons"]:
        if comp.get("id") == req.comparison_id:
            comp["vote"] = req.vote
            if req.comment is not None:
                comp["comment"] = req.comment
            comp["vote_timestamp"] = datetime.utcnow().isoformat(timespec="seconds")
            save_db(data)
            return {"status": "ok", "id": req.comparison_id}
    raise HTTPException(status_code=404, detail="Comparison not found")


@app.patch("/arena/comparisons")
def batch_update_comparisons(updates: List[dict]):
    data = load_db()
    updated_count = 0
    
    for update_item in updates:
        comp_id = update_item.get("id")
        if not comp_id:
            continue
            
        for comp in data["comparisons"]:
            if comp["id"] == comp_id:
                if "question" in update_item:
                    comp["question"] = update_item["question"]
                if "answer_a" in update_item:
                    comp["answer_a"] = update_item["answer_a"]
                if "answer_b" in update_item:
                    comp["answer_b"] = update_item["answer_b"]
                updated_count += 1
                break
    
    save_db(data)
    return {"status": "success", "updated": updated_count}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
