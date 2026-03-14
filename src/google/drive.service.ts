// =============================================================
// src/google/drive.service.ts — Google Drive Service
//
// Reads files from a Drive folder and makes them available
// as text documents for the RAG pipeline to index.
//
// Also supports backing up and restoring the vector store
// index to/from Google Drive.
// =============================================================

import { Injectable, OnModuleInit, Logger } from '@nestjs/common';
import { google, drive_v3 } from 'googleapis';
import { readFileSync } from 'fs';

// Google Workspace files must be exported to a standard format
const EXPORT_MIME: Record<string, string> = {
  'application/vnd.google-apps.document': 'text/plain',     // Google Docs
  'application/vnd.google-apps.spreadsheet': 'text/csv',    // Google Sheets
  'application/vnd.google-apps.presentation': 'text/plain', // Google Slides
};

const READABLE_MIME = new Set(['text/plain', 'text/markdown', 'text/csv', 'application/json']);

export interface DriveDocument {
  text: string;
  metadata: {
    source: 'google_drive';
    fileId: string;
    fileName: string;
    mimeType: string;
    modifiedTime: string;
  };
}

@Injectable()
export class DriveService implements OnModuleInit {
  private readonly logger = new Logger(DriveService.name);
  private driveApi: drive_v3.Drive;
  private folderId: string | null;

  async onModuleInit() {
    this.folderId = process.env.GOOGLE_DRIVE_FOLDER_ID || null;
    const auth = this.createAuth();
    this.driveApi = google.drive({ version: 'v3', auth });
    this.logger.log('Google Drive API initialized.');
  }

  /**
   * Lists all files in the configured Drive folder.
   */
  async listFiles(folderId?: string): Promise<drive_v3.Schema$File[]> {
    const folder = folderId || this.folderId;
    if (!folder) {
      throw new Error('No Drive folder ID. Set GOOGLE_DRIVE_FOLDER_ID in .env.');
    }

    const res = await this.driveApi.files.list({
      q: `'${folder}' in parents and trashed = false`,
      fields: 'files(id, name, mimeType, modifiedTime)',
      pageSize: 100,
      orderBy: 'modifiedTime desc',
    });

    return res.data.files || [];
  }

  /**
   * Reads all supported files from the Drive folder as plain text documents.
   */
  async getAllDocuments(folderId?: string): Promise<DriveDocument[]> {
    const files = await this.listFiles(folderId);
    this.logger.log(`Found ${files.length} files in Drive folder.`);

    const documents: DriveDocument[] = [];

    for (const file of files) {
      try {
        const content = await this.readFile(file);
        if (content?.trim()) {
          documents.push({
            text: content.trim(),
            metadata: {
              source: 'google_drive',
              fileId: file.id,
              fileName: file.name,
              mimeType: file.mimeType,
              modifiedTime: file.modifiedTime,
            },
          });
          this.logger.log(`Read: ${file.name}`);
        }
      } catch (err) {
        this.logger.error(`Failed to read ${file.name}: ${err.message}`);
      }
    }

    return documents;
  }

  /**
   * Uploads a string as a file to Google Drive (creates or updates).
   * Used to back up the vector store index.
   */
  async uploadFile(fileName: string, content: string, folderId?: string): Promise<string> {
    const folder = folderId || this.folderId;
    if (!folder) throw new Error('No Drive folder ID for upload.');

    const existingId = await this.findFile(fileName, folder);
    const media = { mimeType: 'application/json', body: content };

    if (existingId) {
      await this.driveApi.files.update({ fileId: existingId, media });
      this.logger.log(`Updated "${fileName}" in Drive.`);
      return existingId;
    }

    const res = await this.driveApi.files.create({
      requestBody: { name: fileName, parents: [folder] },
      media,
      fields: 'id',
    });
    this.logger.log(`Uploaded "${fileName}" to Drive.`);
    return res.data.id;
  }

  /**
   * Downloads a file from Drive by name. Returns null if not found.
   */
  async downloadFile(fileName: string, folderId?: string): Promise<string | null> {
    const folder = folderId || this.folderId;
    const fileId = await this.findFile(fileName, folder);
    if (!fileId) return null;

    const res = await this.driveApi.files.get(
      { fileId, alt: 'media' },
      { responseType: 'text' },
    );
    return res.data as string;
  }

  // --- Private helpers ---

  private async readFile(file: drive_v3.Schema$File): Promise<string | null> {
    if (EXPORT_MIME[file.mimeType]) {
      const res = await this.driveApi.files.export(
        { fileId: file.id, mimeType: EXPORT_MIME[file.mimeType] },
        { responseType: 'text' },
      );
      return res.data as string;
    }

    if (READABLE_MIME.has(file.mimeType)) {
      const res = await this.driveApi.files.get(
        { fileId: file.id, alt: 'media' },
        { responseType: 'text' },
      );
      return res.data as string;
    }

    this.logger.warn(`Unsupported MIME type: ${file.mimeType} (${file.name})`);
    return null;
  }

  private async findFile(fileName: string, folderId: string): Promise<string | null> {
    if (!folderId) return null;
    const res = await this.driveApi.files.list({
      q: `name = '${fileName}' and '${folderId}' in parents and trashed = false`,
      fields: 'files(id)',
      pageSize: 1,
    });
    return res.data.files?.[0]?.id || null;
  }

  private createAuth() {
    const path = process.env.GOOGLE_CREDENTIALS_PATH || 'credentials.json';
    let credentials: object;
    try {
      credentials = JSON.parse(readFileSync(path, 'utf8'));
    } catch (err) {
      throw new Error(`Cannot read credentials from "${path}": ${err.message}`);
    }
    return new google.auth.GoogleAuth({
      credentials,
      scopes: [
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/drive.file',
      ],
    });
  }
}
