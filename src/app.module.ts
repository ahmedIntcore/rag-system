// =============================================================
// src/app.module.ts — Root Application Module
//
// WHAT IS A MODULE IN NESTJS?
//   A module is a class decorated with @Module().
//   It groups related Controllers and Services.
//   Every NestJS app has at least one module: the root AppModule.
//
//   Think of modules like folders that tell NestJS:
//   "these pieces of code belong together and work as a unit."
//
// MODULE GRAPH:
//   AppModule
//   └── RagModule
//       ├── RagController   (HTTP routes)
//       ├── RagService      (business logic)
//       ├── GoogleModule
//       │   ├── SheetsService
//       │   └── DriveService
//       ├── EmbeddingsService
//       └── VectorStoreService
// =============================================================

import { Module } from '@nestjs/common';
import { RagModule } from './rag/rag.module';

@Module({
  imports: [
    RagModule, // Import the RAG feature module
  ],
})
export class AppModule {}
