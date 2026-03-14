// =============================================================
// src/embeddings/embeddings.service.ts — Embedding Service
//
// Converts text into number vectors using @xenova/transformers.
// The model runs locally in Node.js — no external API needed.
//
// MODEL: Xenova/all-MiniLM-L6-v2
//   - ~90 MB download (cached after first run)
//   - Produces 384-dimensional vectors
//   - Good quality for English text similarity
// =============================================================

import { Injectable, OnModuleInit, Logger } from '@nestjs/common';

const MODEL_NAME = 'Xenova/all-MiniLM-L6-v2';

@Injectable()
export class EmbeddingsService implements OnModuleInit {
  private readonly logger = new Logger(EmbeddingsService.name);
  private pipe: any = null; // The transformers pipeline (loaded lazily)

  async onModuleInit() {
    // Pre-load the model when the server starts so the first request
    // doesn't have to wait for it to download/initialize.
    this.logger.log(`Loading embedding model: ${MODEL_NAME}...`);
    await this.getPipeline();
    this.logger.log('Embedding model ready.');
  }

  /**
   * Converts a single text string to an embedding vector.
   * @returns A 384-dimensional number array
   */
  async embed(text: string): Promise<number[]> {
    const pipe = await this.getPipeline();
    const output = await pipe(text, { pooling: 'mean', normalize: true });
    return Array.from(output.data) as number[];
  }

  /**
   * Converts multiple texts to embeddings (one by one).
   * @param onProgress Optional callback(done, total) for progress tracking
   */
  async embedBatch(texts: string[], onProgress?: (done: number, total: number) => void): Promise<number[][]> {
    const results: number[][] = [];
    for (let i = 0; i < texts.length; i++) {
      results.push(await this.embed(texts[i]));
      onProgress?.(i + 1, texts.length);
    }
    return results;
  }

  /** Returns the model name string (used in health checks). */
  getModelName(): string {
    return MODEL_NAME;
  }

  // --- Private ---

  private async getPipeline(): Promise<any> {
    if (!this.pipe) {
      // Dynamically import to allow @xenova/transformers to set cache dir first
      const { pipeline, env } = await import('@xenova/transformers');
      env.cacheDir = './data/models';
      this.pipe = await pipeline('feature-extraction', MODEL_NAME);
    }
    return this.pipe;
  }
}
