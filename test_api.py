"""
End-to-end test script for RFP Builder API
Tests the complete workflow including:
- File upload
- RFP analysis
- Response generation with diagrams/charts/tables
- Code interpretation
- Review and revision loop
"""

import requests
import json
import time
from pathlib import Path

# Configuration
API_BASE_URL = "http://127.0.0.1:8000"
EXAMPLES_DIR = Path(__file__).parent / "examples"

# File paths
RFP_TO_ANSWER = EXAMPLES_DIR / "rfp_to_answer" / "RFP-2022-01-LaSalle-SSES-Engineering-Services-Phase-1.pdf"
PAST_RFP = EXAMPLES_DIR / "past_rfps" / "RFP_Response.pdf"
INTERNAL_DOC = EXAMPLES_DIR / "internal_capabilties" / "Internal_Capabilities_Overview.pdf"


def test_health_check():
    """Test that the API is running"""
    print("\n" + "="*60)
    print("🔍 Testing API Health Check...")
    print("="*60)
    
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            print("✅ API is healthy!")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"❌ API health check failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API. Is the server running?")
        return False


def test_rfp_workflow():
    """Test the complete RFP workflow"""
    print("\n" + "="*60)
    print("🚀 Testing RFP Workflow...")
    print("="*60)
    
    # Check files exist
    print("\n📁 Checking example files...")
    for name, path in [("RFP to Answer", RFP_TO_ANSWER), 
                       ("Past RFP", PAST_RFP), 
                       ("Internal Doc", INTERNAL_DOC)]:
        if path.exists():
            print(f"   ✅ {name}: {path.name}")
        else:
            print(f"   ❌ {name} not found: {path}")
            return None
    
    # Prepare multipart form data
    print("\n📤 Uploading files to API...")
    
    files = []
    try:
        # Open files for multipart upload
        rfp_file = open(RFP_TO_ANSWER, 'rb')
        past_rfp_file = open(PAST_RFP, 'rb')
        internal_file = open(INTERNAL_DOC, 'rb')
        
        files = [
            ('rfp', (RFP_TO_ANSWER.name, rfp_file, 'application/pdf')),
            ('example_rfps', (PAST_RFP.name, past_rfp_file, 'application/pdf')),
            ('company_context', (INTERNAL_DOC.name, internal_file, 'application/pdf')),
        ]
        
        # Make API request
        print("   Sending request to /api/rfp/generate...")
        print("   ⏳ This may take several minutes...")
        
        start_time = time.time()
        response = requests.post(
            f"{API_BASE_URL}/api/rfp/generate",
            files=files,
            timeout=600  # 10 minute timeout
        )
        elapsed = time.time() - start_time
        
        print(f"\n   ⏱️  Request completed in {elapsed:.1f} seconds")
        print(f"   📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            return result
        else:
            print(f"   ❌ Error: {response.text[:500]}")
            return None
            
    except requests.exceptions.Timeout:
        print("   ❌ Request timed out after 10 minutes")
        return None
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None
    finally:
        # Close files
        for f in files:
            try:
                f[1][1].close()
            except:
                pass


def analyze_result(result: dict):
    """Analyze the workflow result"""
    print("\n" + "="*60)
    print("📋 Analyzing Workflow Result...")
    print("="*60)
    
    if not result:
        print("❌ No result to analyze")
        return
    
    # Check for response content
    if 'response' in result:
        response = result['response']
        print(f"\n📝 Response length: {len(response)} characters")
        
        # Check for visual elements
        has_mermaid = '```mermaid' in response
        has_python_chart = '```python' in response or '![' in response
        has_table = '|' in response and '---' in response
        
        print("\n🎨 Visual Elements Detection:")
        print(f"   {'✅' if has_mermaid else '❌'} Mermaid diagrams")
        print(f"   {'✅' if has_python_chart else '❌'} Charts/Graphs")
        print(f"   {'✅' if has_table else '❌'} Tables")
        
        # Show first 2000 chars of response
        print("\n📄 Response Preview (first 2000 chars):")
        print("-"*50)
        print(response[:2000])
        if len(response) > 2000:
            print(f"\n... [{len(response) - 2000} more characters]")
    
    # Check for generated images
    if 'images' in result and result['images']:
        print(f"\n🖼️  Generated Images: {len(result['images'])}")
        for i, img in enumerate(result['images'][:5]):
            print(f"   Image {i+1}: {img.get('description', 'No description')[:50]}...")
    
    # Check workflow metadata
    if 'metadata' in result:
        meta = result['metadata']
        print(f"\n📊 Workflow Metadata:")
        print(f"   Steps completed: {meta.get('steps_completed', 'N/A')}")
        print(f"   Revisions needed: {meta.get('revision_count', 0)}")
        print(f"   Total time: {meta.get('total_time', 'N/A')}")
    
    # Save full result to file
    output_file = Path(__file__).parent / "test_output.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Full result saved to: {output_file}")
    
    # Save response as markdown
    if 'response' in result:
        md_file = Path(__file__).parent / "test_output.md"
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(result['response'])
        print(f"📝 Response saved to: {md_file}")


def check_logs():
    """Check the logs directory for output"""
    print("\n" + "="*60)
    print("📂 Checking Log Files...")
    print("="*60)
    
    logs_dir = Path(__file__).parent / "backend" / "logs"
    
    if not logs_dir.exists():
        # Try alternative location
        logs_dir = Path(__file__).parent / "logs"
    
    if not logs_dir.exists():
        print(f"⚠️  Logs directory not found. Will be created on first API call.")
        return
    
    # Find most recent session
    sessions = sorted(logs_dir.iterdir(), reverse=True)
    
    if not sessions:
        print("⚠️  No log sessions found yet.")
        return
    
    latest_session = sessions[0]
    print(f"\n📁 Latest session: {latest_session.name}")
    
    # List log files
    log_files = list(latest_session.glob("*.md")) + list(latest_session.glob("*.json"))
    print(f"   Found {len(log_files)} log files:")
    
    for log_file in sorted(log_files):
        size = log_file.stat().st_size
        print(f"   - {log_file.name} ({size:,} bytes)")
        
        # Show preview of markdown logs
        if log_file.suffix == '.md' and size > 0:
            content = log_file.read_text(encoding='utf-8')
            preview = content[:500]
            print(f"\n     Preview of {log_file.name}:")
            print("     " + "-"*40)
            for line in preview.split('\n')[:10]:
                print(f"     {line}")
            if len(content) > 500:
                print(f"     ... [{len(content) - 500} more characters]")


def main():
    print("\n" + "="*60)
    print("🏗️  RFP BUILDER - End-to-End Test")
    print("="*60)
    print(f"API URL: {API_BASE_URL}")
    print(f"Examples: {EXAMPLES_DIR}")
    
    # Test 1: Health check
    if not test_health_check():
        print("\n⚠️  API not available. Please start the server first:")
        print("   cd backend && python -m uvicorn app.main:app --reload")
        return
    
    # Test 2: Run workflow
    result = test_rfp_workflow()
    
    # Test 3: Analyze result
    analyze_result(result)
    
    # Test 4: Check logs
    check_logs()
    
    print("\n" + "="*60)
    print("✅ Test Complete!")
    print("="*60)
    print("\nNext steps:")
    print("1. Check test_output.md for the generated response")
    print("2. Check test_output.json for the full API response")
    print("3. Check backend/logs/ for detailed LLM interaction logs")


if __name__ == "__main__":
    main()
