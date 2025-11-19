"""
Parent-child chunking strategy for improved RAG retrieval.
Stores small chunks for precise retrieval, links to parent chunks for context.
"""
from typing import List, Dict, Any, Optional
from logger_config import logger


class ParentChildChunker:
    """
    Parent-child chunking strategy.
    Creates small child chunks (200-300 chars) for retrieval,
    and larger parent chunks (1000+ chars) for context.
    """
    
    def __init__(self,
                 child_chunk_size: int = 300,
                 parent_chunk_size: int = 1000,
                 child_overlap: int = 50,
                 parent_overlap: int = 200):
        """
        Initialize parent-child chunker.
        
        Args:
            child_chunk_size: Size of child chunks (for retrieval)
            parent_chunk_size: Size of parent chunks (for context)
            child_overlap: Overlap between child chunks
            parent_overlap: Overlap between parent chunks
        """
        self.child_chunk_size = child_chunk_size
        self.parent_chunk_size = parent_chunk_size
        self.child_overlap = child_overlap
        self.parent_overlap = parent_overlap
    
    def chunk_text(self, text: str) -> Dict[str, Any]:
        """
        Create parent-child chunk structure.
        
        Args:
            text: Text to chunk
            
        Returns:
            Dictionary with 'children' (small chunks) and 'parents' (large chunks)
            Each chunk has parent_id/child_ids for linking
        """
        if not text or not text.strip():
            return {"children": [], "parents": []}
        
        # First, create parent chunks (large, for context)
        parents = self._create_parent_chunks(text)
        
        # Then, create child chunks (small, for retrieval)
        children = self._create_child_chunks(text, parents)
        
        # Link children to parents
        self._link_children_to_parents(children, parents)
        
        return {
            "children": children,
            "parents": parents,
            "structure": "parent_child"
        }
    
    def _create_parent_chunks(self, text: str) -> List[Dict[str, Any]]:
        """Create large parent chunks for context."""
        import re
        
        # Split by paragraphs first
        paragraphs = re.split(r'\n\s*\n', text)
        parents = []
        current_chunk = []
        current_length = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            para_length = len(para)
            
            # If adding this paragraph exceeds parent size, finalize current parent
            if current_length + para_length > self.parent_chunk_size and current_chunk:
                parent_text = "\n\n".join(current_chunk)
                parents.append({
                    "text": parent_text,
                    "chunk_index": len(parents),
                    "chunk_type": "parent",
                    "parent_id": f"parent_{len(parents)}",
                    "child_ids": [],
                    "length": len(parent_text)
                })
                
                # Start new parent with overlap (last paragraph)
                current_chunk = [current_chunk[-1]] if current_chunk else []
                current_length = len(current_chunk[-1]) if current_chunk else 0
            
            current_chunk.append(para)
            current_length += para_length + 2  # +2 for "\n\n"
        
        # Add final parent
        if current_chunk:
            parent_text = "\n\n".join(current_chunk)
            parents.append({
                "text": parent_text,
                "chunk_index": len(parents),
                "chunk_type": "parent",
                "parent_id": f"parent_{len(parents)}",
                "child_ids": [],
                "length": len(parent_text)
            })
        
        return parents
    
    def _create_child_chunks(self, text: str, parents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create small child chunks for precise retrieval."""
        import re
        
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        children = []
        current_chunk = []
        current_length = 0
        overlap_sentences = []
        overlap_sentence_count = max(1, int(self.child_overlap / 50))  # ~1-2 sentences
        
        for i, sentence in enumerate(sentences):
            sentence_length = len(sentence)
            
            if current_length + sentence_length > self.child_chunk_size and current_chunk:
                child_text = " ".join(current_chunk)
                children.append({
                    "text": child_text,
                    "chunk_index": len(children),
                    "chunk_type": "child",
                    "child_id": f"child_{len(children)}",
                    "parent_id": None,  # Will be linked later
                    "length": len(child_text)
                })
                
                # Start new child with overlap
                overlap_sentences = current_chunk[-overlap_sentence_count:] if len(current_chunk) >= overlap_sentence_count else current_chunk
                current_chunk = overlap_sentences.copy()
                current_length = sum(len(s) for s in current_chunk) + len(current_chunk) - 1  # + spaces
            
            current_chunk.append(sentence)
            current_length += sentence_length + 1  # +1 for space
        
        # Add final child
        if current_chunk:
            child_text = " ".join(current_chunk)
            children.append({
                "text": child_text,
                "chunk_index": len(children),
                "chunk_type": "child",
                "child_id": f"child_{len(children)}",
                "parent_id": None,
                "length": len(child_text)
            })
        
        return children
    
    def _link_children_to_parents(self, children: List[Dict[str, Any]], parents: List[Dict[str, Any]]):
        """Link child chunks to their parent chunks based on text overlap."""
        for child in children:
            child_text = child["text"]
            best_parent = None
            best_overlap = 0
            
            # Find parent with most text overlap
            for parent in parents:
                parent_text = parent["text"]
                
                # Calculate overlap (simple word-based)
                child_words = set(child_text.lower().split())
                parent_words = set(parent_text.lower().split())
                
                if child_words and parent_words:
                    overlap = len(child_words & parent_words) / len(child_words)
                    
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_parent = parent
            
            # Link child to best parent
            if best_parent and best_overlap > 0.3:  # At least 30% overlap
                child["parent_id"] = best_parent["parent_id"]
                if child["child_id"] not in best_parent["child_ids"]:
                    best_parent["child_ids"].append(child["child_id"])
            else:
                # If no good parent found, link to nearest parent by position
                # Simple heuristic: use parent at similar position
                child_idx = child["chunk_index"]
                parent_idx = min(child_idx * len(parents) // max(len(children), 1), len(parents) - 1)
                if parent_idx < len(parents):
                    child["parent_id"] = parents[parent_idx]["parent_id"]
                    if child["child_id"] not in parents[parent_idx]["child_ids"]:
                        parents[parent_idx]["child_ids"].append(child["child_id"])
    
    def get_flat_chunks_for_storage(self, chunk_structure: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Convert parent-child structure to flat list for storage.
        Stores both children and parents, with linking metadata.
        
        Args:
            chunk_structure: Result from chunk_text()
            
        Returns:
            Flat list of chunks ready for storage
        """
        flat_chunks = []
        
        # Add children first (for retrieval)
        for child in chunk_structure.get("children", []):
            flat_chunks.append({
                "text": child["text"],
                "chunk_index": child["chunk_index"],
                "chunk_type": "child",
                "chunk_id": child["child_id"],
                "parent_id": child.get("parent_id"),
                "is_retrieval_chunk": True,  # Flag for retrieval
                "is_context_chunk": False
            })
        
        # Add parents (for context)
        for parent in chunk_structure.get("parents", []):
            flat_chunks.append({
                "text": parent["text"],
                "chunk_index": parent["chunk_index"],
                "chunk_type": "parent",
                "chunk_id": parent["parent_id"],
                "child_ids": parent.get("child_ids", []),
                "is_retrieval_chunk": False,
                "is_context_chunk": True  # Flag for context
            })
        
        return flat_chunks

