#!/usr/bin/env python3
"""
LangServe Debug Script

This script makes direct HTTP requests to test both the old format (direct payload) 
and new format (wrapped in input field) to verify that the wrapper format resolves 
the 422 errors.

Usage:
    python debug_langserve.py [backend_url]
    
Examples:
    python debug_langserve.py
    python debug_langserve.py http://localhost:8000
    BACKEND_URL=https://api.cf0.ai python debug_langserve.py
"""

import json
import sys
import os
import time
import requests
from typing import Dict, Any, Optional

def test_endpoint(url: str, payload: Dict[str, Any], headers: Dict[str, str], description: str) -> Dict[str, Any]:
    """Test a single endpoint with given payload"""
    print(f"\n🔗 {description}")
    print(f"   URL: {url}")
    print(f"   Payload: {json.dumps(payload, separators=(',', ':'))[:100]}...")
    
    result = {
        'description': description,
        'url': url,
        'payload_size': len(json.dumps(payload)),
        'success': False,
        'status_code': None,
        'response_time_ms': None,
        'error': None,
        'response_data': None
    }
    
    try:
        start_time = time.time()
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        end_time = time.time()
        
        result['status_code'] = response.status_code
        result['response_time_ms'] = round((end_time - start_time) * 1000, 2)
        
        if response.status_code == 200:
            result['success'] = True
            print(f"   ✅ SUCCESS - Status: {response.status_code} ({result['response_time_ms']}ms)")
            
            # Try to parse response
            try:
                if 'stream' in url:
                    # For streaming endpoints, just check if we get data
                    content = response.text[:200]
                    result['response_data'] = f"Stream response: {len(response.text)} chars"
                    print(f"   📊 Response: {len(response.text)} characters")
                    if content:
                        print(f"   📄 Sample: {content}...")
                else:
                    # For invoke endpoints, parse JSON
                    json_response = response.json()
                    result['response_data'] = json_response
                    print(f"   📊 Response keys: {list(json_response.keys())}")
                    if 'content' in json_response:
                        content_preview = json_response['content'][:100]
                        print(f"   📄 Content: {content_preview}...")
            except Exception as parse_error:
                print(f"   ⚠️  Could not parse response: {parse_error}")
                result['response_data'] = response.text[:200]
                
        elif response.status_code == 422:
            print(f"   ❌ VALIDATION ERROR - Status: {response.status_code} ({result['response_time_ms']}ms)")
            try:
                error_data = response.json()
                result['error'] = error_data
                print(f"   🔍 Error details: {json.dumps(error_data, indent=2)}")
                
                # Analyze validation errors
                if 'detail' in error_data and isinstance(error_data['detail'], list):
                    print(f"   📋 Validation errors ({len(error_data['detail'])}):")
                    for i, error in enumerate(error_data['detail'][:3]):  # Show first 3 errors
                        field_path = " → ".join(str(loc) for loc in error.get('loc', []))
                        print(f"     {i+1}. {field_path}: {error.get('msg', 'Unknown error')}")
                    if len(error_data['detail']) > 3:
                        print(f"     ... and {len(error_data['detail']) - 3} more errors")
                        
            except Exception as parse_error:
                print(f"   ⚠️  Could not parse error response: {parse_error}")
                result['error'] = response.text[:200]
                
        else:
            print(f"   ❌ HTTP ERROR - Status: {response.status_code} ({result['response_time_ms']}ms)")
            result['error'] = f"HTTP {response.status_code}: {response.text[:200]}"
            print(f"   📄 Response: {response.text[:200]}...")
            
    except requests.exceptions.Timeout:
        result['error'] = "Request timeout"
        print(f"   ⏰ TIMEOUT - Request took longer than 15 seconds")
        
    except requests.exceptions.ConnectionError:
        result['error'] = "Connection error" 
        print(f"   🚫 CONNECTION ERROR - Could not connect to server")
        
    except Exception as e:
        result['error'] = str(e)
        print(f"   💥 UNEXPECTED ERROR - {e}")
    
    return result

def main():
    # Get backend URL
    backend_url = sys.argv[1] if len(sys.argv) > 1 else os.getenv('BACKEND_URL', 'http://localhost:8000')
    
    print("🚀 LangServe Debug Script")
    print("=" * 60)
    print(f"🎯 Target backend: {backend_url}")
    
    # Test connection first
    try:
        health_response = requests.get(f"{backend_url}/health", timeout=5)
        if health_response.status_code == 200:
            print(f"✅ Backend is responding (health check passed)")
        else:
            print(f"⚠️  Backend responded with status {health_response.status_code}")
    except Exception as e:
        print(f"❌ Backend health check failed: {e}")
        print("   Continuing with tests anyway...")
    
    print("=" * 60)
    
    # Test payloads
    direct_payload = {
        "mode": "ask",
        "message": "Calculate 2+2 and put the result in cell A1",
        "wid": "debug-test-wb",
        "sid": "Sheet1",
        "contexts": ["This is a debug test"],
        "model": "gpt-4"
    }
    
    wrapped_payload = {
        "input": direct_payload
    }
    
    # Request headers
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'User-Agent': 'LangServe-Debug-Script/1.0'
    }
    
    # Test scenarios
    scenarios = [
        {
            "name": "Ask Invoke - Wrapped Format",
            "url": f"{backend_url}/ask/invoke",
            "payload": wrapped_payload,
            "expected": "✅ Should work with new wrapper format"
        },
        {
            "name": "Ask Invoke - Direct Format", 
            "url": f"{backend_url}/ask/invoke",
            "payload": direct_payload,
            "expected": "❓ May fail with 422 if wrapper required"
        },
        {
            "name": "Analyst Invoke - Wrapped Format",
            "url": f"{backend_url}/analyst/invoke", 
            "payload": wrapped_payload,
            "expected": "✅ Should work with new wrapper format"
        },
        {
            "name": "Analyst Invoke - Direct Format",
            "url": f"{backend_url}/analyst/invoke",
            "payload": direct_payload, 
            "expected": "❓ May fail with 422 if wrapper required"
        },
        {
            "name": "Ask Stream - Wrapped Format",
            "url": f"{backend_url}/ask/stream",
            "payload": wrapped_payload,
            "expected": "✅ Should work with new wrapper format"
        },
        {
            "name": "Ask Stream - Direct Format",
            "url": f"{backend_url}/ask/stream",
            "payload": direct_payload,
            "expected": "❓ May fail with 422 if wrapper required"
        }
    ]
    
    # Run tests
    results = []
    for scenario in scenarios:
        print(f"\n{'='*20} {scenario['name']} {'='*20}")
        print(f"💭 Expected: {scenario['expected']}")
        
        result = test_endpoint(
            url=scenario['url'],
            payload=scenario['payload'], 
            headers=headers,
            description=scenario['name']
        )
        results.append(result)
        
        # Add a small delay between requests
        time.sleep(0.5)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY") 
    print("=" * 60)
    
    success_count = sum(1 for r in results if r['success'])
    total_count = len(results)
    
    print(f"✅ Successful tests: {success_count}/{total_count}")
    print(f"❌ Failed tests: {total_count - success_count}/{total_count}")
    
    # Analyze patterns
    wrapped_results = [r for r in results if 'Wrapped' in r['description']]
    direct_results = [r for r in results if 'Direct' in r['description']]
    
    wrapped_success = sum(1 for r in wrapped_results if r['success'])
    direct_success = sum(1 for r in direct_results if r['success'])
    
    print(f"\n📦 Wrapped format success rate: {wrapped_success}/{len(wrapped_results)}")
    print(f"📝 Direct format success rate: {direct_success}/{len(direct_results)}")
    
    if wrapped_success > direct_success:
        print(f"\n🎉 CONCLUSION: Wrapped format performs better!")
        print(f"   The LangServe input wrapper fix is working correctly.")
    elif direct_success > wrapped_success:
        print(f"\n🤔 UNEXPECTED: Direct format performs better")
        print(f"   This suggests the wrapper may not be necessary or working as expected.")
    else:
        print(f"\n⚖️  MIXED RESULTS: Both formats have similar success rates")
        print(f"   Further investigation may be needed.")
    
    # Show failed tests details
    failed_tests = [r for r in results if not r['success']]
    if failed_tests:
        print(f"\n❌ FAILED TESTS DETAILS:")
        for failed in failed_tests:
            print(f"   🔸 {failed['description']}")
            print(f"     Status: {failed.get('status_code', 'Unknown')}")
            print(f"     Error: {str(failed.get('error', 'Unknown'))[:100]}...")
    
    # Generate curl commands for manual testing
    print(f"\n" + "=" * 60)
    print("🔧 MANUAL TESTING COMMANDS")
    print("=" * 60)
    
    print("💡 Test wrapped format (recommended):")
    print(f"""
curl -X POST "{backend_url}/ask/invoke" \\
  -H "Content-Type: application/json" \\
  -d '{json.dumps(wrapped_payload, separators=(',', ':'))}'
""")
    
    print("💡 Test direct format (for comparison):")
    print(f"""
curl -X POST "{backend_url}/ask/invoke" \\
  -H "Content-Type: application/json" \\
  -d '{json.dumps(direct_payload, separators=(',', ':'))}'
""")
    
    print("💡 Test streaming endpoint:")
    print(f"""
curl -X POST "{backend_url}/ask/stream" \\
  -H "Content-Type: application/json" \\
  -d '{json.dumps(wrapped_payload, separators=(',', ':'))}'
""")
    
    print(f"\n✅ Debug script complete!")
    
    # Exit with appropriate code
    if success_count == total_count:
        print("🎉 All tests passed!")
        sys.exit(0)
    elif success_count > 0:
        print("⚠️  Some tests failed - check output above")
        sys.exit(1)
    else:
        print("💥 All tests failed - there may be a serious issue")
        sys.exit(2)

if __name__ == "__main__":
    main() 