// =============================================================
// src/rag/rag.controller.ts — HTTP Route Controller (Spec-Driven)
//
// SPEC-DRIVEN RULE:
//   Every route here MUST exist in spec/openapi.yaml (paths section).
//   Every route's request/response shape MUST match the spec schemas.
//
//   There are NO @ApiTags / @ApiOperation / @ApiResponse decorators here —
//   documentation lives in spec/openapi.yaml, not in the code.
//
// ROUTE → SPEC MAPPING:
//   GET  /          → paths./. get (operationId: getRoot)
//   GET  /health    → paths./health.get (operationId: getHealth)
//   POST /ask       → paths./ask.post (operationId: askQuestion)
//   DEL  /history   → paths./history.delete (operationId: clearHistory)
//   POST /data/index  → paths./data/index.post (operationId: indexData)
//   GET  /data/sheets → paths./data/sheets.get (operationId: listSheets)
//   POST /data/backup  → paths./data/backup.post (operationId: backupIndex)
//   POST /data/restore → paths./data/restore.post (operationId: restoreIndex)
// =============================================================

import { Controller, Get, Post, Delete, Body, HttpCode, HttpStatus } from '@nestjs/common';
import { RagService } from './rag.service';
import { AskQuestionDto } from './dto/ask-question.dto';
import { IndexDataDto } from './dto/index-data.dto';
import { SheetsService } from '../google/sheets.service';
import { VectorStoreService } from '../vector-store/vector-store.service';
import { EmbeddingsService } from '../embeddings/embeddings.service';
import type {
  RootResponse,
  HealthResponse,
  AskResponse,
  MessageResponse,
  IndexResponse,
  SheetsResponse,
  BackupResponse,
  RestoreResponse,
} from '../common/types';

@Controller()
export class RagController {
  constructor(
    private readonly ragService: RagService,
    private readonly sheetsService: SheetsService,
    private readonly vectorStoreService: VectorStoreService,
    private readonly embeddingsService: EmbeddingsService,
  ) {}

  // spec: paths./. get — operationId: getRoot
  @Get()
  root(): RootResponse {
    return {
      message: 'RAG System API is running!',
      docs: 'Visit /docs for the interactive API documentation',
      health: 'Visit /health for server status',
    };
  }

  // spec: paths./health.get — operationId: getHealth
  @Get('health')
  health(): HealthResponse {
    return {
      status: 'ok',
      indexSize: this.vectorStoreService.size,
      model: this.embeddingsService.getModelName(),
    };
  }

  // spec: paths./ask.post — operationId: askQuestion
  @Post('ask')
  @HttpCode(HttpStatus.OK)
  async ask(@Body() dto: AskQuestionDto): Promise<AskResponse> {
    return this.ragService.ask(dto);
  }

  // spec: paths./history.delete — operationId: clearHistory
  @Delete('history')
  clearHistory(): MessageResponse {
    this.ragService.clearHistory();
    return { message: 'Conversation history cleared.' };
  }

  // spec: paths./data/index.post — operationId: indexData
  @Post('data/index')
  @HttpCode(HttpStatus.OK)
  async index(@Body() dto: IndexDataDto): Promise<IndexResponse> {
    return this.ragService.indexData(dto);
  }

  // spec: paths./data/sheets.get — operationId: listSheets
  @Get('data/sheets')
  async listSheets(): Promise<SheetsResponse> {
    const sheetNames = await this.sheetsService.getSheetNames();
    return { sheetNames };
  }

  // spec: paths./data/backup.post — operationId: backupIndex
  @Post('data/backup')
  @HttpCode(HttpStatus.OK)
  async backup(): Promise<BackupResponse> {
    const driveFileId = await this.ragService.backupToDrive();
    return { message: 'Backup complete.', driveFileId };
  }

  // spec: paths./data/restore.post — operationId: restoreIndex
  @Post('data/restore')
  @HttpCode(HttpStatus.OK)
  async restore(): Promise<RestoreResponse> {
    const ok = await this.ragService.restoreFromDrive();
    return ok
      ? { message: 'Restore complete.', chunkCount: this.vectorStoreService.size }
      : { message: 'No backup found on Drive.' };
  }
}
