"""
Script to fix imports after reorganization.
"""
import os
import re
from pathlib import Path

# Mapping of old imports to new imports
IMPORT_MAPPINGS = {
    'from src.processors.document_processor import': 'from src.processors.document_processor import',
    'from src.processors.embedding_generator import': 'from src.processors.embedding_generator import',
    'from src.stores.neo4j_store import': 'from src.stores.neo4j_store import',
    'from src.core.rag_pipeline import': 'from src.core.rag_pipeline import',
    'from src.core.enhanced_rag_pipeline import': 'from src.core.enhanced_rag_pipeline import',
    'from src.clients.lmstudio_client import': 'from src.clients.lmstudio_client import',
    'from src.stores.memory_store import': 'from src.stores.memory_store import',
    'from src.stores.document_store import': 'from src.stores.document_store import',
    'from src.stores.hybrid_memory_store import': 'from src.stores.hybrid_memory_store import',
    'from src.stores.hybrid_document_store import': 'from src.stores.hybrid_document_store import',
    'from src.search.hybrid_search import': 'from src.search.hybrid_search import',
    'from src.search.query_expander import': 'from src.search.query_expander import',
    'from src.search.query_analyzer import': 'from src.search.query_analyzer import',
    'from src.search.enhanced_document_search import': 'from src.search.enhanced_document_search import',
    'from src.search.enhanced_query_understanding import': 'from src.search.enhanced_query_understanding import',
    'from src.search.multi_query_retrieval import': 'from src.search.multi_query_retrieval import',
    'from src.search.smart_document_selector import': 'from src.search.smart_document_selector import',
    'from src.memory.intelligent_memory import': 'from src.memory.intelligent_memory import',
    'from src.memory.conversation_store import': 'from src.memory.conversation_store import',
    'from src.memory.conversation_threading import': 'from src.memory.conversation_threading import',
    'from src.utils.cross_encoder_reranker import': 'from src.utils.cross_encoder_reranker import',
    'from src.utils.document_comparison import': 'from src.utils.document_comparison import',
    'from src.utils.user_state_manager import': 'from src.utils.user_state_manager import',
    'from src.utils.user_relations import': 'from src.utils.user_relations import',
    'from src.utils.knowledge_graph import': 'from src.utils.knowledge_graph import',
    'from src.tools.llm_tools import': 'from src.tools.llm_tools import',
    'from src.tools.meta_tools import': 'from src.tools.meta_tools import',
    'from src.tools.action_parser import': 'from src.tools.action_parser import',
    'from src.tools.llm_item_tracker import': 'from src.tools.llm_item_tracker import',
    'from src.evaluation.rag_evaluator import': 'from src.evaluation.rag_evaluator import',
    'from src.evaluation.performance_monitor import': 'from src.evaluation.performance_monitor import',
    'from src.evaluation.performance_optimizations import': 'from src.evaluation.performance_optimizations import',
    'from src.evaluation.ab_testing import': 'from src.evaluation.ab_testing import',
    'from src.evaluation.check_llm_hallucination import': 'from src.evaluation.check_llm_hallucination import',
}

def add_path_insert_if_needed(content, file_path):
    """Add sys.path.insert if not already present."""
    if 'sys.path.insert' in content or 'import sys' not in content:
        # Check if we need to add path insertion
        has_src_import = any('from src.' in line for line in content.split('\n'))
        if has_src_import and 'sys.path.insert' not in content:
            # Calculate relative path to root
            depth = len(Path(file_path).parent.parts) - len(Path('.').resolve().parts)
            if depth > 0:
                path_parts = ['..'] * depth
                path_str = "', '".join(path_parts)
                path_insert = f"import sys\nimport os\nsys.path.insert(0, os.path.join(os.path.dirname(__file__), '{path_str}'))\n"
                # Insert after first import or at the beginning
                lines = content.split('\n')
                insert_idx = 0
                for i, line in enumerate(lines):
                    if line.startswith('import ') or line.startswith('from '):
                        insert_idx = i + 1
                        break
                lines.insert(insert_idx, path_insert)
                return '\n'.join(lines)
    return content

def fix_imports_in_file(file_path):
    """Fix imports in a single file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Apply import mappings
        for old_import, new_import in IMPORT_MAPPINGS.items():
            content = content.replace(old_import, new_import)
        
        # Add path insertion if needed
        content = add_path_insert_if_needed(content, file_path)
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    """Fix imports in all Python files."""
    root = Path('.')
    
    # Files to process
    python_files = []
    for pattern in ['src/**/*.py', 'scripts/**/*.py', 'tests/**/*.py', '*.py']:
        python_files.extend(root.glob(pattern))
    
    # Exclude certain files
    excluded = {'scripts/fix_imports.py', '__pycache__'}
    python_files = [f for f in python_files if not any(ex in str(f) for ex in excluded)]
    
    updated = 0
    for file_path in python_files:
        if fix_imports_in_file(file_path):
            print(f"Updated: {file_path}")
            updated += 1
    
    print(f"\nUpdated {updated} files.")

if __name__ == '__main__':
    main()

