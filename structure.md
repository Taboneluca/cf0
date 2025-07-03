intelligent-spreadsheet-assistant/
├── frontend/               # Next.js frontend application (React + Tailwind)
│   ├── components/         # React components (Spreadsheet, Chat panel, etc.)
│   ├── pages/ or app/      # Next.js pages or app routes
│   ├── styles/             # Tailwind CSS config and global styles
│   └── README.md           # Guide for setting up/running the frontend
├── backend/                # Backend application (FastAPI server)
│   ├── agents/             # LLM agent definitions and logic for "Ask" and "Analyst" modes
│   ├── spreadsheet_engine/ # Spreadsheet data model and helper functions (read/write, apply formulas)
│   ├── chat/               # Chat management (conversation state, mode handling, routing to agent)
│   ├── utils/              # Utility modules (OpenAI API client, config, guardrails, etc.)
│   ├── main.py             # FastAPI app initialization and API endpoint definitions
│   └── README.md           # Guide for setting up/running the backend
└── README.md               # (Optional) high-level project README summarizing the project
