from typing import List, Dict, Any, Optional
from pydantic import BaseModel, ValidationError
import json

class ChatRequest(BaseModel):
    mode: str
    message: str
    wid: str
    sid: str
    contexts: Optional[List[str]] = []
    model: Optional[str] = None  # Provider:model_id format, e.g. "openai:gpt-4o-mini"

class ChatResponse(BaseModel):
    reply: str
    sheet: Dict[str, Any]
    log: List[Dict[str, Any]]

class LangServeRequest(BaseModel):
    mode: str
    message: str
    wid: str = "default"
    sid: str = "Sheet1"
    contexts: List[str] = []
    model: Optional[str] = None

def validate_langserve_payload(payload: dict) -> dict:
    """
    Temporary validation test function to help debug the LangServeRequest schema.
    Tests sample payloads against the LangServeRequest model and logs detailed validation results.
    """
    result = {
        "valid": False,
        "errors": [],
        "parsed_data": None,
        "raw_payload": payload
    }
    
    try:
        # Attempt to validate the payload
        validated_request = LangServeRequest(**payload)
        result["valid"] = True
        result["parsed_data"] = validated_request.model_dump()
        print(f"✅ LangServeRequest validation successful: {json.dumps(result['parsed_data'], indent=2)}")
    except ValidationError as e:
        result["errors"] = e.errors()
        print(f"❌ LangServeRequest validation failed:")
        print(f"📄 Raw payload: {json.dumps(payload, indent=2)}")
        print(f"💥 Validation errors: {json.dumps(result['errors'], indent=2)}")
        
        # Provide detailed error analysis
        for error in e.errors():
            field_path = " -> ".join(str(loc) for loc in error['loc'])
            print(f"🔍 Field '{field_path}': {error['msg']} (type: {error['type']})")
            if 'input' in error:
                print(f"   Input value: {error['input']} (type: {type(error['input'])})")
    except Exception as e:
        result["errors"] = [{"msg": str(e), "type": "unexpected_error"}]
        print(f"💥 Unexpected error during validation: {str(e)}")
    
    return result

def test_langserve_validation():
    """
    Test function with various payload scenarios to identify validation issues.
    """
    print("🧪 Running LangServe validation tests...")
    
    test_cases = [
        # Valid request
        {
            "name": "Valid request",
            "payload": {
                "mode": "ask",
                "message": "Hello",
                "wid": "test-workbook",
                "sid": "Sheet1",
                "contexts": [],
                "model": "gpt-4"
            }
        },
        # Request with null values
        {
            "name": "Request with null contexts",
            "payload": {
                "mode": "ask",
                "message": "Hello",
                "wid": "test-workbook",
                "sid": "Sheet1",
                "contexts": None,
                "model": "gpt-4"
            }
        },
        # Request with missing optional fields
        {
            "name": "Request with missing optional fields",
            "payload": {
                "mode": "ask",
                "message": "Hello",
                "wid": "test-workbook",
                "sid": "Sheet1"
            }
        },
        # Request with wrong data types
        {
            "name": "Request with wrong data types",
            "payload": {
                "mode": "ask",
                "message": "Hello",
                "wid": "test-workbook",
                "sid": "Sheet1",
                "contexts": "not-an-array",
                "model": 123
            }
        }
    ]
    
    for test_case in test_cases:
        print(f"\n🔬 Testing: {test_case['name']}")
        validate_langserve_payload(test_case['payload'])
    
    print("\n✅ LangServe validation tests complete")

if __name__ == "__main__":
    test_langserve_validation() 