// =============================================================
// src/google/google.module.ts — Google APIs Module
//
// Groups SheetsService and DriveService together.
// Exports them so other modules (like RagModule) can use them.
//
// WHAT IS "exports" IN A MODULE?
//   By default, a service defined in Module A is private to Module A.
//   To make it available to other modules that import Module A,
//   you must list it in the "exports" array.
// =============================================================

import { Module } from '@nestjs/common';
import { SheetsService } from './sheets.service';
import { DriveService } from './drive.service';

@Module({
  providers: [SheetsService, DriveService],
  exports: [SheetsService, DriveService], // Make available to importing modules
})
export class GoogleModule {}
