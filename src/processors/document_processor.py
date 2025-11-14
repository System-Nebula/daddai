"""
Document processing module using Docling.
Processes various document formats and extracts structured content.
"""
import os
from typing import List, Dict, Any, Union
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import PdfFormatOption
from logger_config import logger


class DocumentProcessor:
    """Process documents using Docling and chunk them for RAG."""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        Initialize the document processor.
        
        Args:
            chunk_size: Size of text chunks for processing
            chunk_overlap: Overlap between chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Initialize Docling converter
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
    
    def process_document(self, file_path: str) -> Dict[str, Any]:
        """
        Process a document and extract structured content.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Dictionary containing document content and metadata
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Document not found: {file_path}")
        
        # Extract metadata
        file_ext = os.path.splitext(file_path)[1].lower()
        metadata = {
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "file_type": file_ext,
        }
        
        # Handle plain text files directly (Docling doesn't support these)
        text_extensions = [
            # Plain text and logs
            '.txt', '.log',
            # Markdown variants
            '.md', '.markdown', '.livemd', '.mixr', '.rst', '.org', '.wiki',
            # Data/config formats
            '.yaml', '.yml', '.toml', '.xml',
            # Code files
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h', '.hpp',
            '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala', '.r',
            '.sh', '.bash', '.zsh', '.ps1', '.bat', '.cmd', '.sql', '.pl', '.lua',
            # Config files
            '.ini', '.cfg', '.conf', '.config', '.env', '.properties', '.gitignore',
            '.dockerfile', '.makefile', '.cmake', '.gradle', '.maven', '.sbt'
        ]
        
        if file_ext in text_extensions:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                document_text = f.read()
            
            # Chunk the document
            chunks = self._chunk_text(document_text)
            
            return {
                "text": document_text,
                "chunks": chunks,
                "metadata": metadata,
                "full_document": None  # No Docling document for plain text
            }
        
        # Handle Jupyter notebook files (.ipynb) - extract cells and format
        if file_ext == '.ipynb':
            import json
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    notebook_data = json.load(f)
                
                # Format notebook as readable text
                document_text = self._format_notebook_for_rag(notebook_data)
                
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in notebook {file_path}: {e}")
                raise
            except Exception as e:
                logger.error(f"Error processing notebook file {file_path}: {e}")
                raise
            
            # Chunk the document
            chunks = self._chunk_text(document_text)
            
            return {
                "text": document_text,
                "chunks": chunks,
                "metadata": metadata,
                "full_document": None  # No Docling document for notebooks
            }
        
        # Handle JSON files - format as readable text
        if file_ext == '.json':
            import json
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    json_data = json.load(f)
                
                # Format JSON as readable text
                document_text = self._format_json_for_rag(json_data)
                
            except json.JSONDecodeError as e:
                # If JSON is invalid, try to read as text
                logger.warning(f"Invalid JSON in {file_path}, reading as text: {e}")
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    document_text = f.read()
            except Exception as e:
                logger.error(f"Error processing JSON file {file_path}: {e}")
                raise
            
            # Chunk the document
            chunks = self._chunk_text(document_text)
            
            return {
                "text": document_text,
                "chunks": chunks,
                "metadata": metadata,
                "full_document": None  # No Docling document for JSON
            }
        
        # Handle CSV files - convert to markdown table format for better readability
        if file_ext == '.csv':
            import csv
            document_lines = []
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore', newline='') as f:
                # Try to detect delimiter
                sample = f.read(1024)
                f.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                reader = csv.reader(f, delimiter=delimiter)
                rows = list(reader)
                
                if not rows:
                    document_text = "CSV file is empty."
                else:
                    # Convert to markdown table format
                    # Header row
                    header = rows[0]
                    document_lines.append("| " + " | ".join(header) + " |")
                    document_lines.append("| " + " | ".join(["---"] * len(header)) + " |")
                    
                    # Data rows
                    for row in rows[1:]:
                        # Pad row if it's shorter than header
                        while len(row) < len(header):
                            row.append("")
                        # Truncate if longer
                        row = row[:len(header)]
                        document_lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
                    
                    document_text = "\n".join(document_lines)
            
            # Chunk the document
            chunks = self._chunk_text(document_text)
            
            return {
                "text": document_text,
                "chunks": chunks,
                "metadata": metadata,
                "full_document": None  # No Docling document for CSV
            }
        
        # For other formats, try Docling first, then fallback to text reading
        # Docling-supported formats: PDF, DOCX, DOC, PPTX, PPT, HTML, AsciiDoc
        docling_formats = ['.pdf', '.docx', '.doc', '.pptx', '.ppt', '.html', '.htm', '.adoc', '.asciidoc']
        
        if file_ext in docling_formats:
            try:
                # Convert document using Docling
                result = self.converter.convert(file_path)
                
                # Extract text content
                document_text = result.document.export_to_markdown()
                
                # Chunk the document
                chunks = self._chunk_text(document_text)
                
                return {
                    "text": document_text,
                    "chunks": chunks,
                    "metadata": metadata,
                    "full_document": result.document
                }
            except Exception as e:
                logger.warning(f"Docling failed to process {file_path}: {e}. Attempting to read as text...")
                # Fall through to text reading
        
        # Fallback: Try reading as text for any other format
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                document_text = f.read()
            
            # Chunk the document
            chunks = self._chunk_text(document_text)
            
            return {
                "text": document_text,
                "chunks": chunks,
                "metadata": metadata,
                "full_document": None
            }
        except Exception as e:
            logger.error(f"Failed to read file {file_path} as text: {e}")
            raise ValueError(f"Unsupported file format or unable to read file: {file_ext}")
    
    def _chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Split text into chunks with overlap, respecting sentence boundaries.
        
        Args:
            text: Text to chunk
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        import re
        
        # Split into sentences (simple approach - can be improved)
        # Split on sentence endings, but keep the punctuation
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        chunks = []
        
        if not sentences:
            # Fallback to word-based chunking if no sentences found
            words = text.split()
            for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
                chunk_words = words[i:i + self.chunk_size]
                chunk_text = " ".join(chunk_words)
                chunks.append({
                    "text": chunk_text,
                    "chunk_index": len(chunks),
                    "start_word": i,
                    "end_word": min(i + self.chunk_size, len(words))
                })
            return chunks
        current_chunk = []
        current_length = 0
        overlap_sentences = []
        
        # Calculate overlap in sentences (rough estimate)
        overlap_sentence_count = max(1, int(self.chunk_overlap / 100))  # ~1-2 sentences for overlap
        
        for i, sentence in enumerate(sentences):
            sentence_length = len(sentence.split())
            
            # If adding this sentence would exceed chunk size, finalize current chunk
            if current_length + sentence_length > self.chunk_size and current_chunk:
                chunk_text = " ".join(current_chunk)
                chunks.append({
                    "text": chunk_text,
                    "chunk_index": len(chunks),
                    "start_sentence": i - len(current_chunk),
                    "end_sentence": i
                })
                
                # Start new chunk with overlap sentences
                overlap_sentences = current_chunk[-overlap_sentence_count:] if len(current_chunk) >= overlap_sentence_count else current_chunk
                current_chunk = overlap_sentences.copy()
                current_length = sum(len(s.split()) for s in current_chunk)
            
            current_chunk.append(sentence)
            current_length += sentence_length
        
        # Add final chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append({
                "text": chunk_text,
                "chunk_index": len(chunks),
                "start_sentence": len(sentences) - len(current_chunk),
                "end_sentence": len(sentences)
            })
        
        return chunks
    
    def _format_notebook_for_rag(self, notebook_data: Dict[str, Any]) -> str:
        """
        Format Jupyter notebook data as readable text for RAG processing.
        
        Args:
            notebook_data: Parsed notebook JSON data
            
        Returns:
            Formatted text representation
        """
        lines = []
        
        # Extract notebook metadata
        nb_metadata = notebook_data.get('metadata', {})
        if nb_metadata:
            lines.append("=" * 60)
            lines.append("NOTEBOOK METADATA")
            lines.append("=" * 60)
            if 'kernelspec' in nb_metadata:
                kernel = nb_metadata['kernelspec'].get('display_name', 'Unknown')
                lines.append(f"Kernel: {kernel}")
            if 'language_info' in nb_metadata:
                lang = nb_metadata['language_info'].get('name', 'Unknown')
                lines.append(f"Language: {lang}")
            lines.append("")
        
        # Process cells
        cells = notebook_data.get('cells', [])
        if not cells:
            return "Empty notebook"
        
        lines.append("=" * 60)
        lines.append(f"NOTEBOOK CONTENT ({len(cells)} cells)")
        lines.append("=" * 60)
        lines.append("")
        
        for i, cell in enumerate(cells):
            cell_type = cell.get('cell_type', 'unknown')
            source = cell.get('source', [])
            
            # Convert source array to string
            if isinstance(source, list):
                cell_text = ''.join(source)
            else:
                cell_text = str(source)
            
            # Skip empty cells
            if not cell_text.strip():
                continue
            
            lines.append(f"[Cell {i + 1}] Type: {cell_type.upper()}")
            lines.append("-" * 60)
            
            if cell_type == 'code':
                # Format code cell
                lines.append("```python")
                lines.append(cell_text)
                lines.append("```")
                
                # Include outputs if available
                outputs = cell.get('outputs', [])
                if outputs:
                    lines.append("\nOutput:")
                    for j, output in enumerate(outputs[:5]):  # Limit to first 5 outputs
                        output_type = output.get('output_type', 'unknown')
                        if output_type == 'stream':
                            text = ''.join(output.get('text', []))
                            if text.strip():
                                lines.append(f"  [{j+1}] Stream: {text[:500]}")
                        elif output_type == 'execute_result' or output_type == 'display_data':
                            data = output.get('data', {})
                            if 'text/plain' in data:
                                text = ''.join(data['text/plain'])
                                lines.append(f"  [{j+1}] Result: {text[:500]}")
                            elif 'text/html' in data:
                                lines.append(f"  [{j+1}] HTML output (truncated)")
                        elif output_type == 'error':
                            error_name = output.get('ename', 'Error')
                            error_value = ''.join(output.get('evalue', []))
                            lines.append(f"  [{j+1}] Error: {error_name}: {error_value[:500]}")
                    
                    if len(outputs) > 5:
                        lines.append(f"  ... ({len(outputs) - 5} more outputs)")
            
            elif cell_type == 'markdown':
                # Format markdown cell
                lines.append(cell_text)
            
            elif cell_type == 'raw':
                # Format raw cell
                lines.append("[Raw Content]")
                lines.append(cell_text)
            
            else:
                # Unknown cell type
                lines.append(f"[{cell_type}]")
                lines.append(cell_text)
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_json_for_rag(self, json_data: Any, indent: int = 0, max_depth: int = 10) -> str:
        """
        Format JSON data as readable text for RAG processing.
        
        Args:
            json_data: JSON data (dict, list, or primitive)
            indent: Current indentation level
            max_depth: Maximum nesting depth to prevent excessive recursion
            
        Returns:
            Formatted text representation
        """
        if max_depth <= 0:
            return "[...]"
        
        if isinstance(json_data, dict):
            lines = []
            for key, value in json_data.items():
                key_str = str(key)
                if isinstance(value, (dict, list)):
                    lines.append(f"{'  ' * indent}{key_str}:")
                    lines.append(self._format_json_for_rag(value, indent + 1, max_depth - 1))
                else:
                    value_str = str(value)
                    # Truncate very long values
                    if len(value_str) > 500:
                        value_str = value_str[:500] + "... [truncated]"
                    lines.append(f"{'  ' * indent}{key_str}: {value_str}")
            return "\n".join(lines)
        
        elif isinstance(json_data, list):
            if len(json_data) == 0:
                return f"{'  ' * indent}[]"
            
            lines = []
            # For lists, show first few items and summary
            max_items = 20
            for i, item in enumerate(json_data[:max_items]):
                if isinstance(item, (dict, list)):
                    lines.append(f"{'  ' * indent}[{i}]:")
                    lines.append(self._format_json_for_rag(item, indent + 1, max_depth - 1))
                else:
                    item_str = str(item)
                    if len(item_str) > 200:
                        item_str = item_str[:200] + "... [truncated]"
                    lines.append(f"{'  ' * indent}[{i}]: {item_str}")
            
            if len(json_data) > max_items:
                lines.append(f"{'  ' * indent}... ({len(json_data) - max_items} more items)")
            
            return "\n".join(lines)
        
        else:
            # Primitive types
            result = str(json_data)
            if len(result) > 1000:
                result = result[:1000] + "... [truncated]"
            return result
    
    def process_directory(self, directory_path: str) -> List[Dict[str, Any]]:
        """
        Process all supported documents in a directory.
        
        Args:
            directory_path: Path to directory containing documents
            
        Returns:
            List of processed documents
        """
        supported_extensions = ['.pdf', '.docx', '.doc', '.txt', '.md', '.log', '.csv', '.json', '.ipynb']
        processed_docs = []
        
        # Get all files first
        files_to_process = []
        for filename in os.listdir(directory_path):
            file_path = os.path.join(directory_path, filename)
            if os.path.isfile(file_path):
                ext = os.path.splitext(filename)[1].lower()
                if ext in supported_extensions:
                    files_to_process.append((file_path, filename))
        
        print(f"Found {len(files_to_process)} document(s) to process")
        
        # Process files with progress indication
        for i, (file_path, filename) in enumerate(files_to_process, 1):
            try:
                print(f"[{i}/{len(files_to_process)}] Processing: {filename}")
                doc = self.process_document(file_path)
                processed_docs.append(doc)
                print(f"  ✓ Processed: {len(doc['chunks'])} chunks extracted")
            except Exception as e:
                print(f"  ✗ Error processing {filename}: {e}")
        
        return processed_docs
