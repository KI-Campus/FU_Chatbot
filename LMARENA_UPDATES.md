# LMarena Button Format Update

## Changes Summary
The voting UI has been updated to match the LMarena interface format with 4-way voting buttons instead of the original 3-way format.

### Button Labels Updated
| Before | After |
|--------|-------|
| "Wähle A" | **"A ist besser"** |
| "Gleichwertig" | **"Unentschieden"** |
| "Wähle B" | **"B ist besser"** |
| *(N/A)* | **"Beide schlecht"** *(NEW)* |

### New Vote Type
- Added `both_bad` as a 4th voting option (alongside A, B, tie)
- Vote type is now: `Literal["A", "B", "tie", "both_bad"]`

## Files Modified

### 1. `src/openwebui/voting_system.py`
- Updated `ArenaComparison.vote` field to support `both_bad`
- Updated `update_vote()` method signature to accept `both_bad`
- Updated `get_statistics()` to calculate:
  - `votes_both_bad`: count of both_bad votes
  - `both_bad_rate`: percentage of both_bad votes

### 2. `src/openwebui/arena_api.py`
- Updated `VoteRequest` model to accept `both_bad` vote type
- Enhanced `/arena/statistics` endpoint to ensure `both_bad` fields are always included

### 3. `src/openwebui/voting_ui_simple.py`
- **Voting UI (`/`):**
  - Updated all 4 button labels to German LMarena format
  - Added 4th button "Beide schlecht" with `onclick="selectVote('both_bad')"`
  - Updated `selectVote()` loop to handle all 4 vote types

- **Results Dashboard (`/results`):**
  - Added `.vote-both_bad` CSS styling (red background: `#ffe8e8`)
  - Updated `pill()` function to display and style `both_bad` votes with "Beide schlecht" label

## Verification Results

✅ **API Endpoints**
- Health check: Healthy
- 55 total comparisons in database
- 3 votes with `both_bad` (5.5% rate)

✅ **Voting UI**
- All 4 buttons display correctly: "A ist besser", "Unentschieden", "B ist besser", "Beide schlecht"
- Vote handler supports `both_bad`
- Vote submission and persistence working

✅ **Results Dashboard**
- CSS styling for `both_bad` votes defined
- Pill function correctly displays and styles all 4 vote types
- Vote statistics include both_bad counts and rates

✅ **Functional Tests**
- Created test comparison successfully
- Voted with `both_bad` option
- Vote persisted correctly to JSONL storage

## Running the System

### Start API Server (Port 8001)
```bash
cd /Users/browse/FU_Chatbot_RD_Zitho
.venv/bin/python -m uvicorn src.openwebui.arena_api:app --host 127.0.0.1 --port 8001
```

### Start UI Server (Port 8002)
```bash
cd /Users/browse/FU_Chatbot_RD_Zitho
.venv/bin/python -m uvicorn src.openwebui.voting_ui_simple:app --host 127.0.0.1 --port 8002
```

### Access the System
- **Voting Interface:** http://127.0.0.1:8002/
- **Results Dashboard:** http://127.0.0.1:8002/results
- **API Documentation:** http://127.0.0.1:8001/docs

## API Statistics Response Example
```json
{
  "total_comparisons": 55,
  "voted": 55,
  "unvoted": 0,
  "votes_for_a": 19,
  "votes_for_b": 17,
  "votes_tie": 16,
  "votes_both_bad": 3,
  "win_rate_a": 0.365,
  "win_rate_b": 0.327,
  "tie_rate": 0.308,
  "both_bad_rate": 0.055,
  "models_seen": ["kicampus-original", "kicampus-improved"]
}
```

## Data Persistence
- All votes are stored in append-only JSONL format
- Location: `src/openwebui/data/arena_votes.jsonl`
- Each line contains a complete `ArenaComparison` object with all vote information
