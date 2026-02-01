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
    print("Testing API Health Check...")
    print("="*60)
    
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            print("[OK] API is healthy!")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"[FAIL] API health check failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("[FAIL] Cannot connect to API. Is the server running?")
        return False


def test_rfp_workflow():
    """Test the complete RFP workflow"""
    print("\n" + "="*60)
    print("Testing RFP Workflow...")
    print("="*60)
    
    # Check files exist
    print("\nChecking example files...")
    for name, path in [("RFP to Answer", RFP_TO_ANSWER), 
                       ("Past RFP", PAST_RFP), 
                       ("Internal Doc", INTERNAL_DOC)]:
        if path.exists():
            print(f"   [OK] {name}: {path.name}")
        else:
            print(f"   [FAIL] {name} not found: {path}")
            return None
    
    # Prepare multipart form data
    print("\nUploading files to API...")
    
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
        print("   [WAIT] This may take several minutes...")
        
        start_time = time.time()
        response = requests.post(
            f"{API_BASE_URL}/api/rfp/generate",
            files=files,
            timeout=600  # 10 minute timeout
        )
        elapsed = time.time() - start_time
        
        print(f"\n   Request completed in {elapsed:.1f} seconds")
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            return result
        else:
            print(f"   [FAIL] Error: {response.text[:500]}")
            return None
            
    except requests.exceptions.Timeout:
        print("   [FAIL] Request timed out after 10 minutes")
        return None
    except Exception as e:
        print(f"   [FAIL] Error: {e}")
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
    print("Analyzing Workflow Result...")
    print("="*60)
    
    if not result:
        print("[FAIL] No result to analyze")
        return
    
    # Check for response content
    if 'response' in result:
        response = result['response']
        print(f"\nResponse length: {len(response)} characters")
        
        # Check for visual elements
        has_mermaid = '```mermaid' in response
        has_python_chart = '```python' in response or '![' in response
        has_table = '|' in response and '---' in response
        
        print("\nVisual Elements Detection:")
        print(f"   {'[OK]' if has_mermaid else '[FAIL]'} Mermaid diagrams")
        print(f"   {'[OK]' if has_python_chart else '[FAIL]'} Charts/Graphs")
        print(f"   {'[OK]' if has_table else '[FAIL]'} Tables")
        
        # Show first 2000 chars of response
        print("\nResponse Preview (first 2000 chars):")
        print("-"*50)
        print(response[:2000])
        if len(response) > 2000:
            print(f"\n... [{len(response) - 2000} more characters]")
    
    # Check for generated images
    if 'images' in result and result['images']:
        print(f"\nGenerated Images: {len(result['images'])}")
        for i, img in enumerate(result['images'][:5]):
            print(f"   Image {i+1}: {img.get('description', 'No description')[:50]}...")
    
    # Check workflow metadata
    if 'metadata' in result:
        meta = result['metadata']
        print(f"\nWorkflow Metadata:")
        print(f"   Steps completed: {meta.get('steps_completed', 'N/A')}")
        print(f"   Revision count: {meta.get('revision_count', 0)}")
        print(f"   Total time: {meta.get('total_time', 'N/A')}")
    
    # Save full result to file
    output_file = Path(__file__).parent / "test_output.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\nFull result saved to: {output_file}")
    
    # Save response as markdown
    if 'response' in result:
        md_file = Path(__file__).parent / "test_output.md"
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(result['response'])
        print(f"Response saved to: {md_file}")


def check_logs():
    """Check the logs directory for output"""
    print("\n" + "="*60)
    print("Checking Log Files...")
    print("="*60)
    
    logs_dir = Path(__file__).parent / "backend" / "outputs"
    
    if not logs_dir.exists():
        print(f"[WARN] Outputs directory not found. Will be created on first API call.")
        return
    
    # Find most recent run
    runs_dir = logs_dir / "runs"
    if not runs_dir.exists():
        print("[WARN] No runs directory found yet.")
        return
    
    sessions = sorted(runs_dir.iterdir(), reverse=True)
    
    if not sessions:
        print("[WARN] No log sessions found yet.")
        return
    
    latest_session = sessions[0]
    print(f"\nLatest session: {latest_session.name}")
    
    # Show directory structure
    print("\nEnterprise Directory Structure:")
    print("-"*60)
    
    subdirs_info = {
        "word_document": "Final .docx proposal",
        "image_assets": "Generated charts/graphs",
        "diagrams": "Mermaid SVG diagrams",
        "llm_interactions": "LLM API logs (JSON+MD)",
        "execution_logs": "Code execution logs",
        "metadata": "Analysis, plan, critique JSON",
        "code_snapshots": "Generated code evolution"
    }
    
    for subdir_name, description in subdirs_info.items():
        subdir = latest_session / subdir_name
        if subdir.exists():
            count = len(list(subdir.glob("*")))
            print(f"  {subdir_name}/")
            print(f"    Description: {description}")
            print(f"    Files: {count}")
        
    # Show manifest
    manifest_file = latest_session / "metadata" / "manifest.json"
    if manifest_file.exists():
        print(f"\nRun Manifest:")
        with open(manifest_file) as f:
            manifest = json.load(f)
            print(f"   Timestamp: {manifest.get('timestamp')}")
            print(f"   Has Plan: {manifest.get('has_plan')}")
            print(f"   Critique Count: {manifest.get('critique_count')}")


def main():
    print("\n" + "="*60)
    print("RFP BUILDER - End-to-End Test")
    print("="*60)
    print(f"API URL: {API_BASE_URL}")
    print(f"Examples: {EXAMPLES_DIR}")
    
    # Test 1: Health check
    if not test_health_check():
        print("\n[WARN] API not available. Please start the server first:")
        print("   cd backend && python -m uvicorn app.main:app --reload")
        return
    
    # Test 2: Run workflow
    result = test_rfp_workflow()
    
    # Test 3: Analyze result
    analyze_result(result)
    
    # Test 4: Check logs
    check_logs()
    
    print("\n" + "="*60)
    print("[OK] Test Complete!")
    print("="*60)
    print("\nNext steps:")
    print("1. Check backend/outputs/runs/{latest_run}/ for all artifacts")
    print("2. Open word_document/proposal.docx to view the generated proposal")
    print("3. Check metadata/manifest.json for run summary")
    print("4. Review llm_interactions/ for LLM request/response logs")


if __name__ == "__main__":
    main()
