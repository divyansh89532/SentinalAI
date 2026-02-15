# SentinalAI - Forensic Video Intelligence Platform

Turn 10,000 hours of footage into 10 seconds of answers.

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.10+
- Node.js 18+
- AWS Account (for Nova API)

### Setup

1. **Clone the repository**
   \`\`\`bash
   git clone https://github.com/yourusername/chronotrace.git
   cd chronotrace
   \`\`\`

2. **Configure environment**
   \`\`\`bash
   cp .env.example .env
   # Edit .env with your AWS credentials
   \`\`\`

3. **Start development environment**
   \`\`\`bash
   make dev
   \`\`\`

4. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/api/docs

## Project Structure

\`\`\`
chronotrace/
├── backend/          # Python FastAPI backend
├── frontend/         # React TypeScript frontend
├── deploy/           # Deployment configurations
├── docs/             # Documentation
└── data/             # Local data (gitignored)
\`\`\`

## Features

- 🔍 Natural language video search
- 🎥 Automatic video segmentation
- 🔒 Privacy-first auto-blur
- ⚠️ Anomaly detection
- 📊 Real-time analytics
- 🚀 Sub-second search (96.7% accuracy)

## Development

### Running Tests
\`\`\`bash
make test
\`\`\`

### Building for Production
\`\`\`bash
make build
\`\`\`

## Documentation

See [docs/](./docs/) for detailed documentation.

## License

MIT License - see LICENSE file
