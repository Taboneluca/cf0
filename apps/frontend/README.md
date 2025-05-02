# CF0 Spreadsheet Application

A powerful spreadsheet application with built-in LLM capabilities.

## Features

- Spreadsheet interface with formula support
- AI-powered data analysis
- User authentication and waitlist system
- Workbook saving and sharing

## Tech Stack

- Next.js (App Router)
- Supabase (Authentication & Database)
- Tailwind CSS
- AI SDK with OpenAI integration

## Getting Started

### Prerequisites

- Node.js 18+ 
- npm or yarn
- Supabase account

### Installation

1. Clone the repository
   \`\`\`bash
   git clone https://github.com/yourusername/spreadsheet-llm.git
   cd spreadsheet-llm
   \`\`\`

2. Install dependencies
   \`\`\`bash
   npm install
   # or
   yarn
   \`\`\`

3. Copy the example environment file
   \`\`\`bash
   cp .env.example .env.local
   \`\`\`

4. Update the `.env.local` file with your Supabase credentials

5. Run the development server
   \`\`\`bash
   npm run dev
   # or
   yarn dev
   \`\`\`

6. Open [http://localhost:3000](http://localhost:3000) in your browser

## Database Setup

The application requires the following tables in your Supabase database:
- profiles
- workbooks
- waitlist

SQL setup scripts are available in the `database` directory.

## License

[MIT](LICENSE)
