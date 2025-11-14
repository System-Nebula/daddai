@echo off
echo ========================================
echo RAG System Setup for Windows
echo ========================================
echo.

echo Checking Python installation...
python --version
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from python.org
    pause
    exit /b 1
)

echo.
echo Installing PyTorch with CUDA support...
echo (This may take a few minutes)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

echo.
echo Installing other dependencies...
pip install -r requirements.txt

echo.
echo ========================================
echo Setup complete!
echo ========================================
echo.
echo Next steps:
echo 1. Make sure Neo4j is running
echo 2. Make sure LMStudio is running with a model loaded
echo 3. Create a .env file with your configuration
echo 4. Run: python main.py ingest --path your_documents/
echo.
pause
