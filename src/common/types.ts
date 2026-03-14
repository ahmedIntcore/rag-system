// =============================================================
// src/common/types.ts — TypeScript Types Derived from the Spec
//
// SPEC-DRIVEN RULE:
//   Every type here MUST match a schema defined in spec/openapi.yaml.
//   If you change the spec, update these types to match.
//   If you change these types, update the spec first.
//
// WHY SEPARATE TYPES FILE?
//   - Single place to update when the spec changes
//   - Used by both DTOs (validation) and services (business logic)
//   - Acts as a bridge between the YAML spec and TypeScript code
//
// NAMING CONVENTION:
//   Types mirror spec schema names exactly:
//     spec: AskRequest   → type: AskRequest
//     spec: AskResponse  → type: AskResponse
//     spec: SourceChunk  → type: SourceChunk
// =============================================================

// =============================================================
// REQUEST TYPES (match spec components/schemas/*Request)
// =============================================================

/** Matches spec: components/schemas/AskRequest */
export interface AskRequest {
  question: string;           // required, minLength:1, maxLength:2000
  rememberHistory?: boolean;  // default: true
  showSources?: boolean;      // default: true
  topK?: number;              // default: 5, min:1, max:20
}

/** Matches spec: components/schemas/IndexRequest */
export interface IndexRequest {
  sheetName?: string | null;    // null = first sheet
  driveFolderId?: string | null;
  includeSheets?: boolean;      // default: true
  includeDrive?: boolean;       // default: false
  forceReindex?: boolean;       // default: true
}

// =============================================================
// RESPONSE TYPES (match spec components/schemas/*Response)
// =============================================================

/** Matches spec: components/schemas/SourceChunk */
export interface SourceChunk {
  text: string;
  score: number;   // 0.0 – 1.0
  metadata: Record<string, unknown>;
}

/** Matches spec: components/schemas/AskResponse */
export interface AskResponse {
  question: string;
  answer: string;
  sources: SourceChunk[];
}

/** Matches spec: components/schemas/IndexResponse */
export interface IndexResponse {
  message: string;
  chunkCount: number;
}

/** Matches spec: components/schemas/HealthResponse */
export interface HealthResponse {
  status: 'ok' | 'degraded';
  indexSize: number;
  model: string;
}

/** Matches spec: components/schemas/SheetsResponse */
export interface SheetsResponse {
  sheetNames: string[];
}

/** Matches spec: components/schemas/BackupResponse */
export interface BackupResponse {
  message: string;
  driveFileId: string;
}

/** Matches spec: components/schemas/RestoreResponse */
export interface RestoreResponse {
  message: string;
  chunkCount?: number;
}

/** Matches spec: components/schemas/MessageResponse */
export interface MessageResponse {
  message: string;
}

/** Matches spec: components/schemas/RootResponse */
export interface RootResponse {
  message: string;
  docs: string;
  health: string;
}

/** Matches spec: components/schemas/ErrorResponse */
export interface ErrorResponse {
  statusCode: number;
  message: string;
  error?: string;
}
