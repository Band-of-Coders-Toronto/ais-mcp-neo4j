#!/bin/bash

# Setup script for Neo4j MCP Server development environment
# Compatible with Cygwin and other bash environments
# Run from: ais/ais-mcp-neo4j/servers/mcp-neo4j-cypher

set -e  # Exit on any error

echo "🚀 Setting up Neo4j MCP Server development environment..."
echo "Current directory: $(pwd)"

# Check if we're in the correct directory
if [[ ! -f "pyproject.toml" ]]; then
    echo "❌ Error: pyproject.toml not found. Please run this script from the mcp-neo4j-cypher directory."
    echo "Expected path: .../ais/ais-mcp-neo4j/servers/mcp-neo4j-cypher"
    exit 1
fi

echo "✅ Confirmed we're in the correct directory"

# Check if Python is available
if ! command -v python &> /dev/null; then
    echo "❌ Error: Python is not installed or not in PATH"
    echo "Please install Python 3.11+ and ensure it's available in your PATH"
    exit 1
fi

PYTHON_VERSION=$(python --version 2>&1 | cut -d' ' -f2)
echo "✅ Found Python version: $PYTHON_VERSION"

# Create virtual environment if it doesn't exist
if [[ ! -d "venv" ]]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
if [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "msys" ]]; then
    # Windows/Cygwin path
    source venv/Scripts/activate
else
    # Unix/Linux path
    source venv/bin/activate
fi

echo "✅ Virtual environment activated"

# Verify we're in the virtual environment
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✅ Confirmed virtual environment is active: $VIRTUAL_ENV"
else
    echo "❌ Warning: Virtual environment may not be properly activated"
fi

# Display current pip version (but don't upgrade it)
PIP_VERSION=$(pip --version 2>&1 | cut -d' ' -f2)
echo "📝 Current pip version: $PIP_VERSION"
echo "⚠️  Note: pip will NOT be upgraded (known to cause issues)"

# Install hatchling first (required for pyproject.toml builds)
echo "📦 Installing hatchling..."
pip install --no-cache-dir hatchling

# Install core dependencies
echo "📦 Installing core dependencies..."
pip install --no-cache-dir neo4j>=5.26.0 mcp>=1.6.0

# Install the project in editable mode
echo "📦 Installing project in editable mode..."
pip install --no-cache-dir -e .

# Install development dependencies
echo "📦 Installing development dependencies..."
pip install --no-cache-dir pytest pytest-asyncio

echo ""
echo "🎉 Setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Activate the virtual environment:"
if [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "msys" ]]; then
    echo "   source venv/Scripts/activate"
else
    echo "   source venv/bin/activate"
fi
echo ""
echo "2. Set up your Neo4j environment variables:"
echo "   export NEO4J_URI=\"bolt://localhost:7687\""
echo "   export NEO4J_USERNAME=\"neo4j\""
echo "   export NEO4J_PASSWORD=\"your_password\""
echo "   export NEO4J_DATABASE=\"neo4j\""
echo ""
echo "3. Run tests to verify setup:"
echo "   pytest tests/integration/ -v"
echo ""
echo "4. Check available tools:"
echo "   python -c \"from src.mcp_neo4j_cypher.server import create_mcp_server; print('Setup successful!')\""
echo ""
echo "🔧 Development workflow:"
echo "   - Edit server.py to add new tools"
echo "   - Write failing tests first (TDD approach)"
echo "   - Follow development_iteration.md for Docker deployment"
echo ""
echo "📚 Documentation:"
echo "   - customer_tools_priority.md - Implementation priorities"
echo "   - helpful_verbs.md - Available Cypher queries"
echo "   - system_overview.md - System architecture"
echo ""
echo "✅ Environment ready for development!"
