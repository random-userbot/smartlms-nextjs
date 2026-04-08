from app.models.models import ICAPLevel
from typing import Optional

def map_action_to_icap(action: str) -> Optional[ICAPLevel]:
    """
    Map raw activity actions to the ICAP (Interactive, Constructive, Active, Passive) framework.
    
    ICAP Framework Definitions:
    - Interactive: Dialog/Peer interaction or AI Tutor queries.
    - Constructive: Generating new content (notes, summaries).
    - Active: Selecting, manipulating, or navigating (quiz answers, seeking).
    - Passive: Just viewing or listening.
    """
    action = action.lower()
    
    # INTERACTIVE: Dynamic dialogue or peer engagement
    if any(k in action for k in ["chat", "query", "ask", "doubt", "answer_ai", "tutor_interaction"]):
        return ICAPLevel.INTERACTIVE
        
    # CONSTRUCTIVE: Knowledge generation
    if any(k in action for k in ["note", "summary", "feedback_submit", "reflect", "code_snippet"]):
        return ICAPLevel.CONSTRUCTIVE
        
    # ACTIVE: Direct physical engagement with materials
    if any(k in action for k in ["quiz_start", "quiz_submit", "quiz_answer", "seek", "link_click", "material_download", "search"]):
        return ICAPLevel.ACTIVE
        
    # PASSIVE: Consuming content
    if any(k in action for k in ["lecture_start", "video_play", "video_resume", "page_view", "view_material"]):
        return ICAPLevel.PASSIVE
        
    return None

def get_action_evidence(action: str, details: dict) -> str:
    """Generate a human-readable evidence string for explainability."""
    if "chat" in action:
        return f"Student engaged in dialogue with AI Tutor: '{details.get('content', 'Query submitted')}'"
    if "note" in action:
        return "Student actively synthesized knowledge via note-taking."
    if "quiz_submit" in action:
        return f"Student completed assessment with a focus on active recall."
    if "tab_switch" in action:
        return "Attention lapse detected (Tab Switch)."
    if "idle" in action:
        return "Cognitive idle phase detected (Inactivity)."
    return f"Activity '{action}' recorded."
