#!/usr/bin/env python3
"""
Test script to validate the LangServe integration end-to-end.
Tests the exact request format being sent by the frontend against the LangServeRequest schema.
Includes test cases for valid requests, requests with null values, requests with missing fields, 
and requests with wrong data types to identify the exact validation issues causing 422 errors.
"""

import asyncio
import json
import aiohttp
import sys
import os
from typing import Dict, Any, List

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.schemas import LangServeRequest, validate_langserve_payload, test_langserve_validation

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
TEST_TOKEN = os.getenv("TEST_TOKEN", "test-auth-token")

class LangServeIntegrationTester:
    """
    Comprehensive tester for LangServe integration
    """
    
    def __init__(self, base_url: str = BACKEND_URL):
        self.base_url = base_url.rstrip('/')
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def get_test_cases(self) -> List[Dict[str, Any]]:
        """
        Define comprehensive test cases covering various scenarios
        """
        return [
            {
                "name": "Valid ask request",
                "payload": {
                    "mode": "ask",
                    "message": "What is in cell A1?",
                    "wid": "test-workbook-123",
                    "sid": "Sheet1",
                    "contexts": ["This is a test context"],
                    "model": "gpt-4"
                },
                "should_pass": True
            },
            {
                "name": "Valid analyst request",
                "payload": {
                    "mode": "analyst",
                    "message": "Analyze the financial data",
                    "wid": "test-workbook-456",
                    "sid": "Financial",
                    "contexts": [],
                    "model": "gpt-4"
                },
                "should_pass": True
            },
            {
                "name": "Minimal valid request (defaults)",
                "payload": {
                    "mode": "ask",
                    "message": "Hello"
                },
                "should_pass": True
            },
            {
                "name": "Request with null contexts",
                "payload": {
                    "mode": "ask",
                    "message": "Test message",
                    "wid": "test-wid",
                    "sid": "Sheet1",
                    "contexts": None,
                    "model": "gpt-4"
                },
                "should_pass": False
            },
            {
                "name": "Request with undefined contexts",
                "payload": {
                    "mode": "ask",
                    "message": "Test message",
                    "wid": "test-wid",
                    "sid": "Sheet1",
                    "model": "gpt-4"
                },
                "should_pass": True  # contexts has default value
            },
            {
                "name": "Request with empty string message",
                "payload": {
                    "mode": "ask",
                    "message": "",
                    "wid": "test-wid",
                    "sid": "Sheet1",
                    "contexts": []
                },
                "should_pass": True
            },
            {
                "name": "Request with missing required field (message)",
                "payload": {
                    "mode": "ask",
                    "wid": "test-wid",
                    "sid": "Sheet1",
                    "contexts": []
                },
                "should_pass": False
            },
            {
                "name": "Request with wrong data type for contexts",
                "payload": {
                    "mode": "ask",
                    "message": "Test",
                    "contexts": "not-an-array",
                    "model": "gpt-4"
                },
                "should_pass": False
            },
            {
                "name": "Request with wrong data type for model",
                "payload": {
                    "mode": "ask",
                    "message": "Test",
                    "contexts": [],
                    "model": 123
                },
                "should_pass": False
            },
            {
                "name": "Request with mixed null and valid values",
                "payload": {
                    "mode": "ask",
                    "message": "Test message",
                    "wid": None,
                    "sid": "Sheet1",
                    "contexts": [],
                    "model": None
                },
                "should_pass": False  # wid is required, can't be None
            }
        ]
    
    async def test_schema_validation(self):
        """
        Test schema validation using Pydantic directly
        """
        print("\n" + "="*80)
        print("🧪 TESTING PYDANTIC SCHEMA VALIDATION")
        print("="*80)
        
        test_cases = self.get_test_cases()
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n🔬 Test {i}/{len(test_cases)}: {test_case['name']}")
            print(f"📄 Payload: {json.dumps(test_case['payload'], indent=2)}")
            
            result = validate_langserve_payload(test_case['payload'])
            
            if result['valid'] == test_case['should_pass']:
                if result['valid']:
                    print(f"✅ PASS: Request validated successfully")
                else:
                    print(f"✅ PASS: Request failed validation as expected")
                    print(f"   Errors: {result['errors']}")
            else:
                if result['valid']:
                    print(f"❌ FAIL: Request passed validation but was expected to fail")
                else:
                    print(f"❌ FAIL: Request failed validation but was expected to pass")
                    print(f"   Errors: {result['errors']}")
    
    async def test_http_endpoints(self):
        """
        Test actual HTTP endpoints to validate the complete request flow
        """
        print("\n" + "="*80)
        print("🌐 TESTING HTTP ENDPOINTS")
        print("="*80)
        
        endpoints = ["/ask/invoke", "/analyst/invoke", "/ask/stream", "/analyst/stream"]
        test_payload = {
            "mode": "ask",
            "message": "Test message for HTTP endpoint",
            "wid": "http-test-workbook",
            "sid": "Sheet1",
            "contexts": ["HTTP test context"],
            "model": "gpt-4"
        }
        
        for endpoint in endpoints:
            print(f"\n🔗 Testing endpoint: {endpoint}")
            url = f"{self.base_url}{endpoint}"
            
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {TEST_TOKEN}"
                }
                
                # For streaming endpoints, use different timeout
                timeout = aiohttp.ClientTimeout(total=10 if "stream" in endpoint else 5)
                
                async with self.session.post(
                    url, 
                    json=test_payload, 
                    headers=headers,
                    timeout=timeout
                ) as response:
                    print(f"   Status: {response.status}")
                    print(f"   Headers: {dict(response.headers)}")
                    
                    if response.status == 422:
                        error_data = await response.json()
                        print(f"   🚨 422 Validation Error Details:")
                        print(f"      {json.dumps(error_data, indent=6)}")
                    elif response.status == 200:
                        if "stream" in endpoint:
                            print(f"   ✅ Streaming endpoint accessible")
                            # Read first few chunks to verify streaming works
                            chunk_count = 0
                            async for chunk in response.content.iter_chunked(1024):
                                chunk_count += 1
                                if chunk_count <= 3:
                                    print(f"      Chunk {chunk_count}: {chunk[:100]}...")
                                if chunk_count >= 3:
                                    break
                        else:
                            data = await response.json()
                            print(f"   ✅ Response: {json.dumps(data, indent=6)[:200]}...")
                    else:
                        content = await response.text()
                        print(f"   ❌ Unexpected status. Content: {content[:200]}...")
                        
            except asyncio.TimeoutError:
                print(f"   ⏰ Timeout - endpoint may be working but slow")
            except Exception as e:
                print(f"   ❌ Error: {str(e)}")
    
    async def test_frontend_request_simulation(self):
        """
        Simulate exact requests that would come from the frontend
        """
        print("\n" + "="*80)
        print("🖥️  TESTING FRONTEND REQUEST SIMULATION")
        print("="*80)
        
        frontend_scenarios = [
            {
                "name": "Standard frontend ask request",
                "payload": {
                    "mode": "ask",
                    "message": "What is the sum of A1:A10?",
                    "wid": "frontend-test-wb",
                    "sid": "Sheet1",
                    "contexts": [],
                    "model": "gpt-4"
                }
            },
            {
                "name": "Frontend request with undefined model",
                "payload": {
                    "mode": "analyst",
                    "message": "Analyze this data",
                    "wid": "frontend-test-wb",
                    "sid": "Sheet1",
                    "contexts": ["Financial analysis context"]
                }
            },
            {
                "name": "Frontend request with empty contexts",
                "payload": {
                    "mode": "ask",
                    "message": "Help me",
                    "wid": "frontend-test-wb",
                    "sid": "Sheet1",
                    "contexts": []
                }
            }
        ]
        
        for scenario in frontend_scenarios:
            print(f"\n🎭 Scenario: {scenario['name']}")
            
            # First test schema validation
            print("   Schema validation:")
            result = validate_langserve_payload(scenario['payload'])
            if result['valid']:
                print(f"      ✅ Valid schema")
            else:
                print(f"      ❌ Invalid schema: {result['errors']}")
            
            # Then test via proxy endpoint (simulating frontend flow)
            print("   HTTP request via /ask/stream:")
            try:
                async with self.session.post(
                    f"{self.base_url}/ask/stream",
                    json=scenario['payload'],
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {TEST_TOKEN}"
                    },
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    print(f"      Status: {response.status}")
                    if response.status == 422:
                        error_data = await response.json()
                        print(f"      🚨 422 Error: {json.dumps(error_data, indent=8)}")
                    elif response.status == 200:
                        print(f"      ✅ Success - streaming response available")
                    else:
                        content = await response.text()
                        print(f"      ❌ Status {response.status}: {content[:100]}...")
            except Exception as e:
                print(f"      ❌ Request failed: {str(e)}")

async def main():
    """
    Main test runner
    """
    print("🚀 LangServe Integration Test Suite")
    print("="*80)
    
    # First run the schema validation tests
    print("\n📋 Running standalone schema validation tests...")
    test_langserve_validation()
    
    # Then run the integration tests
    async with LangServeIntegrationTester() as tester:
        await tester.test_schema_validation()
        await tester.test_frontend_request_simulation()
        
        # Only test HTTP endpoints if backend URL is available
        if BACKEND_URL != "http://localhost:8000" or os.getenv("TEST_LIVE_ENDPOINTS"):
            await tester.test_http_endpoints()
        else:
            print("\n⚠️  Skipping live HTTP endpoint tests. Set TEST_LIVE_ENDPOINTS=1 to enable.")
    
    print("\n" + "="*80)
    print("✅ LangServe Integration Test Suite Complete")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main()) 