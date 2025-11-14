# Neo4j Setup Instructions for Windows

## Quick Installation Guide

### Step 1: Download Neo4j Desktop
1. The download page should have opened in your browser
2. If not, visit: https://neo4j.com/download/
3. Click "Download Neo4j Desktop" for Windows
4. Save the installer to your Downloads folder

### Step 2: Install Neo4j Desktop
1. Navigate to your Downloads folder
2. Double-click `neo4j-desktop-installer.exe`
3. Follow the installation wizard:
   - Accept the license agreement
   - Choose installation location (default is fine)
   - Click "Install"
   - Wait for installation to complete

### Step 3: Launch and Set Up Neo4j Desktop
1. Launch Neo4j Desktop from Start Menu
2. Create a Neo4j account (or sign in if you have one)
3. Create a new project:
   - Click "New Project"
   - Give it a name (e.g., "RAG System")

### Step 4: Create a Database
1. In your project, click "Add" → "Local DBMS"
2. Configure your database:
   - **Name**: `rag-database` (or any name you prefer)
   - **Password**: Set a strong password (remember this!)
   - **Version**: Choose the latest stable version (5.x recommended)
3. Click "Create"

### Step 5: Start the Database
1. Click the "Start" button on your database
2. Wait for it to start (the button will turn green)
3. Click "Open" to open Neo4j Browser (optional, for testing)

### Step 6: Configure for Your RAG System
1. In Neo4j Desktop, select your database
2. Go to "Settings" tab
3. Add these settings (if not already present):
   ```
   dbms.memory.heap.initial_size=2G
   dbms.memory.heap.max_size=4G
   dbms.memory.pagecache.size=2G
   ```
4. Click "Apply" and restart the database

### Step 7: Update Your .env File
Create or update `.env` file in your project root:
```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here
```

Replace `your_password_here` with the password you set in Step 4.

### Step 8: Test Connection
Run this command to test:
```bash
python -c "from neo4j_store import Neo4jStore; store = Neo4jStore(); print('Connected successfully!'); store.close()"
```

## Troubleshooting

### Database won't start
- Check if port 7687 is already in use
- Try stopping and restarting the database
- Check Neo4j Desktop logs for errors

### Connection refused
- Make sure the database is started (green status)
- Verify the password in your .env file matches Neo4j Desktop
- Check that Neo4j is listening on `bolt://localhost:7687`

### Forgot password
- In Neo4j Desktop, select your database
- Click "Reset Password" in the settings
- Set a new password and update your .env file

## Next Steps

Once Neo4j is set up:
1. Start ingesting documents: `python main.py ingest --path your_documents/`
2. Query your RAG system: `python main.py query --question "Your question"`

For more help, visit: https://neo4j.com/docs/

