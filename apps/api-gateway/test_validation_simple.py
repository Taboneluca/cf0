#!/usr/bin/env python3
"""
Simple LangServe Validation Test

Tests only the core Pydantic validation logic without requiring all dependencies.
"""

import json
from typing import List, Optional
from pydantic import BaseModel, ValidationError

class LangServeRequest(BaseModel):
    mode: str
    message: str
    wid: str = "default"
    sid: str = "Sheet1"
    contexts: List[str] = []
    model: Optional[str] = None

class LangServeInputWrapper(BaseModel):
    """
    LangServe-compatible request wrapper that handles the input field requirement.
    LangServe expects all parameters to be nested under an 'input' field.
    """
    input: LangServeRequest

def test_validation():
    print("🧪 Simple LangServe Validation Test")
    print("=" * 50)
    
    # Test cases
    test_cases = [
        {
            "name": "Direct Request Format",
            "payload": {
                "mode": "ask",
                "message": "Hello",
                "wid": "test-wb",
                "sid": "Sheet1",
                "contexts": [],
                "model": "gpt-4"
            },
            "test_direct": True,
            "test_wrapped": False
        },
        {
            "name": "Wrapped Request Format (LangServe)",
            "payload": {
                "input": {
                    "mode": "ask",
                    "message": "Hello",
                    "wid": "test-wb",
                    "sid": "Sheet1",
                    "contexts": [],
                    "model": "gpt-4"
                }
            },
            "test_direct": False,
            "test_wrapped": True
        },
        {
            "name": "Frontend Production Format",
            "payload": {
                "input": {
                    "mode": "ask",
                    "message": "Calculate sum of A1:A10",
                    "wid": "workbook_123",
                    "sid": "Sheet1",
                    "contexts": ["Previous calculation: 100"],
                    "model": "gpt-4"
                }
            },
            "test_direct": False,
            "test_wrapped": True
        },
        {
            "name": "Null Contexts (Should Fail)",
            "payload": {
                "mode": "ask",
                "message": "Hello",
                "wid": "test-wb",
                "sid": "Sheet1",
                "contexts": None,
                "model": "gpt-4"
            },
            "test_direct": True,
            "test_wrapped": False
        }
    ]
    
    success_count = 0
    total_tests = 0
    
    for test_case in test_cases:
        print(f"\n🔬 Testing: {test_case['name']}")
        print(f"   Payload: {json.dumps(test_case['payload'], separators=(',', ':'))[:80]}...")
        
        # Test direct format
        if test_case['test_direct']:
            total_tests += 1
            try:
                result = LangServeRequest(**test_case['payload'])
                print(f"   ✅ Direct format: VALID")
                print(f"      Parsed: {result.model_dump()}")
                success_count += 1
            except ValidationError as e:
                print(f"   ❌ Direct format: INVALID")
                print(f"      Errors: {[err['msg'] for err in e.errors()]}")
        
        # Test wrapped format  
        if test_case['test_wrapped']:
            total_tests += 1
            try:
                result = LangServeInputWrapper(**test_case['payload'])
                print(f"   ✅ Wrapped format: VALID")
                print(f"      Extracted: {result.input.model_dump()}")
                success_count += 1
            except ValidationError as e:
                print(f"   ❌ Wrapped format: INVALID")
                print(f"      Errors: {[err['msg'] for err in e.errors()]}")
    
    print(f"\n{'='*50}")
    print(f"📊 SUMMARY")
    print(f"{'='*50}")
    print(f"✅ Passed: {success_count}/{total_tests}")
    print(f"❌ Failed: {total_tests - success_count}/{total_tests}")
    
    if success_count == total_tests:
        print(f"🎉 All validation tests passed!")
        return True
    else:
        print(f"⚠️ Some tests failed")
        return False

def test_langserve_wrapper_extraction():
    """Test the key functionality: extracting requests from input wrapper"""
    print(f"\n🔄 Testing LangServe Input Wrapper Extraction")
    print("=" * 50)
    
    # Simulated frontend request (wrapped format)
    frontend_request = {
        "input": {
            "mode": "ask",
            "message": "Test extraction",
            "wid": "test-workbook",
            "sid": "Sheet1",
            "contexts": ["context1", "context2"],
            "model": "gpt-4"
        }
    }
    
    try:
        # Parse the wrapped request
        wrapper = LangServeInputWrapper(**frontend_request)
        extracted_request = wrapper.input
        
        print(f"✅ Successfully parsed wrapped request")
        print(f"📦 Original wrapper keys: {list(frontend_request.keys())}")
        print(f"📝 Extracted request: {extracted_request.model_dump()}")
        print(f"🔍 Request details:")
        print(f"   Mode: {extracted_request.mode}")
        print(f"   Message: {extracted_request.message[:50]}...")
        print(f"   Workbook: {extracted_request.wid}")
        print(f"   Sheet: {extracted_request.sid}")
        print(f"   Contexts: {len(extracted_request.contexts)} items")
        print(f"   Model: {extracted_request.model}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to extract request: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting Simple LangServe Validation Tests")
    
    # Run main validation tests
    validation_success = test_validation()
    
    # Test extraction functionality
    extraction_success = test_langserve_wrapper_extraction()
    
    print(f"\n🏁 FINAL RESULTS")
    print("=" * 50)
    print(f"✅ Validation Tests: {'PASSED' if validation_success else 'FAILED'}")
    print(f"✅ Extraction Tests: {'PASSED' if extraction_success else 'FAILED'}")
    
    if validation_success and extraction_success:
        print(f"🎉 All core functionality working correctly!")
        print(f"💡 The LangServe input wrapper fix should resolve 422 errors")
    else:
        print(f"⚠️ Some core functionality issues detected")
        
    print(f"\n✅ Test complete!") 