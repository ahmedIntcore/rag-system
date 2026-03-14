// =============================================================
// src/rag/rag.module.ts — RAG Feature Module
//
// This module wires everything together:
//   - Imports: other modules whose services we need
//   - Controllers: HTTP route handlers
//   - Providers: services available in this module
//
// NESTJS MODULE SYSTEM:
//   Think of modules like building blocks.
//   You import what you need and export what others can use.
//   NestJS reads the module tree and sets up dependency injection.
// =============================================================

import { Module } from '@nestjs/common';
import { RagController } from './rag.controller';
import { RagService } from './rag.service';
import { GoogleModule } from '../google/google.module';
import { EmbeddingsService } from '../embeddings/embeddings.service';
import { VectorStoreService } from '../vector-store/vector-store.service';

@Module({
  imports: [
    GoogleModule, // Provides SheetsService and DriveService
  ],
  controllers: [
    RagController, // Registers HTTP routes
  ],
  providers: [
    RagService,          // Core RAG orchestration
    EmbeddingsService,   // Text → vector embeddings
    VectorStoreService,  // Vector similarity search
  ],
})
export class RagModule {}
