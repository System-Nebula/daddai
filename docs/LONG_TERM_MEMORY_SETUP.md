# Long-Term Memory & Document Upload System

## ✅ What's Been Added

### 1. Long-Term Memory System
- **Memory Storage**: User memories stored in Neo4j with embeddings
- **RAG-Based Retrieval**: Uses semantic search to find relevant memories
- **Per-User Memory Banks**: Each user has their own memory storage
- **Automatic Storage**: Important conversation turns are automatically stored

### 2. Shared Document System
- **Document Upload**: Users can upload PDFs, DOCX, text files via Discord
- **Shared Knowledge Base**: Uploaded documents are available to ALL users
- **Automatic Processing**: Documents are processed with Docling and stored in Neo4j
- **RAG Integration**: Shared documents are searched alongside personal documents

### 3. Admin UI
- **User Management**: View all users with memory counts
- **Memory Browser**: View any user's memories with pagination
- **Document List**: View all shared documents
- **Discord Embeds**: Nice UI with buttons for navigation

## 🚀 New Commands

### User Commands
- `/upload <file>` - Upload a document to shared knowledge base
- `/rag <question>` - Ask questions (now uses memory + shared docs)
- `/clear` - Clear conversation history

### Admin Commands
- `/admin users` - List all users with memory statistics
- `/admin memories <user>` - View a user's memories (paginated)
- `/admin documents` - List all shared documents

## 📋 Setup

### 1. Update Neo4j Schema
The new memory and document nodes will be created automatically on first use.

### 2. Test Memory API
```bash
python memory_api.py --action store --user-id test123 --content "User likes pizza"
python memory_api.py --action get --user-id test123
python memory_api.py --action list-users
```

### 3. Test Document API
```bash
python document_api.py --action upload --user-id test123 --file-path "test.pdf" --file-name "test.pdf"
python document_api.py --action list
```

### 4. Update Discord Bot
The bot now automatically:
- Stores important conversation turns as memories
- Uses memories when answering questions
- Searches shared documents alongside personal documents

## 🔧 How It Works

### Memory Flow
1. User asks question → Bot queries RAG
2. Bot gets answer → Stores as memory (if substantial)
3. Next question → Bot retrieves relevant memories
4. Memories + Documents → Combined context for better answers

### Document Upload Flow
1. User uploads file → `/upload` command
2. File downloaded → Saved temporarily
3. Docling processes → Extracts text and chunks
4. Embeddings generated → Using GPU
5. Stored in Neo4j → As SharedDocument nodes
6. Available to all users → Searched in RAG queries

### Admin UI Flow
1. Admin runs `/admin memories @user`
2. Bot retrieves user memories
3. Creates paginated embeds
4. Buttons for navigation
5. View memories in Discord

## 📊 Database Schema

### New Node Types
- **Memory**: User memories with embeddings
- **SharedDocument**: Documents uploaded by users
- **SharedChunk**: Chunks from shared documents
- **User**: Enhanced with memory relationships

### Relationships
- `(User)-[:HAS_MEMORY]->(Memory)`
- `(User)-[:UPLOADED]->(SharedDocument)`
- `(SharedDocument)-[:CONTAINS]->(SharedChunk)`

## 🎯 Features

✅ **Long-term memory** - Remembers important information across sessions
✅ **RAG-based relevance** - Finds relevant memories using semantic search
✅ **Shared documents** - Upload once, available to everyone
✅ **Admin UI** - Beautiful Discord embeds with pagination
✅ **Automatic storage** - Important conversations saved automatically
✅ **Context-aware** - Uses memories + documents + conversation history

## 🐛 Troubleshooting

### Memories not being stored
- Check Neo4j is running
- Verify memory_store.py can connect
- Check embeddings are being generated

### Documents not uploading
- Check file size (max 25MB)
- Verify file type is supported
- Check temp directory permissions
- Ensure Docling can process the file

### Admin commands not working
- Verify user has ADMINISTRATOR permission
- Check command registration
- Verify memory_api.py and document_api.py work

## 📝 Next Steps

1. **Test the system**:
   - Upload a document: `/upload`
   - Ask questions: `/rag`
   - View memories: `/admin memories @yourself`

2. **Customize**:
   - Adjust memory storage threshold in `index.js`
   - Modify memory types in `memory_store.py`
   - Change document processing in `document_processor.py`

3. **Monitor**:
   - Use `/admin users` to see memory growth
   - Use `/admin documents` to see shared documents
   - Check Neo4j for data structure

The system is now fully functional with long-term memory and document uploads! 🎉

