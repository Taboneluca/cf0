"""
Run script for the Intelligent Spreadsheet Assistant backend.
This is a convenience wrapper around uvicorn.
"""

import uvicorn

if __name__ == "__main__":
    print("Starting Intelligent Spreadsheet Assistant backend...")
    print("API will be available at http://localhost:8000")
    print("API documentation at http://localhost:8000/docs")
    print("Press Ctrl+C to stop the server")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    ) 