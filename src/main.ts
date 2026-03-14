// =============================================================
// src/main.ts — NestJS Application Entry Point
//
// WHAT IS NestJS?
//   NestJS is a Node.js framework built on top of Express.
//   It adds structure using TypeScript decorators and modules,
//   making large apps easier to organise and maintain.
//
//   Key ideas:
//   - Modules  → group related code together
//   - Controllers → handle HTTP requests (routes)
//   - Services    → business logic, injected automatically
//   - DTOs        → define the shape of request/response data
//
// HOW TO RUN:
//   npm run dev       ← development mode (auto-restart on save)
//   npm run build && npm start  ← production
//
// OPEN IN BROWSER:
//   http://localhost:3000/docs  ← Swagger interactive API docs
// =============================================================

import 'reflect-metadata'; // Required for NestJS decorators
import { NestFactory } from '@nestjs/core';
import { ValidationPipe } from '@nestjs/common';
import { SwaggerModule, DocumentBuilder } from '@nestjs/swagger';
import { AppModule } from './app.module';
import * as dotenv from 'dotenv';

// Load environment variables from .env before anything else
dotenv.config();

async function bootstrap() {
  // Create the NestJS application
  // NestJS wraps Express under the hood by default
  const app = await NestFactory.create(AppModule);

  // --- Global Validation Pipe ---
  // Automatically validates all incoming request bodies using class-validator.
  // If a required field is missing or has the wrong type, NestJS returns 400 Bad Request.
  // whitelist: strip unknown fields (only keep fields defined in the DTO)
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      transform: true,     // Automatically convert types (e.g. string "5" → number 5)
      forbidNonWhitelisted: false,
    }),
  );

  // --- CORS ---
  // Allow all origins in development (restrict in production)
  app.enableCors();

  // --- Swagger / OpenAPI Documentation ---
  // Swagger generates interactive API docs from our DTOs and decorators.
  // Visit /docs to see the full API documentation and test endpoints.
  const swaggerConfig = new DocumentBuilder()
    .setTitle('RAG System — Google Sheets & Drive Q&A')
    .setDescription(
      'A Retrieval-Augmented Generation (RAG) API built with NestJS.\n\n' +
      'Answers questions based on data from Google Sheets and Google Drive, ' +
      'powered by Claude AI.\n\n' +
      '**How it works:**\n' +
      '1. Data from Google Sheets/Drive is indexed at startup\n' +
      '2. Questions are matched to relevant data using vector similarity\n' +
      '3. Claude generates answers grounded in your data',
    )
    .setVersion('1.0')
    .addTag('RAG', 'Ask questions and manage conversation history')
    .addTag('Data', 'Index and manage data sources')
    .addTag('System', 'Health and status endpoints')
    .build();

  const document = SwaggerModule.createDocument(app, swaggerConfig);
  SwaggerModule.setup('docs', app, document); // Available at /docs

  const port = process.env.PORT || 3000;
  await app.listen(port);

  console.log(`\n✅ RAG System running!`);
  console.log(`   API:  http://localhost:${port}`);
  console.log(`   Docs: http://localhost:${port}/docs\n`);
}

bootstrap();
