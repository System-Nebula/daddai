# Quick Start Guide - Neo4j Setup

## Step 1: Start Your Database in Neo4j Desktop

1. **Open Neo4j Desktop** (from Start Menu)

2. **Create a Project** (if you haven't already):
   - Click "New Project"
   - Name it (e.g., "RAG System")
   - Click "Create"

3. **Create a Database** (if you haven't already):
   - Click "Add" → "Local DBMS"
   - Set a **Name** (e.g., "rag-database")
   - Set a **Password** (remember this!)
   - Choose Neo4j version (5.x recommended)
   - Click "Create"

4. **Start the Database**:
   - Click the **"Start"** button on your database
   - Wait for it to turn **green** (running status)
   - The status should show "Running"

## Step 2: Configure Your .env File

Create or edit `.env` file in your project root with:

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here
```

**Important**: Replace `your_password_here` with the password you set when creating the database!

## Step 3: Test the Connection

Run:
```bash
python setup_neo4j.py
```

If successful, you'll see:
- Connection successful message
- Database schema initialized
- Ready to use!

## Step 4: Start Using Your RAG System

Once Neo4j is connected:

1. **Ingest documents**:
   ```bash
   python main.py ingest --path your_documents/
   ```

2. **Query the system**:
   ```bash
   python main.py query --question "What is this document about?"
   ```

3. **Interactive mode**:
   ```bash
   python main.py interactive
   ```

## Troubleshooting

### "Connection refused" error
- Make sure Neo4j Desktop is open
- Make sure your database is **STARTED** (green status)
- Check the password in `.env` matches Neo4j Desktop

### "Authentication failed" error
- Check your password in `.env` file
- Reset password in Neo4j Desktop if needed
- Update `.env` with the new password

### Database won't start
- Check if port 7687 is already in use
- Try stopping and restarting the database
- Check Neo4j Desktop logs for errors

## Need Help?

- Neo4j Desktop docs: https://neo4j.com/developer/neo4j-desktop/
- Check `NEO4J_SETUP.md` for detailed instructions

