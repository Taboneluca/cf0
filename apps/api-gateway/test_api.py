"""
Simple test script for the Intelligent Spreadsheet Assistant API.
Run this after starting the API server to test basic functionality.
"""

import requests
import json

# Base URL for the API (adjust if using a different port)
API_URL = "http://localhost:8000"

def test_root():
    """Test the root endpoint"""
    response = requests.get(f"{API_URL}/")
    assert response.status_code == 200
    print("Root endpoint working!")
    print(response.json())
    print()

def test_new_sheet():
    """Test creating a new sheet"""
    response = requests.post(
        f"{API_URL}/sheet/new",
        json={"rows": 5, "columns": 3}
    )
    assert response.status_code == 200
    print("Created new sheet:")
    print(json.dumps(response.json(), indent=2))
    print()

def test_update_cell():
    """Test updating a cell"""
    response = requests.post(
        f"{API_URL}/sheet/update",
        json={"cell": "A1", "value": "Test Value"}
    )
    assert response.status_code == 200
    print("Updated cell A1:")
    print(json.dumps(response.json(), indent=2))
    print()

def test_get_sheet():
    """Test getting the current sheet"""
    response = requests.get(f"{API_URL}/sheet")
    assert response.status_code == 200
    print("Current sheet state:")
    print(json.dumps(response.json(), indent=2))
    print()

def test_ask_mode():
    """Test the chat endpoint in Ask mode"""
    response = requests.post(
        f"{API_URL}/chat",
        json={
            "mode": "ask",
            "message": "What data is in this spreadsheet?"
        }
    )
    assert response.status_code == 200
    print("Ask mode response:")
    print(json.dumps(response.json(), indent=2))
    print()

def test_analyst_mode():
    """Test the chat endpoint in Analyst mode"""
    response = requests.post(
        f"{API_URL}/chat",
        json={
            "mode": "analyst",
            "message": "Add a new row"
        }
    )
    assert response.status_code == 200
    print("Analyst mode response:")
    print(json.dumps(response.json(), indent=2))
    print()

if __name__ == "__main__":
    try:
        print("Testing Intelligent Spreadsheet Assistant API...")
        test_root()
        test_new_sheet()
        test_update_cell()
        test_get_sheet()
        test_ask_mode()
        test_analyst_mode()
        print("All tests passed!")
    except Exception as e:
        print(f"Error: {str(e)}")
        print("Make sure the API server is running on http://localhost:8000") 