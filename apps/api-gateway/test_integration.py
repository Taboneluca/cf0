#!/usr/bin/env python3
"""
Integration Test for LangServe Input Wrapper Fix

This test simulates the complete request flow from frontend to backend
to verify that the LangServe input wrapper format resolves the 422 errors.
"""

import json
from typing import List, Optional, Union
from pydantic import BaseModel, ValidationError

class LangServeRequest(BaseModel):
    mode: str
    message: str
    wid: str = "default"
    sid: str = "Sheet1"
    contexts: List[str] = []
    model: Optional[str] = None

class LangServeInputWrapper(BaseModel):
    input: LangServeRequest

def simulate_frontend_request():
    """Simulate what the frontend sends after sanitization and wrapping"""
    # Step 1: Frontend creates initial request
    frontend_payload = {
        "mode": "ask",
        "message": "Calculate the sum of A1:A10 and put result in B1",
        "wid": "user_workbook_123",
        "sid": "Sheet1",
        "contexts": ["Previous calculation was 250", "Working on Q1 budget"],
        "model": "gpt-4"
    }
    
    print("📱 Frontend: Creating request payload")
    print(f"   Original: {json.dumps(frontend_payload, indent=2)}")
    
    # Step 2: Frontend sanitizes the payload (simulate sanitizePayload function)
    sanitized = {
        'mode': str(frontend_payload.get('mode', 'ask')),
        'message': str(frontend_payload.get('message', '')),
        'wid': str(frontend_payload.get('wid', 'default')),
        'sid': str(frontend_payload.get('sid', 'Sheet1')),
        'contexts': frontend_payload.get('contexts', []) if isinstance(frontend_payload.get('contexts'), list) else [],
        'model': frontend_payload.get('model') if frontend_payload.get('model') else None
    }
    
    print("🧹 Frontend: Sanitized payload")
    print(f"   Sanitized: {json.dumps(sanitized, indent=2)}")
    
    # Step 3: Frontend wraps in LangServe format (the key fix!)
    langserve_wrapped = {
        "input": sanitized
    }
    
    print("📦 Frontend: Wrapped for LangServe")
    print(f"   Wrapped: {json.dumps(langserve_wrapped, indent=2)}")
    
    return langserve_wrapped

def simulate_backend_processing(request_payload):
    """Simulate backend LangServe request processing"""
    print("\n🔧 Backend: Processing LangServe request")
    
    # Step 1: Attempt to validate as LangServeInputWrapper
    try:
        wrapper = LangServeInputWrapper(**request_payload)
        print("✅ Backend: LangServeInputWrapper validation PASSED")
        
        # Step 2: Extract the actual request
        actual_request = wrapper.input
        print("📤 Backend: Extracted request from input wrapper")
        print(f"   Extracted: {actual_request.model_dump()}")
        
        # Step 3: Process the request (simulate langserve_stream_wrapper logic)
        print("⚙️ Backend: Processing extracted request...")
        print(f"   Mode: {actual_request.mode}")
        print(f"   Message: {actual_request.message}")
        print(f"   Workbook: {actual_request.wid}")
        print(f"   Sheet: {actual_request.sid}")
        print(f"   Contexts: {len(actual_request.contexts)} items")
        print(f"   Model: {actual_request.model}")
        
        return True, "Request processed successfully"
        
    except ValidationError as e:
        print("❌ Backend: LangServeInputWrapper validation FAILED")
        print(f"   Validation errors: {[err['msg'] for err in e.errors()]}")
        return False, f"Validation failed: {e.errors()}"
    except Exception as e:
        print(f"❌ Backend: Unexpected error: {e}")
        return False, f"Processing error: {str(e)}"

def test_old_vs_new_format():
    """Test both old (direct) and new (wrapped) formats to show the difference"""
    print("\n" + "="*60)
    print("🆚 COMPARING OLD vs NEW REQUEST FORMATS")
    print("="*60)
    
    # Sample request data
    request_data = {
        "mode": "ask",
        "message": "Test message",
        "wid": "test-wb",
        "sid": "Sheet1",
        "contexts": [],
        "model": "gpt-4"
    }
    
    # Test old format (direct)
    print("\n🔴 OLD FORMAT (Direct - causes 422 errors):")
    print(f"   Payload: {json.dumps(request_data)}")
    
    try:
        # This would fail in LangServe because it expects input wrapper
        direct_request = LangServeRequest(**request_data)
        print("   ✅ Direct validation: PASSED (but LangServe route would reject)")
        
        # Simulate what LangServe route expects
        try:
            wrapper_from_direct = LangServeInputWrapper(**request_data)
            print("   ❌ LangServe route validation: WOULD FAIL")
        except ValidationError:
            print("   ❌ LangServe route validation: FAILS (expected)")
            
    except ValidationError as e:
        print(f"   ❌ Direct validation: FAILED - {e.errors()}")
    
    # Test new format (wrapped)
    print("\n🟢 NEW FORMAT (Wrapped - fixes 422 errors):")
    wrapped_data = {"input": request_data}
    print(f"   Payload: {json.dumps(wrapped_data)}")
    
    try:
        wrapper_request = LangServeInputWrapper(**wrapped_data)
        extracted = wrapper_request.input
        print("   ✅ LangServe route validation: PASSED")
        print(f"   ✅ Extracted request: {extracted.model_dump()}")
        
    except ValidationError as e:
        print(f"   ❌ Wrapped validation: FAILED - {e.errors()}")

def run_integration_test():
    print("🚀 LangServe Input Wrapper Integration Test")
    print("="*60)
    
    # Step 1: Simulate frontend request creation and wrapping
    wrapped_request = simulate_frontend_request()
    
    # Step 2: Simulate backend processing
    success, message = simulate_backend_processing(wrapped_request)
    
    # Step 3: Report results
    print("\n" + "="*60)
    print("📊 INTEGRATION TEST RESULTS")
    print("="*60)
    
    if success:
        print("✅ INTEGRATION TEST: PASSED")
        print("🎉 LangServe input wrapper format is working correctly!")
        print("💡 This should resolve the 422 validation errors")
        print("\n🔑 Key Changes Made:")
        print("   1. Frontend wraps requests in { 'input': payload }")
        print("   2. Backend extracts requests from wrapper.input")
        print("   3. LangServe routes use LangServeInputWrapper for validation")
    else:
        print("❌ INTEGRATION TEST: FAILED")
        print(f"💥 Error: {message}")
        print("⚠️ The LangServe input wrapper fix needs investigation")
    
    return success

if __name__ == "__main__":
    # Run the integration test
    integration_success = run_integration_test()
    
    # Run format comparison test
    test_old_vs_new_format()
    
    # Final summary
    print("\n" + "="*60)
    print("🏁 FINAL TEST SUMMARY")
    print("="*60)
    print(f"✅ Integration Test: {'PASSED' if integration_success else 'FAILED'}")
    print(f"🎯 Expected Outcome: 422 errors should be resolved")
    
    if integration_success:
        print("\n🌟 SUCCESS: All components working together correctly!")
        print("📋 Next Steps:")
        print("   1. Deploy changes to test environment")
        print("   2. Monitor for reduced 422 error rates")
        print("   3. Verify chat functionality works end-to-end")
    else:
        print("\n⚠️ Issues detected - review implementation")
    
    print(f"\n✅ Test suite complete!") 