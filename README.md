# AI Assistant Application

This project consists of a Next.js frontend and a FastAPI backend that communicate with each other.

## Project Structure

- `/frontend`: Next.js application
- `/backend`: FastAPI application

## Setup

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment (if not already created):
   ```bash
   python -m venv venv
   ```

3. Activate the virtual environment:
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Create a `.env` file in the backend directory with your OpenAI API key:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

6. Start the backend server:
   ```bash
   uvicorn main:app --reload
   ```

The backend server will run on http://localhost:8000.

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

The frontend will run on http://localhost:3000.

## API Endpoints

The backend provides the following endpoints:

- `GET /`: Welcome message
- `POST /api/chat`: General chat endpoint
- `POST /api/ask`: Chat endpoint with general assistant behavior
- `POST /api/analyst`: Chat endpoint with financial analyst behavior

## Environment Variables

### Frontend

- `NEXT_PUBLIC_API_URL`: URL of the backend API (default: http://localhost:8000)

### Backend

- `OPENAI_API_KEY`: Your OpenAI API key

## Production Deployment

For production deployment:

1. Update the CORS settings in the backend to only allow specific origins
2. Set the `NEXT_PUBLIC_API_URL` to your production backend URL
3. Deploy the backend and frontend to your preferred hosting providers 