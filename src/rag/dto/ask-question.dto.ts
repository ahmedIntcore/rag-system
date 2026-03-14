// =============================================================
// src/rag/dto/ask-question.dto.ts — Ask Question DTO
//
// WHAT IS A DTO?
//   Data Transfer Object — a class that defines the expected shape
//   of data coming in (request body) or going out (response).
//
// HOW NESTJS USES DTOs:
//   1. class-validator decorators (@IsString, @IsBoolean...) validate input.
//      If validation fails → NestJS automatically returns 400 Bad Request.
//   2. @ApiProperty decorators tell Swagger what the field means.
//      This generates the interactive docs at /docs automatically.
// =============================================================

import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { IsString, IsBoolean, IsOptional, MinLength, MaxLength } from 'class-validator';

export class AskQuestionDto {
  @ApiProperty({
    description: 'The question to ask about the data',
    example: 'What products are available in the Electronics category?',
  })
  @IsString()
  @MinLength(1)
  @MaxLength(2000)
  question: string;

  @ApiPropertyOptional({
    description: 'If true, Claude remembers previous questions in this session',
    default: true,
  })
  @IsBoolean()
  @IsOptional()
  rememberHistory?: boolean = true;

  @ApiPropertyOptional({
    description: 'If true, include retrieved source chunks in the response',
    default: true,
  })
  @IsBoolean()
  @IsOptional()
  showSources?: boolean = true;

  @ApiPropertyOptional({
    description: 'Number of source chunks to retrieve (higher = more context, slower)',
    default: 5,
  })
  @IsOptional()
  topK?: number = 5;
}

export class SourceChunkDto {
  @ApiProperty({ description: 'The text content of this chunk' })
  text: string;

  @ApiProperty({ description: 'Similarity score: 0.0 (unrelated) to 1.0 (identical)' })
  score: number;

  @ApiProperty({ description: 'Original row/document data from the data source' })
  metadata: Record<string, any>;
}

export class AskResponseDto {
  @ApiProperty({ description: 'The original question' })
  question: string;

  @ApiProperty({ description: "Claude's answer based on the data" })
  answer: string;

  @ApiProperty({ type: [SourceChunkDto], description: 'Source chunks used as context' })
  sources: SourceChunkDto[];
}
