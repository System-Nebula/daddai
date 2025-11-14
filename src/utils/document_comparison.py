"""
Smart document comparison with context compression.
Handles large documents by intelligently compressing and comparing them.
"""
import json
import sys
import argparse
from typing import List, Dict, Any
from src.clients.lmstudio_client import LMStudioClient
from config import LMSTUDIO_BASE_URL


class DocumentComparator:
    """Smart document comparator with intelligent chunking."""
    
    def __init__(self):
        self.lmstudio_client = LMStudioClient(base_url=LMSTUDIO_BASE_URL)
    
    def intelligent_chunk(self, text: str, max_chunk_size: int = 8000) -> List[Dict[str, Any]]:
        """
        Intelligently chunk a document by:
        1. Build steps/phases (for build logs)
        2. Time periods (timestamps)
        3. Error sections
        4. Summary sections
        5. Natural breaks (empty lines, headers)
        
        Returns list of chunks with metadata.
        """
        chunks = []
        lines = text.split('\n')
        
        # Detect document type and chunking strategy
        is_build_log = any(keyword in text.lower()[:1000] for keyword in ['build', 'compiling', 'linking', 'error', 'warning'])
        
        if is_build_log:
            # Chunk by build phases/steps
            chunks = self._chunk_build_log(lines, max_chunk_size)
        else:
            # Chunk by natural breaks (paragraphs, sections)
            chunks = self._chunk_by_sections(lines, max_chunk_size)
        
        return chunks
    
    def _chunk_build_log(self, lines: List[str], max_chunk_size: int) -> List[Dict[str, Any]]:
        """Chunk build logs by phases, errors, and time periods."""
        chunks = []
        current_chunk = []
        current_size = 0
        current_phase = None
        
        # Detect phase markers
        phase_markers = [
            'building', 'compiling', 'linking', 'testing', 'packaging',
            'installing', 'cleaning', 'configure', 'make', 'cmake',
            'error', 'warning', 'failed', 'success', 'completed'
        ]
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            # Detect phase changes
            phase_detected = None
            for marker in phase_markers:
                if marker in line_lower and len(line) < 200:  # Phase markers are usually short
                    phase_detected = marker
                    break
            
            # If we hit a new phase and have content, save current chunk
            if phase_detected and current_phase != phase_detected and current_chunk:
                chunk_text = '\n'.join(current_chunk)
                chunks.append({
                    'text': chunk_text,
                    'phase': current_phase or 'unknown',
                    'line_start': i - len(current_chunk),
                    'line_end': i,
                    'size': len(chunk_text)
                })
                current_chunk = []
                current_size = 0
            
            current_phase = phase_detected or current_phase
            
            # Add line to current chunk
            line_size = len(line) + 1  # +1 for newline
            if current_size + line_size > max_chunk_size and current_chunk:
                # Save current chunk
                chunk_text = '\n'.join(current_chunk)
                chunks.append({
                    'text': chunk_text,
                    'phase': current_phase or 'unknown',
                    'line_start': i - len(current_chunk),
                    'line_end': i,
                    'size': len(chunk_text)
                })
                # Start new chunk with overlap (last 5 lines)
                overlap_lines = current_chunk[-5:] if len(current_chunk) >= 5 else current_chunk
                current_chunk = overlap_lines.copy()
                current_size = sum(len(l) + 1 for l in overlap_lines)
            
            current_chunk.append(line)
            current_size += line_size
        
        # Add final chunk
        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            chunks.append({
                'text': chunk_text,
                'phase': current_phase or 'unknown',
                'line_start': len(lines) - len(current_chunk),
                'line_end': len(lines),
                'size': len(chunk_text)
            })
        
        return chunks
    
    def _chunk_by_sections(self, lines: List[str], max_chunk_size: int) -> List[Dict[str, Any]]:
        """Chunk by natural breaks (empty lines, headers)."""
        chunks = []
        current_chunk = []
        current_size = 0
        
        for i, line in enumerate(lines):
            line_size = len(line) + 1
            
            # Natural break: empty line or header-like line
            is_break = (
                not line.strip() or
                (line.startswith('#') and len(line) < 100) or
                (line.isupper() and len(line) < 100 and not line.isdigit())
            )
            
            if is_break and current_chunk and current_size > max_chunk_size * 0.5:
                # Save chunk at natural break
                chunk_text = '\n'.join(current_chunk)
                chunks.append({
                    'text': chunk_text,
                    'phase': 'section',
                    'line_start': i - len(current_chunk),
                    'line_end': i,
                    'size': len(chunk_text)
                })
                current_chunk = []
                current_size = 0
            
            if current_size + line_size > max_chunk_size and current_chunk:
                # Force break
                chunk_text = '\n'.join(current_chunk)
                chunks.append({
                    'text': chunk_text,
                    'phase': 'section',
                    'line_start': i - len(current_chunk),
                    'line_end': i,
                    'size': len(chunk_text)
                })
                overlap_lines = current_chunk[-3:] if len(current_chunk) >= 3 else current_chunk
                current_chunk = overlap_lines.copy()
                current_size = sum(len(l) + 1 for l in overlap_lines)
            
            current_chunk.append(line)
            current_size += line_size
        
        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            chunks.append({
                'text': chunk_text,
                'phase': 'section',
                'line_start': len(lines) - len(current_chunk),
                'line_end': len(lines),
                'size': len(chunk_text)
            })
        
        return chunks
    
    def compress_document(self, text: str, max_chars: int = 8000) -> str:
        """
        Intelligently compress a document while preserving key information.
        Uses LLM to extract important sections, changes, errors, and key metrics.
        """
        if len(text) <= max_chars:
            return text
        
        # For build logs, extract key patterns: errors, warnings, timestamps, key metrics
        # First, try to extract structured information
        lines = text.split('\n')
        
        # Extract errors and warnings (most important for build logs)
        errors = [line for line in lines if any(keyword in line.lower() for keyword in ['error', 'failed', 'exception', 'fatal'])]
        warnings = [line for line in lines if any(keyword in line.lower() for keyword in ['warning', 'warn', 'deprecated'])]
        
        # Extract timestamps and key metrics
        timestamps = [line for line in lines if any(char.isdigit() and ':' in line for char in line[:10])]
        
        # Extract summary sections (if present)
        summary_keywords = ['summary', 'total', 'completed', 'success', 'failed', 'duration', 'time']
        summary_lines = [line for line in lines if any(keyword in line.lower() for keyword in summary_keywords)]
        
        # Build compressed version
        compressed_parts = []
        
        # Add header (first 500 chars)
        if len(text) > 500:
            compressed_parts.append(f"[Document Start]\n{text[:500]}\n...")
        
        # Add errors (critical)
        if errors:
            compressed_parts.append(f"\n[Errors Found: {len(errors)}]\n" + "\n".join(errors[:50]))  # Limit to 50 errors
        
        # Add warnings
        if warnings:
            compressed_parts.append(f"\n[Warnings Found: {len(warnings)}]\n" + "\n".join(warnings[:50]))
        
        # Add summary lines
        if summary_lines:
            compressed_parts.append(f"\n[Summary/Metrics]\n" + "\n".join(summary_lines[:30]))
        
        # Add tail (last 500 chars) - often contains final status
        if len(text) > 500:
            compressed_parts.append(f"\n...\n[Document End]\n{text[-500:]}")
        
        compressed = "\n".join(compressed_parts)
        
        # If still too long, use LLM to summarize
        if len(compressed) > max_chars:
            return self._llm_compress(compressed, max_chars)
        
        return compressed
    
    def _llm_compress(self, text: str, max_chars: int) -> str:
        """Use LLM to intelligently compress text."""
        prompt = f"""Compress the following text while preserving:
1. All errors, failures, and critical issues
2. Key metrics, timestamps, and important numbers
3. Summary information and final status
4. Important changes or differences

Original text:
{text[:max_chars * 3]}

Provide a compressed version (max {max_chars} characters) that preserves all critical information:"""
        
        try:
            messages = [
                {"role": "system", "content": "You are a document compression expert. Compress text while preserving all critical information, errors, and key metrics."},
                {"role": "user", "content": prompt}
            ]
            
            response = self.lmstudio_client.generate_response(
                messages=messages,
                temperature=0.3,  # Lower temperature for more factual compression
                max_tokens=min(2000, max_chars // 2)  # Estimate tokens
            )
            
            return response[:max_chars] if response else text[:max_chars]
        except Exception as e:
            print(f"LLM compression failed: {e}", file=sys.stderr)
            # Fallback: simple truncation with key sections
            return text[:max_chars]
    
    def find_differences(self, doc1_text: str, doc2_text: str, doc1_name: str, doc2_name: str) -> Dict[str, Any]:
        """
        Find differences between two documents using intelligent chunking and comparison.
        """
        import sys
        print(f"Comparing documents: {doc1_name} ({len(doc1_text)} chars) vs {doc2_name} ({len(doc2_text)} chars)", file=sys.stderr)
        
        # Intelligently chunk both documents
        # Each chunk should be small enough to fit multiple chunks in context window
        # Reserve ~3000 chars for prompt, so we can fit ~4-5 chunks of ~2000 chars each
        max_chunk_size = 2000
        
        print(f"Intelligently chunking documents (max {max_chunk_size} chars per chunk)...", file=sys.stderr)
        chunks1 = self.intelligent_chunk(doc1_text, max_chunk_size)
        chunks2 = self.intelligent_chunk(doc2_text, max_chunk_size)
        
        print(f"Chunked {doc1_name} into {len(chunks1)} chunks, {doc2_name} into {len(chunks2)} chunks", file=sys.stderr)
        
        # Compare chunks intelligently
        # Strategy: Compare corresponding chunks (by phase/position) and also cross-compare for changes
        all_comparisons = []
        
        # Compare corresponding chunks (same index)
        max_chunks_to_compare = min(len(chunks1), len(chunks2), 10)  # Limit to prevent timeout
        for i in range(max_chunks_to_compare):
            chunk1 = chunks1[i]
            chunk2 = chunks2[i] if i < len(chunks2) else None
            
            if chunk2:
                try:
                    comparison = self._compare_chunks(
                        chunk1['text'], 
                        chunk2['text'],
                        f"{doc1_name} (chunk {i+1}/{len(chunks1)}, {chunk1.get('phase', 'unknown')} phase)",
                        f"{doc2_name} (chunk {i+1}/{len(chunks2)}, {chunk2.get('phase', 'unknown')} phase)"
                    )
                    if comparison and len(comparison) > 50:
                        all_comparisons.append({
                            'chunk_index': i,
                            'phase': chunk1.get('phase', 'unknown'),
                            'comparison': comparison
                        })
                except Exception as e:
                    print(f"Error comparing chunk {i}: {e}", file=sys.stderr)
        
        # If documents have different numbers of chunks, compare extra chunks
        if len(chunks1) > len(chunks2):
            for i in range(len(chunks2), min(len(chunks1), len(chunks2) + 3)):
                all_comparisons.append({
                    'chunk_index': i,
                    'phase': chunks1[i].get('phase', 'unknown'),
                    'comparison': f"**New section in newer document**: {chunks1[i].get('phase', 'unknown')} phase (lines {chunks1[i].get('line_start', 0)}-{chunks1[i].get('line_end', 0)})\n\n{chunks1[i]['text'][:500]}..."
                })
        elif len(chunks2) > len(chunks1):
            for i in range(len(chunks1), min(len(chunks2), len(chunks1) + 3)):
                all_comparisons.append({
                    'chunk_index': i,
                    'phase': chunks2[i].get('phase', 'unknown'),
                    'comparison': f"**New section in newer document**: {chunks2[i].get('phase', 'unknown')} phase (lines {chunks2[i].get('line_start', 0)}-{chunks2[i].get('line_end', 0)})\n\n{chunks2[i]['text'][:500]}..."
                })
        
        # Combine all comparisons
        if all_comparisons:
            comparison_text = "## Detailed Comparison by Section\n\n"
            for comp in all_comparisons:
                comparison_text += f"### Section {comp['chunk_index'] + 1} ({comp['phase']} phase)\n\n{comp['comparison']}\n\n---\n\n"
            
            # Generate summary
            try:
                summary = self._generate_summary(all_comparisons, doc1_name, doc2_name)
                comparison_text = f"## Summary\n\n{summary}\n\n{comparison_text}"
            except Exception as e:
                print(f"Error generating summary: {e}", file=sys.stderr)
            
            return {
                "comparison": comparison_text,
                "doc1_original_length": len(doc1_text),
                "doc2_original_length": len(doc2_text),
                "doc1_chunks": len(chunks1),
                "doc2_chunks": len(chunks2),
                "comparisons_count": len(all_comparisons)
            }
        else:
            # Fallback to simple compression if chunking didn't work
            print("Chunking produced no comparisons, falling back to compression...", file=sys.stderr)
            return self._fallback_compression_comparison(doc1_text, doc2_text, doc1_name, doc2_name)
    
    def _compare_chunks(self, chunk1_text: str, chunk2_text: str, chunk1_name: str, chunk2_name: str) -> str:
        """Compare two chunks and return differences."""
        # Limit chunk size for LLM
        max_chunk_chars = 1500
        if len(chunk1_text) > max_chunk_chars:
            chunk1_text = chunk1_text[:max_chunk_chars] + "\n[Truncated...]"
        if len(chunk2_text) > max_chunk_chars:
            chunk2_text = chunk2_text[:max_chunk_chars] + "\n[Truncated...]"
        
        prompt = f"""Compare these two document sections and identify ALL differences:

Section 1 ({chunk1_name}):
{chunk1_text}

Section 2 ({chunk2_name}):
{chunk2_text}

Focus on:
1. Errors, warnings, failures
2. Metrics, numbers, counts
3. Added/removed lines
4. Modified content
5. Status changes

Provide a concise but detailed comparison:"""
        
        try:
            messages = [
                {"role": "system", "content": "You are an expert at comparing technical document sections. Identify all differences concisely."},
                {"role": "user", "content": prompt}
            ]
            
            comparison = self.lmstudio_client.generate_response(
                messages=messages,
                temperature=0.4,
                max_tokens=800  # Shorter for individual chunks
            )
            return comparison
        except Exception as e:
            return f"Error comparing chunks: {e}"
    
    def _generate_summary(self, comparisons: List[Dict[str, Any]], doc1_name: str, doc2_name: str) -> str:
        """Generate an overall summary from all chunk comparisons."""
        # Extract key points from all comparisons
        all_comparison_texts = [c['comparison'] for c in comparisons]
        combined = "\n\n".join([f"Section {i+1}: {c['comparison'][:300]}..." for i, c in enumerate(comparisons[:5])])
        
        prompt = f"""Based on these section-by-section comparisons between {doc1_name} and {doc2_name}, provide a high-level summary:

{combined}

Summarize:
1. Overall changes (what changed most significantly)
2. Error/warning changes
3. Key metrics differences
4. Major additions/removals

Keep it concise (3-4 paragraphs):"""
        
        try:
            messages = [
                {"role": "system", "content": "You are an expert at summarizing document comparisons."},
                {"role": "user", "content": prompt}
            ]
            
            summary = self.lmstudio_client.generate_response(
                messages=messages,
                temperature=0.5,
                max_tokens=600
            )
            return summary
        except Exception as e:
            return f"Summary generation error: {e}"
    
    def _fallback_compression_comparison(self, doc1_text: str, doc2_text: str, doc1_name: str, doc2_name: str) -> Dict[str, Any]:
        """Fallback to compression-based comparison if chunking fails."""
        import sys
        max_doc_chars = 6000
        
        print(f"Using fallback compression (max {max_doc_chars} chars each)...", file=sys.stderr)
        compressed_doc1 = self.compress_document(doc1_text, max_doc_chars)
        compressed_doc2 = self.compress_document(doc2_text, max_doc_chars)
        
        comparison_prompt = f"""Compare these two documents and identify ALL differences:

Document 1 (older): {doc1_name}
{compressed_doc1}

Document 2 (newer): {doc2_name}
{compressed_doc2}

Focus on errors, warnings, metrics, and key changes:"""
        
        try:
            messages = [
                {"role": "system", "content": "You are an expert at comparing technical documents and build logs."},
                {"role": "user", "content": comparison_prompt}
            ]
            
            comparison = self.lmstudio_client.generate_response(
                messages=messages,
                temperature=0.4,
                max_tokens=2000
            )
            
            return {
                "comparison": comparison,
                "doc1_compressed_length": len(compressed_doc1),
                "doc1_original_length": len(doc1_text),
                "doc2_compressed_length": len(compressed_doc2),
                "doc2_original_length": len(doc2_text),
                "compression_ratio_doc1": len(compressed_doc1) / len(doc1_text) if doc1_text else 0,
                "compression_ratio_doc2": len(compressed_doc2) / len(doc2_text) if doc2_text else 0
            }
        except Exception as e:
            return {
                "error": str(e),
                "comparison": f"Error comparing documents: {e}"
            }


def main():
    parser = argparse.ArgumentParser(description='Smart document comparison')
    parser.add_argument('--action', type=str, required=True, choices=['compare'])
    parser.add_argument('--doc1-name', type=str, default='Document 1', help='First document name')
    parser.add_argument('--doc2-name', type=str, default='Document 2', help='Second document name')
    parser.add_argument('--stdin', action='store_true', help='Read documents from stdin as JSON')
    
    args = parser.parse_args()
    
    try:
        comparator = DocumentComparator()
        
        if args.action == 'compare':
            # Read documents from stdin as JSON to avoid command-line length limits
            if args.stdin:
                stdin_data = sys.stdin.read()
                try:
                    input_data = json.loads(stdin_data)
                    doc1_text = input_data.get('doc1_text', '')
                    doc2_text = input_data.get('doc2_text', '')
                    doc1_name = input_data.get('doc1_name', args.doc1_name)
                    doc2_name = input_data.get('doc2_name', args.doc2_name)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON input: {e}")
            else:
                # Fallback: try command-line args (for small documents)
                parser.add_argument('--doc1-text', type=str, help='First document text')
                parser.add_argument('--doc2-text', type=str, help='Second document text')
                args = parser.parse_args()
                doc1_text = args.doc1_text or ''
                doc2_text = args.doc2_text or ''
                doc1_name = args.doc1_name
                doc2_name = args.doc2_name
            
            if not doc1_text or not doc2_text:
                raise ValueError("doc1_text and doc2_text required for compare action")
            
            result = comparator.find_differences(
                doc1_text,
                doc2_text,
                doc1_name,
                doc2_name
            )
            
            response = {
                "success": True,
                "result": result
            }
            print(json.dumps(response), file=sys.stdout)
            sys.stdout.flush()
        
    except Exception as e:
        error_response = {
            "success": False,
            "error": str(e)
        }
        print(json.dumps(error_response), file=sys.stdout)
        sys.stdout.flush()
        sys.exit(1)


if __name__ == "__main__":
    main()

