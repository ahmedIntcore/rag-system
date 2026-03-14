# RAG System — NestJS

A Retrieval-Augmented Generation (RAG) API built with **NestJS**, **Google Sheets**, **Google Drive**, and **Claude AI**.

## Project Structure

```
src/
├── main.ts                    ← App entry point, Swagger setup
├── app.module.ts              ← Root module
├── rag/
│   ├── rag.module.ts          ← Feature module (wires everything)
│   ├── rag.controller.ts      ← HTTP routes (7 endpoints)
│   ├── rag.service.ts         ← Business logic (RAG pipeline)
│   └── dto/
│       ├── ask-question.dto.ts ← Request/response shapes for /ask
│       └── index-data.dto.ts  ← Request shape for /data/index
├── google/
│   ├── google.module.ts       ← Google APIs module
│   ├── sheets.service.ts      ← Google Sheets reader
│   └── drive.service.ts       ← Google Drive reader + backup
├── embeddings/
│   └── embeddings.service.ts  ← Text → vector embeddings
└── vector-store/
    └── vector-store.service.ts ← Cosine similarity search
```

## Setup

### 1. Install dependencies
```bash
npm install
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Google Credentials
- Go to [Google Cloud Console](https://console.cloud.google.com)
- Create a Service Account and download the JSON key
- Enable **Google Sheets API** and **Google Drive API**
- Share your Sheet/Drive folder with the service account email
- Set `GOOGLE_CREDENTIALS_PATH=credentials.json` in `.env`

### 4. Run in development mode
```bash
npm run dev
```

Open **http://localhost:3000/docs** → interactive Swagger UI!

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Server status and index size |
| `POST` | `/ask` | Ask a question, get an AI answer |
| `DELETE` | `/history` | Clear conversation history |
| `POST` | `/data/index` | Build index from Sheets and/or Drive |
| `GET` | `/data/sheets` | List worksheet tab names |
| `POST` | `/data/backup` | Backup index to Google Drive |
| `POST` | `/data/restore` | Restore index from Drive backup |

## Example Usage

### Build the index
```bash
curl -X POST http://localhost:3000/data/index \
  -H "Content-Type: application/json" \
  -d '{"includeSheets": true, "forceReindex": true}'
```

### Ask a question
```bash
curl -X POST http://localhost:3000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What products are in the Electronics category?"}'
```

### Index Drive documents + Sheets together
```bash
curl -X POST http://localhost:3000/data/index \
  -H "Content-Type: application/json" \
  -d '{"includeSheets": true, "includeDrive": true, "forceReindex": true}'
```

### Backup index to Drive
```bash
curl -X POST http://localhost:3000/data/backup
```

## How NestJS Works

| Concept | Role |
|---------|------|
| **Module** | Groups related controllers + services |
| **Controller** | Handles HTTP requests → calls service → returns response |
| **Service** | Business logic, injected automatically by NestJS |
| **DTO** | Defines request/response shape + automatic validation |
| **Decorator** | `@Get()`, `@Post()`, `@Body()`, `@Injectable()` — metadata for NestJS |
