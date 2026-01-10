import re

from langfuse.decorators import observe
from llama_index.core.schema import TextNode

CITATION_TEXT = '<a href="{url}"><sup>[{index}]</sup></a>'


class CitationParser:
    """This class is responsible for parsing the document references from the return string."""

    def __init__(self) -> None:
        self.name = "OutputParser"

    def _clean_up_answer(self, answer: str) -> str:
        """Remove double spaces and remove doc references in false format.
        Keep only references with allowed format [docN] where N=integer. E.g. [doc5] instead of [doc10.2] or doc[2.3.1]
        """
        answer = answer.replace("  ", " ")
        # Anything where N is a float
        answer = re.sub(r"\[doc\d+(?:\.\d+)+\]", "", answer)
        # Anything where N is not purely digits (e.g., [docabc], [doc1a2])
        answer = re.sub(r"\[doc\D+\]", "", answer)
        answer = re.sub(r"\[doc\d+\D+.*?\]", "", answer)
        return answer

    def _get_source_docs_from_answer(self, answer: str) -> list[int]:
        """Extract all [docN] from answer and extract N, and just return the N's as a list of ints"""
        results = re.findall(r"\[doc(\d+)\]", answer)
        doc_ids = [int(i) for i in results]
        # remove duplicates while preserving order
        doc_ids = list(dict.fromkeys(doc_ids))
        return doc_ids

    def _remove_doc_ids_from_answer(self, answer: str, doc_ids: list[int]) -> str:
        """Remove all [docN] from answer where N is in doc_ids list. Used for hallucinated references."""
        for idx in doc_ids:
            answer = answer.replace(f"[doc{idx}]", "")
        return answer

    @observe()
    def parse(
        self,
        answer: str,
        source_documents: list[TextNode],
    ) -> str:
        answer = self._clean_up_answer(answer)
        doc_ids = self._get_source_docs_from_answer(answer)

        # Validate which doc IDs exist and remove hallucinated ones
        real_doc_ids: list[int] = []
        fake_doc_ids: list[int] = []
        
        for i in doc_ids:
            idx = i - 1
            try:
                doc = source_documents[idx]
                real_doc_ids.append(i)
            except IndexError:
                print(f"Could not find doc{i} in source documents")
                fake_doc_ids.append(i)
        
        # Remove hallucinated references
        answer = self._remove_doc_ids_from_answer(answer, fake_doc_ids)
        
        # Make references sequential (e.g., [doc3][doc7] -> [doc1][doc2])
        # This must happen BEFORE converting to HTML
        sorted_real_ids = sorted(real_doc_ids)
        for current, target in zip(sorted_real_ids, range(1, len(real_doc_ids) + 1)):
            if current != target:
                answer = answer.replace(f"[doc{current}]", f"[doc{target}]")
        
        # Now convert to HTML links, tracking seen URLs to avoid duplicates
        seen_urls = set()
        for i in range(1, len(real_doc_ids) + 1):
            # Map back to original document
            original_idx = sorted_real_ids[i - 1] - 1
            doc = source_documents[original_idx]
            
            if doc.metadata.get("url") not in seen_urls:
                replacement_text = CITATION_TEXT.format(url=doc.metadata.get("url"), index=i)
                seen_urls.add(doc.metadata.get("url"))
                answer = re.sub(rf"[, ]*\[doc{i}\]", rf"{replacement_text}", answer)
            else:
                # Remove duplicate URL references
                answer = re.sub(rf"[, ]*\[doc{i}\]", "", answer)

        return answer