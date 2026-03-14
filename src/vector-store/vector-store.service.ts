// =============================================================
// src/vector-store/vector-store.service.ts — Vector Store Service
//
// Stores text chunks + embeddings and enables cosine similarity search.
//
// WHAT IS A VECTOR STORE?
//   A database optimised for storing and searching vectors (arrays of numbers).
//   Given a query vector, it finds the most similar stored vectors.
//
// COSINE SIMILARITY:
//   Since all our embeddings are L2-normalised (length = 1),
//   cosine similarity = dot product = sum of element-wise multiplication.
//   Score range: 0.0 (unrelated) to 1.0 (identical meaning).
// =============================================================

import { Injectable, Logger } from '@nestjs/common';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import { dirname } from 'path';

const STORE_PATH = './data/vector_store/store.json';

export interface StoreItem {
  text: string;
  embedding: number[];
  metadata: Record<string, any>;
}

export interface SearchResult {
  text: string;
  score: number;
  metadata: Record<string, any>;
}

@Injectable()
export class VectorStoreService {
  private readonly logger = new Logger(VectorStoreService.name);
  private items: StoreItem[] = [];
  modelName = '';

  get size(): number {
    return this.items.length;
  }

  clear() {
    this.items = [];
  }

  add(text: string, embedding: number[], metadata: Record<string, any> = {}) {
    this.items.push({ text, embedding, metadata });
  }

  addMany(items: StoreItem[]) {
    this.items.push(...items);
  }

  /**
   * Finds the topK most similar chunks to a query embedding.
   */
  search(queryEmbedding: number[], topK = 5): SearchResult[] {
    if (this.items.length === 0) return [];

    return this.items
      .map((item) => ({
        text: item.text,
        metadata: item.metadata,
        score: dotProduct(queryEmbedding, item.embedding),
      }))
      .sort((a, b) => b.score - a.score)
      .slice(0, topK);
  }

  saveToDisk(path = STORE_PATH) {
    mkdirSync(dirname(path), { recursive: true });
    const data = {
      version: 1,
      modelName: this.modelName,
      savedAt: new Date().toISOString(),
      count: this.items.length,
      items: this.items,
    };
    writeFileSync(path, JSON.stringify(data), 'utf8');
    this.logger.log(`Saved ${this.items.length} chunks to ${path}`);
  }

  loadFromDisk(path = STORE_PATH): boolean {
    if (!existsSync(path)) return false;
    try {
      const data = JSON.parse(readFileSync(path, 'utf8'));
      this.items = data.items || [];
      this.modelName = data.modelName || '';
      this.logger.log(`Loaded ${this.items.length} chunks from ${path}`);
      return true;
    } catch (err) {
      this.logger.error(`Failed to load store: ${err.message}`);
      return false;
    }
  }

  toJSON(): string {
    return JSON.stringify({
      version: 1,
      modelName: this.modelName,
      savedAt: new Date().toISOString(),
      count: this.items.length,
      items: this.items,
    });
  }

  fromJSON(json: string) {
    const data = JSON.parse(json);
    this.items = data.items || [];
    this.modelName = data.modelName || '';
  }
}

/** Dot product of two equal-length vectors (cosine similarity for unit vectors). */
function dotProduct(a: number[], b: number[]): number {
  let sum = 0;
  for (let i = 0; i < a.length; i++) sum += a[i] * b[i];
  return sum;
}
