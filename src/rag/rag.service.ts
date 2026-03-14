// =============================================================
// src/rag/rag.service.ts — RAG Business Logic Service
//
// This service orchestrates all the pieces:
//   Sheets + Drive → text chunks → embeddings → vector store → Claude
//
// WHY SEPARATE SERVICE FROM CONTROLLER?
//   The Controller handles HTTP (routes, request/response formatting).
//   The Service handles business logic (what actually happens).
//   This separation makes each part easier to test and understand.
//
// DEPENDENCY INJECTION:
//   NestJS injects SheetsService, DriveService, EmbeddingsService,
//   and VectorStoreService automatically via the constructor.
//   We don't need to call `new SheetsService()` ourselves.
// =============================================================

import { Injectable, OnModuleInit, Logger, ServiceUnavailableException } from '@nestjs/common';
import Anthropic from '@anthropic-ai/sdk';
import { SheetsService } from '../google/sheets.service';
import { DriveService } from '../google/drive.service';
import { EmbeddingsService } from '../embeddings/embeddings.service';
import { VectorStoreService, SearchResult } from '../vector-store/vector-store.service';
import { AskQuestionDto } from './dto/ask-question.dto';
import { IndexDataDto } from './dto/index-data.dto';
import type { AskResponse, IndexResponse } from '../common/types';

const CLAUDE_MODEL = 'claude-opus-4-6';
const CHUNK_SIZE = 800;
const CHUNK_OVERLAP = 100;

interface ConversationMessage {
  role: 'user' | 'assistant';
  content: string;
}

@Injectable()
export class RagService implements OnModuleInit {
  private readonly logger = new Logger(RagService.name);
  private claude: Anthropic;
  private conversationHistory: ConversationMessage[] = [];

  constructor(
    private readonly sheetsService: SheetsService,
    private readonly driveService: DriveService,
    private readonly embeddingsService: EmbeddingsService,
    private readonly vectorStoreService: VectorStoreService,
  ) {}

  async onModuleInit() {
    if (!process.env.ANTHROPIC_API_KEY) {
      this.logger.warn('ANTHROPIC_API_KEY not set — ask() will fail.');
      return;
    }

    this.claude = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

    // Auto-index on startup using saved index if available
    this.vectorStoreService.modelName = this.embeddingsService.getModelName();
    const loaded = this.vectorStoreService.loadFromDisk();
    if (loaded) {
      this.logger.log(`Startup: loaded ${this.vectorStoreService.size} chunks from disk.`);
    } else {
      this.logger.log('No saved index found. Call POST /data/index to build one.');
    }
  }

  // =============================================================
  // INDEXING
  // =============================================================

  /**
   * Builds (or rebuilds) the vector index from Google Sheets and/or Drive.
   */
  async indexData(dto: IndexDataDto): Promise<IndexResponse> {
    const {
      sheetName,
      driveFolderId,
      includeSheets = true,
      includeDrive = false,
      forceReindex = true,
    } = dto;

    if (!forceReindex && this.vectorStoreService.loadFromDisk()) {
      return {
        message: 'Loaded existing index from disk.',
        chunkCount: this.vectorStoreService.size,
      };
    }

    this.vectorStoreService.clear();
    const allChunks: { text: string; metadata: Record<string, any> }[] = [];

    // --- Sheets ---
    if (includeSheets) {
      try {
        const rows = await this.sheetsService.getRows(sheetName || null);
        this.logger.log(`Sheets: ${rows.length} rows loaded.`);
        for (const row of rows) {
          for (const chunk of this.chunkRow(row)) {
            allChunks.push({ text: chunk, metadata: { source: 'google_sheets', ...row } });
          }
        }
      } catch (err) {
        this.logger.error(`Sheets indexing failed: ${err.message}`);
      }
    }

    // --- Drive ---
    if (includeDrive) {
      try {
        const docs = await this.driveService.getAllDocuments(driveFolderId);
        this.logger.log(`Drive: ${docs.length} documents loaded.`);
        for (const doc of docs) {
          for (const chunk of this.chunkText(doc.text)) {
            allChunks.push({ text: chunk, metadata: doc.metadata });
          }
        }
      } catch (err) {
        this.logger.error(`Drive indexing failed: ${err.message}`);
      }
    }

    if (allChunks.length === 0) {
      return { message: 'No data found to index.', chunkCount: 0 };
    }

    this.logger.log(`Embedding ${allChunks.length} chunks...`);
    const texts = allChunks.map((c) => c.text);
    const embeddings = await this.embeddingsService.embedBatch(texts, (done, total) => {
      if (done % 20 === 0 || done === total) {
        this.logger.log(`Embedding progress: ${done}/${total}`);
      }
    });

    for (let i = 0; i < allChunks.length; i++) {
      this.vectorStoreService.add(allChunks[i].text, embeddings[i], allChunks[i].metadata);
    }

    this.vectorStoreService.saveToDisk();
    return {
      message: `Indexed ${allChunks.length} chunks successfully.`,
      chunkCount: this.vectorStoreService.size,
    };
  }

  // =============================================================
  // QUERYING
  // =============================================================

  /**
   * Answers a question using RAG: retrieve relevant chunks → send to Claude.
   */
  async ask(dto: AskQuestionDto): Promise<AskResponse> {
    if (this.vectorStoreService.size === 0) {
      throw new ServiceUnavailableException(
        'Index is empty. Call POST /data/index first to build the index.',
      );
    }

    const { question, topK = 5, rememberHistory = true, showSources = true } = dto;

    // 1. Embed the question
    const queryEmbedding = await this.embeddingsService.embed(question);

    // 2. Retrieve most relevant chunks
    const chunks: SearchResult[] = this.vectorStoreService.search(queryEmbedding, topK);

    // 3. Build context string
    const context = chunks
      .map((c, i) => `[Source ${i + 1}]\n${c.text}`)
      .join('\n\n---\n\n');

    // 4. System prompt
    const systemPrompt =
      `You are a helpful assistant that answers questions based ONLY on the provided data.\n\n` +
      `RULES:\n` +
      `- Answer using only the information in the provided context\n` +
      `- If the context lacks the information, say so clearly\n` +
      `- Be concise and accurate\n\n` +
      `CONTEXT:\n${context}`;

    // 5. Build messages for Claude
    const messages: ConversationMessage[] = rememberHistory
      ? [...this.conversationHistory, { role: 'user', content: question }]
      : [{ role: 'user', content: question }];

    // 6. Call Claude
    const response = await this.claude.messages.create({
      model: CLAUDE_MODEL,
      max_tokens: 1024,
      system: systemPrompt,
      messages,
    });

    const answer = (response.content[0] as any).text as string;

    // 7. Update history
    if (rememberHistory) {
      this.conversationHistory.push({ role: 'user', content: question });
      this.conversationHistory.push({ role: 'assistant', content: answer });
    }

    return {
      question,
      answer,
      sources: showSources
        ? chunks.map((c) => ({ text: c.text, score: c.score, metadata: c.metadata }))
        : [],
    };
  }

  clearHistory() {
    this.conversationHistory = [];
  }

  // =============================================================
  // DRIVE BACKUP
  // =============================================================

  async backupToDrive(): Promise<string> {
    const json = this.vectorStoreService.toJSON();
    return this.driveService.uploadFile('rag-index-backup.json', json);
  }

  async restoreFromDrive(): Promise<boolean> {
    const json = await this.driveService.downloadFile('rag-index-backup.json');
    if (!json) return false;
    this.vectorStoreService.fromJSON(json);
    this.logger.log(`Restored ${this.vectorStoreService.size} chunks from Drive.`);
    return true;
  }

  // =============================================================
  // HELPERS — Text Chunking
  // =============================================================

  private chunkRow(row: Record<string, string>): string[] {
    const text = Object.entries(row)
      .filter(([, v]) => v?.trim())
      .map(([k, v]) => `${k}: ${v}`)
      .join(' | ');

    return text.length ? this.chunkText(text) : [];
  }

  private chunkText(text: string): string[] {
    const chunks: string[] = [];
    let start = 0;

    while (start < text.length) {
      const end = Math.min(start + CHUNK_SIZE, text.length);
      const chunk = text.slice(start, end).trim();
      if (chunk.length > 20) chunks.push(chunk);
      start += CHUNK_SIZE - CHUNK_OVERLAP;
      if (text.length - start < 100) break;
    }

    return chunks;
  }
}
