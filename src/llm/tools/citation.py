"""
Node wrapper for parsing citations and converting [docN] markers to clickable links.
"""

from langfuse.decorators import observe

from llm.objects.citation_parser import CitationParser
from llm.state.models import GraphState


@observe()
def parse_citations(state: GraphState) -> GraphState:
    """
    Parses [docN] citations in answer and converts them to markdown links.
    
    Changes:
    - Sets state.citations_markdown (answer with clickable citation links)
    
    Args:
        state: Current graph state with answer and reranked chunks
        
    Returns:
        Updated state with parsed citations
    """
    parser = CitationParser()
    
    # Parse citations in answer (reranked already contains TextNodes)
    parsed_answer = parser.parse(
        answer=state.answer,
        source_documents=state.reranked
    )
    
    state.citations_markdown = parsed_answer
    
    return state