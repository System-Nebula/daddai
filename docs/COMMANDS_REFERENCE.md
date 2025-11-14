# Complete Commands Reference

This document lists all available commands in the system.

## Table of Contents
1. [Python CLI Commands](#python-cli-commands)
2. [Discord Bot Slash Commands](#discord-bot-slash-commands)
3. [Discord Bot Auto-Detection](#discord-bot-auto-detection)
4. [Python API Commands](#python-api-commands)
5. [Action Commands](#action-commands)

---

## Python CLI Commands

These are commands you can run from the terminal using `python main.py`:

### 1. **Ingest Documents**
Process and store documents in Neo4j.

```bash
# Process a single file
python main.py ingest --path documents/sample.pdf

# Process all documents in a directory
python main.py ingest --path documents/
```

**Supported formats:** PDF, DOCX, DOC, TXT, MD, CSV, JSON, IPYNB

**Options:**
- `--path` (required): Path to file or directory

---

### 2. **Query RAG System**
Ask a single question to the RAG system.

```bash
python main.py query --question "What is the main topic?" --top-k 10
```

**Options:**
- `--question` (required): Your question
- `--top-k` (optional): Number of chunks to retrieve (default: 10)

---

### 3. **Interactive Mode**
Start an interactive session for multiple questions.

```bash
python main.py interactive
```

**Usage:**
- Type questions and press Enter
- Type `exit` or `quit` to stop

---

## Discord Bot Slash Commands

These commands are available in Discord when you mention the bot or use slash commands:

### 1. **`/rag`** - Query RAG System
Query the RAG system with a question.

**Usage:**
```
/rag question: "What is the main topic of the documents?"
```

**Behavior:**
- Uses conversation history for context
- Stores conversation turn
- Returns answer from RAG system

---

### 2. **`/upload`** - Upload Document
Upload a document to the shared knowledge base.

**Usage:**
```
/upload file: [attach PDF/DOCX/TXT/MD file]
```

**Supported formats:**
- `.pdf` - PDF documents
- `.docx` - Microsoft Word documents
- `.doc` - Legacy Word documents
- `.txt` - Plain text files
- `.md` - Markdown files

**File size limit:** 25MB

---

### 3. **`/clear`** - Clear Conversation
Clear your conversation history.

**Usage:**
```
/clear
```

**Note:** Only clears short-term conversation history, NOT long-term memories.

---

### 4. **`/admin`** - Admin Commands
Admin-only commands for managing the system.

#### `/admin users`
List all users with memory counts.

#### `/admin memories [user: @mention] [username: string]`
View a user's memories. Can search by mention or username.

#### `/admin documents`
List all shared documents in the knowledge base.

---

### 5. **`/config`** - Bot Configuration
Configure bot settings (Admin only).

#### `/config channel [channel: #channel]`
Set the channel where the bot responds. Leave empty to allow all channels.

#### `/config status`
View current bot configuration.

#### `/config enable`
Enable bot responses.

#### `/config disable`
Disable bot responses globally.

---

## Discord Bot Auto-Detection

The bot automatically detects these without needing commands:

### **Document Upload Detection**
- Automatically detects when users upload files (PDF, DOCX, TXT, MD)
- Processes and stores them automatically
- Works in configured channel (or all channels if none configured)

### **Question Detection**
- Automatically detects when users ask questions
- Works with mentions: `@bot_name your question`
- Uses RAG system for document-related questions
- Uses simple chat for general questions
- Stores important information as long-term memories

---

## Python API Commands

These are used internally by the Discord bot, but can also be called directly:

### **rag_api.py**
Python API wrapper for RAG queries.

```bash
python rag_api.py --question "Your question" --top-k 10 --channel-id "123456789"
```

**Options:**
- `--question` (required): Question to ask
- `--top-k` (optional): Number of chunks (default: 10)
- `--user-id` (optional): Discord user ID (deprecated)
- `--channel-id` (optional): Discord channel ID for memory
- `--use-memory` (optional): Use long-term memory (default: true)
- `--use-shared-docs` (optional): Use shared documents (default: true)

**Returns:** JSON response with answer and metadata

---

## Action Commands

The enhanced system understands natural language action commands:

### **Give Commands**
Transfer resources or items between users.

```
give @alexei 20 gold pieces
give @alexei a sword
give 20 gold pieces to @alexei
```

### **State Queries**
Query user state (gold, inventory, etc.).

```
how much gold do I have?
how much gold does @alexei have?
what is my inventory?
what is @alexei's balance?
```

### **Set Commands**
Set user state values.

```
set @alexei level to 10
set level to 10 for @alexei
```

### **Add Commands**
Add resources or items.

```
add 50 gold to @alexei
add a potion to @alexei
```

---

## Quick Command Examples

### Python CLI Examples

```bash
# Ingest documents
python main.py ingest --path my_documents/

# Single query
python main.py query --question "What are the key points?" --top-k 5

# Interactive mode
python main.py interactive
```

### Discord Bot Examples

```
# Query with slash command
/rag question: "What does the project plan say about deadlines?"

# Upload document
/upload file: [attach project_plan.pdf]

# Clear conversation
/clear

# Admin: View documents
/admin documents

# Admin: View user memories
/admin memories user: @username
```

### Natural Language Examples (Discord)

```
# Ask a question (mention bot)
@bot_name what is the project status?

# Give gold to user
give @alexei 20 gold pieces

# Check balance
how much gold does @alexei have?

# Upload document (just attach file)
[attach file in Discord]
```

---

## Command Permissions

### **Public Commands** (All Users)
- `/rag` - Query RAG system
- `/upload` - Upload documents
- `/clear` - Clear conversation
- Natural language questions (mentions)
- Action commands (give, query state)

### **Admin Commands** (Administrators Only)
- `/admin` - All admin subcommands
- `/config` - Bot configuration

---

## Tips

1. **Use Interactive Mode** for multiple questions: `python main.py interactive`
2. **Mention the bot** in Discord for quick questions (no slash command needed)
3. **Upload files** by attaching them directly (auto-detected)
4. **Use slash commands** for explicit actions (`/rag`, `/upload`)
5. **Action commands** work naturally: "give @user 20 gold"

---

## Need Help?

- Check `COMMANDS.md` in `discord-bot/` for detailed Discord commands
- Check `README.md` for setup and usage instructions
- Check `QUICK_START.md` for quick setup guide

