// =============================================================
// src/google/sheets.service.ts — Google Sheets Service
//
// WHAT IS @Injectable()?
//   This decorator marks the class as a NestJS "provider" (service).
//   NestJS manages its lifecycle and can inject it into other classes.
//   You never call `new SheetsService()` yourself — NestJS does it.
//
// DEPENDENCY INJECTION (DI):
//   Instead of creating dependencies yourself, you declare what you need
//   in the constructor and NestJS provides them automatically.
//   This makes code easier to test and maintain.
// =============================================================

import { Injectable, OnModuleInit, Logger } from '@nestjs/common';
import { google, sheets_v4 } from 'googleapis';
import { readFileSync } from 'fs';

@Injectable()
export class SheetsService implements OnModuleInit {
  // Logger is NestJS's built-in logging utility
  // Pass the class name so logs show where they came from
  private readonly logger = new Logger(SheetsService.name);
  private sheetsApi: sheets_v4.Sheets;
  private spreadsheetId: string;

  // OnModuleInit: NestJS calls onModuleInit() after the module is created.
  // Use it for setup that requires the DI container to be ready.
  async onModuleInit() {
    if (!process.env.GOOGLE_SHEET_ID) {
      this.logger.warn('GOOGLE_SHEET_ID not set — SheetsService will not work.');
      return;
    }

    this.spreadsheetId = process.env.GOOGLE_SHEET_ID;
    const auth = this.createAuth();
    this.sheetsApi = google.sheets({ version: 'v4', auth });
    this.logger.log('Google Sheets API initialized.');
  }

  /**
   * Returns the names of all worksheet tabs in the spreadsheet.
   */
  async getSheetNames(): Promise<string[]> {
    const res = await this.sheetsApi.spreadsheets.get({
      spreadsheetId: this.spreadsheetId,
      fields: 'sheets.properties.title',
    });
    return res.data.sheets.map((s) => s.properties.title);
  }

  /**
   * Reads all rows from a sheet tab and returns them as an array of objects.
   * First row = column headers.
   *
   * @param sheetName - Tab name, or null for the first sheet
   */
  async getRows(sheetName: string | null = null): Promise<Record<string, string>[]> {
    if (!sheetName) {
      const names = await this.getSheetNames();
      sheetName = names[0];
    }

    const res = await this.sheetsApi.spreadsheets.values.get({
      spreadsheetId: this.spreadsheetId,
      range: sheetName,
    });

    const rawRows = res.data.values || [];
    if (rawRows.length < 2) return [];

    const headers = rawRows[0] as string[];

    return rawRows.slice(1).map((row) => {
      const obj: Record<string, string> = {};
      headers.forEach((header, i) => {
        obj[header] = row[i] !== undefined ? String(row[i]) : '';
      });
      return obj;
    });
  }

  // --- Private helpers ---

  private createAuth() {
    const path = process.env.GOOGLE_CREDENTIALS_PATH || 'credentials.json';
    let credentials: object;
    try {
      credentials = JSON.parse(readFileSync(path, 'utf8'));
    } catch (err) {
      throw new Error(
        `Cannot read Google credentials from "${path}": ${err.message}\n` +
        `Set GOOGLE_CREDENTIALS_PATH in .env to point to your service account JSON file.`,
      );
    }
    return new google.auth.GoogleAuth({
      credentials,
      scopes: ['https://www.googleapis.com/auth/spreadsheets.readonly'],
    });
  }
}
