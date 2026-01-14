"""
Socratic stuckness and goal achievement assessment.

Analyzes student's response to determine:
1. Stuckness level (0.0-1.0): How stuck is the student?
2. Goal achievement (bool): Has the student reached the learning objective?
"""

from langfuse.decorators import observe

from src.llm.objects.LLMs import LLM, Models
from src.llm.prompts.prompt_loader import load_prompt

# Load prompt once at module level
STUCKNESS_GOAL_PROMPT = load_prompt("socratic_stuckness_goal_achievement")


@observe()
def assess_stuckness_and_goal(
    user_query: str,
    chat_history: list,
    learning_objective: str,
    attempt_count: int,
    current_stuckness: float,
    model: Models
) -> tuple[float, bool, str]:
    """
    Assesses student's stuckness level, goal achievement, and mastery using LLM.
    
    Uses socratic_stuckness_goal_achievement.txt prompt to analyze:
    - Quality of student's response
    - Progress toward learning objective
    - Signs of confusion, frustration, or misconceptions
    - Evidence of understanding
    - Current mastery level
    
    Expected LLM output format:
    ```
    STUCKNESS: 0.5
    GOAL_ACHIEVED: false
    MASTERY: medium
    ```
    
    Args:
        user_query: Student's current response
        chat_history: Full conversation history
        learning_objective: What the student should understand
        attempt_count: Number of turns so far
        current_stuckness: Previous stuckness score
        model: LLM model to use
        
    Returns:
        Tuple of (stuckness_score, goal_achieved, mastery_level)
        - stuckness_score: float 0.0-1.0 (0=progressing, 1=completely stuck)
        - goal_achieved: bool (True if student demonstrates understanding)
        - mastery_level: str 'low'|'medium'|'high' (current understanding level)
    """
    # Initialize LLM instance
    _llm = LLM()
    
    # Prepare context for LLM
    context = f"""Learning Objective: {learning_objective}

Attempt Count: {attempt_count}
Current Stuckness: {current_stuckness}

Student's Current Response: {user_query}"""
    
    # Call LLM to assess stuckness and goal
    response = _llm.chat(
        query=context,
        chat_history=chat_history,
        model=model,
        system_prompt=STUCKNESS_GOAL_PROMPT
    )
    
    if response.content is None:
        raise ValueError(
            f"Stuckness/goal assessment response is None. Response: {response}"
        )
    
    # Parse response
    # Expected format:
    # STUCKNESS: 0.5
    # GOAL_ACHIEVED: false
    # MASTERY: medium
    
    stuckness_score = current_stuckness  # Default: keep current
    goal_achieved = False  # Default: not achieved
    mastery_level = "medium"  # Default: medium
    
    lines = response.content.strip().split('\n')
    for line in lines:
        line_clean = line.strip().lower()
        
        if line_clean.startswith('stuckness:'):
            try:
                value = line_clean.split(':', 1)[1].strip()
                stuckness_score = float(value)
                # Clamp to [0.0, 1.0]
                stuckness_score = max(0.0, min(1.0, stuckness_score))
            except (ValueError, IndexError):
                pass  # Keep default
        
        elif line_clean.startswith('goal_achieved:'):
            try:
                value = line_clean.split(':', 1)[1].strip()
                goal_achieved = value == 'true'
            except IndexError:
                pass  # Keep default
        
        elif line_clean.startswith('mastery:'):
            try:
                value = line_clean.split(':', 1)[1].strip()
                # Validate mastery level
                if value in ['low', 'medium', 'high']:
                    mastery_level = value
            except IndexError:
                pass  # Keep default
    
    return stuckness_score, goal_achieved, mastery_level
