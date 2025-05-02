# Backend (Intelligent Spreadsheet Assistant)

This directory contains the backend server for the Intelligent Spreadsheet Assistant, built with FastAPI (Python). The backend provides API endpoints for the frontend to:
- Send user queries/commands to the LLM agent.
- Retrieve responses and spreadsheet updates from the agent.
- Synchronize spreadsheet changes from the frontend.

It also houses the core logic for the LLM "Ask" and "Analyst" agents and the spreadsheet data model.

## Setup and Installation

1. **Create a Virtual Environment:** (Optional, but recommended)
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   ```

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   Create a file named `.env` in the backend directory and add your OpenAI API key:
   ```
   OPENAI_API_KEY=sk-...yourkey...
   OPENAI_MODEL=gpt-4o
   ```
   Do not commit this key to source control.

   Environment variables:
   - OPENAI_API_KEY (required): Your OpenAI API key
   - OPENAI_MODEL (optional): defaults to gpt-4o

4. **Run the Server:**
   ```bash
   uvicorn main:app --reload
   ```
   This starts the FastAPI server on http://127.0.0.1:8000. The `--reload` flag enables auto-restart on code changes.

5. **Test the API:**
   - Open http://localhost:8000/ in a browser to see if the API is running.
   - Go to http://localhost:8000/docs for interactive API documentation.

## Backend Structure

- **main.py**: Entry point of the FastAPI app. Sets up the app, includes CORS middleware, and defines the API routes.

- **spreadsheet_engine/**: Contains the spreadsheet data model and operations.
  - **model.py** - Defines the `Spreadsheet` class for storing and managing cell data.
  - **operations.py** - Implements functions for manipulating the spreadsheet (get/set cells, add rows/columns, etc.).

- **agents/**: (Coming soon) Will contain the LLM agent logic.
  - **ask_agent.py** - For handling analytical questions (read-only operations).
  - **analyst_agent.py** - For executing spreadsheet modifications.

- **chat/**: (Coming soon) Will handle the conversation flow and agent selection.
  - **router.py** - Routes user messages to the appropriate agent.

## API Endpoints

- **POST /chat**: Main interaction endpoint. Accepts a mode ("ask" or "analyst") and a user message.
- **POST /sheet/update**: Updates a specific cell in the spreadsheet.
- **POST /sheet/new**: Creates a new blank spreadsheet.

## Next Steps

- Implement agent logic with OpenAI API integration
- Add chat routing functionality
- Connect with the frontend 