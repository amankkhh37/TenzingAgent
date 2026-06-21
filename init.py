"""
Initialization script - Run this once to setup the system
"""
import sys
from pathlib import Path

def check_python_version():
    """Verify Python 3.12+"""
    if sys.version_info < (3, 12):
        print(f"❌ Python 3.12+ required. You have {sys.version}")
        sys.exit(1)
    print(f"✅ Python {sys.version.split()[0]}")

def check_imports():
    """Check if all required packages are installed"""
    required = [
        "playwright",
        "streamlit",
        "sqlalchemy",
        "requests",
        "pandas",
        "plotly",
        "pydantic",
        "dotenv"
    ]
    
    missing = []
    for package in required:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"❌ Missing packages: {', '.join(missing)}")
        print(f"   Run: pip install {' '.join(missing)}")
        return False
    
    print(f"✅ All {len(required)} packages installed")
    return True

def init_database():
    """Initialize SQLite database"""
    try:
        from database import init_db
        init_db()
        print("✅ Database initialized")
        return True
    except Exception as e:
        print(f"❌ Database init failed: {e}")
        return False

def create_directories():
    """Create required directories"""
    dirs = ["data", "logs", "screenshots", "exports"]
    for d in dirs:
        Path(d).mkdir(exist_ok=True)
    print(f"✅ Created {len(dirs)} directories")

def verify_ollama():
    """Check if Ollama is running"""
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            print("✅ Ollama server running")
            return True
    except:
        pass
    
    print("⚠️  Ollama not running. Start it with: ollama serve")
    return False

def main():
    print("\n🌍 Tenzing Growth Agent - Initialization")
    print("=" * 50)
    
    # Check Python
    check_python_version()
    
    # Check imports
    if not check_imports():
        print("\n❌ Setup failed: Install missing packages")
        print("   Run: pip install -r requirements.txt")
        return False
    
    # Create dirs
    create_directories()
    
    # Init database
    if not init_database():
        return False
    
    # Check Ollama
    verify_ollama()
    
    print("\n" + "=" * 50)
    print("✅ Setup complete!")
    print("\n📖 Next steps:")
    print("   1. Read QUICKSTART.md")
    print("   2. Start Ollama: ollama serve")
    print("   3. Start Dashboard: streamlit run app.py")
    print("   4. Start Scanner: python scanner.py")
    print("\n" + "=" * 50)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
