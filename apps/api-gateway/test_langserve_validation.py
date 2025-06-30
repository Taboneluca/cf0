#!/usr/bin/env python3
"""
LangServe Input Wrapper Validation Test Script

This script validates both direct request formats and the LangServe input wrapper format
to ensure the backend can handle the wrapped payloads that LangServe expects.

Usage:
    python test_langserve_validation.py
"""

import json
import sys
import os
import requests
from typing import Dict, Any, Optional
from api.schemas import validate_langserve_payload, LangServeRequest, LangServeInputWrapper

def test_pydantic_validation():
    """Test Pydantic validation for both direct and wrapper formats"""
    print("=" * 60)
    print("🧪 PYDANTIC VALIDATION TESTS")
    print("=" * 60)
    
    # Import and run the schema validation tests
    from api.schemas import test_langserve_validation
    test_langserve_validation()

def test_http_endpoints():
    """Test actual HTTP requests to LangServe endpoints"""
    print("\n" + "=" * 60)
    print("🌐 HTTP ENDPOINT TESTS")
    print("=" * 60)
    
    backend_url = os.getenv('BACKEND_URL', 'http://localhost:8000')
    
    # Test payloads
    direct_payload = {
        "mode": "ask",
        "message": "Test message",
        "wid": "test-workbook", 
        "sid": "Sheet1",
        "contexts": [],
        "model": "gpt-4"
    }
    
    wrapped_payload = {
        "input": direct_payload
    }
    
    # Test endpoints
    endpoints = ['/ask/invoke', '/analyst/invoke', '/ask/stream', '/analyst/stream']
    
    for endpoint in endpoints:
        print(f"\n🔗 Testing endpoint: {endpoint}")
        
        # Test wrapped format (expected to work)
        print(f"  📦 Testing wrapped format...")
        try:
            url = f"{backend_url}{endpoint}"
            headers = {'Content-Type': 'application/json'}
            
            if 'stream' in endpoint:
                response = requests.post(url, json=wrapped_payload, headers=headers, stream=True, timeout=10)
            else:
                response = requests.post(url, json=wrapped_payload, headers=headers, timeout=10)
            
            print(f"    Status: {response.status_code}")
            if response.status_code == 422:
                try:
                    error_detail = response.json()
                    print(f"    Validation error: {json.dumps(error_detail, indent=4)}")
                except:
                    print(f"    Error text: {response.text[:200]}...")
            elif response.status_code == 200:
                print(f"    ✅ Success!")
                if 'stream' not in endpoint:
                    try:
                        result = response.json()
                        print(f"    Response keys: {list(result.keys())}")
                    except:
                        print(f"    Response length: {len(response.text)} chars")
            else:
                print(f"    Unexpected status: {response.text[:200]}...")
                
        except requests.exceptions.RequestException as e:
            print(f"    ❌ Request failed: {e}")
        
        # Test direct format (may or may not work depending on current implementation)
        print(f"  📝 Testing direct format...")
        try:
            url = f"{backend_url}{endpoint}"
            headers = {'Content-Type': 'application/json'}
            
            if 'stream' in endpoint:
                response = requests.post(url, json=direct_payload, headers=headers, stream=True, timeout=10)
            else:
                response = requests.post(url, json=direct_payload, headers=headers, timeout=10)
            
            print(f"    Status: {response.status_code}")
            if response.status_code == 422:
                try:
                    error_detail = response.json()
                    print(f"    Validation error: {json.dumps(error_detail, indent=4)}")
                except:
                    print(f"    Error text: {response.text[:200]}...")
            elif response.status_code == 200:
                print(f"    ✅ Success!")
            else:
                print(f"    Unexpected status: {response.text[:200]}...")
                
        except requests.exceptions.RequestException as e:
            print(f"    ❌ Request failed: {e}")

def test_curl_examples():
    """Generate curl command examples for manual testing"""
    print("\n" + "=" * 60)
    print("🔧 CURL COMMAND EXAMPLES")
    print("=" * 60)
    
    backend_url = os.getenv('BACKEND_URL', 'http://localhost:8000')
    
    direct_payload = {
        "mode": "ask",
        "message": "Hello, test message",
        "wid": "test-workbook",
        "sid": "Sheet1", 
        "contexts": [],
        "model": "gpt-4"
    }
    
    wrapped_payload = {
        "input": direct_payload
    }
    
    print("💡 Test the wrapped format (should work):")
    print(f"""
curl -X POST "{backend_url}/ask/invoke" \\
  -H "Content-Type: application/json" \\
  -d '{json.dumps(wrapped_payload, indent=2)}'
""")
    
    print("💡 Test the direct format (may fail with 422):")
    print(f"""
curl -X POST "{backend_url}/ask/invoke" \\
  -H "Content-Type: application/json" \\
  -d '{json.dumps(direct_payload, indent=2)}'
""")
    
    print("💡 Test streaming endpoint:")
    print(f"""
curl -X POST "{backend_url}/ask/stream" \\
  -H "Content-Type: application/json" \\
  -d '{json.dumps(wrapped_payload, indent=2)}'
""")

def analyze_request_formats():
    """Analyze different request format scenarios"""
    print("\n" + "=" * 60) 
    print("🔍 REQUEST FORMAT ANALYSIS")
    print("=" * 60)
    
    scenarios = [
        {
            "name": "Frontend production request",
            "description": "Simulates the exact format sent by the frontend",
            "payload": {
                "input": {
                    "mode": "ask",
                    "message": "Calculate the sum of A1:A10",
                    "wid": "wb_123",
                    "sid": "Sheet1",
                    "contexts": ["Previous calculation: 100"],
                    "model": "gpt-4"
                }
            }
        },
        {
            "name": "Minimal wrapped request",
            "description": "Minimum required fields in wrapped format",
            "payload": {
                "input": {
                    "mode": "ask",
                    "message": "Hello",
                    "wid": "default",
                    "sid": "Sheet1",
                    "contexts": []
                }
            }
        },
        {
            "name": "Analyst mode request", 
            "description": "Request for analyst mode with contexts",
            "payload": {
                "input": {
                    "mode": "analyst",
                    "message": "Analyze the financial data trends",
                    "wid": "financial_wb",
                    "sid": "Analysis",
                    "contexts": ["Q1 revenue increased 15%", "Operating costs stable"],
                    "model": "gpt-4"
                }
            }
        },
        {
            "name": "Request with special characters",
            "description": "Test handling of special characters and unicode",
            "payload": {
                "input": {
                    "mode": "ask",
                    "message": "Calculate π × 2 and put in cell A1",
                    "wid": "test_🧮",
                    "sid": "Sheet1",
                    "contexts": ["Using special chars: α, β, γ"],
                }
            }
        }
    ]
    
    for scenario in scenarios:
        print(f"\n📋 {scenario['name']}")
        print(f"   {scenario['description']}")
        print(f"   Payload size: {len(json.dumps(scenario['payload']))} bytes")
        
        # Validate with Pydantic
        try:
            wrapper = LangServeInputWrapper(**scenario['payload'])
            print(f"   ✅ LangServeInputWrapper validation: PASSED")
            print(f"   📝 Extracted request: {wrapper.input.model_dump()}")
        except Exception as e:
            print(f"   ❌ LangServeInputWrapper validation: FAILED - {e}")
        
        print(f"   🔗 JSON structure: {json.dumps(scenario['payload'], separators=(',', ':'))[:100]}...")

def main():
    """Run all validation tests"""
    print("🚀 LangServe Input Wrapper Validation Test Suite")
    print("=" * 60)
    
    # Run Pydantic validation tests
    test_pydantic_validation()
    
    # Analyze request formats
    analyze_request_formats()
    
    # Generate curl examples
    test_curl_examples()
    
    # Test HTTP endpoints if backend is running
    try:
        backend_url = os.getenv('BACKEND_URL', 'http://localhost:8000')
        response = requests.get(f"{backend_url}/health", timeout=5)
        if response.status_code == 200:
            test_http_endpoints()
        else:
            print(f"\n⚠️  Backend not responding at {backend_url} (status: {response.status_code})")
            print("   Skipping HTTP endpoint tests")
    except requests.exceptions.RequestException:
        print(f"\n⚠️  Backend not accessible at {backend_url}")
        print("   Skipping HTTP endpoint tests")
        print("   💡 Start the backend with: python -m apps.api-gateway.main")
    
    print("\n✅ Validation test suite complete!")
    print("💡 Check the logs above for any validation issues")

if __name__ == "__main__":
    main() 