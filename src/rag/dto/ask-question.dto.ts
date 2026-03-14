// =============================================================
// src/rag/dto/ask-question.dto.ts
//
// DTO = Data Transfer Object
// Implements the AskRequest schema from spec/openapi.yaml.
//
// SPEC-DRIVEN RULE:
//   Validation rules here MUST match the spec exactly:
//     spec: minLength: 1   → @MinLength(1)
//     spec: maxLength: 2000 → @MaxLength(2000)
//     spec: minimum: 1     → @Min(1)
//     spec: maximum: 20    → @Max(20)
//     spec: default: true  → = true
//
// NO @nestjs/swagger decorators here — docs come from the YAML spec,
// not from the code.
// =============================================================

import { IsString, IsBoolean, IsOptional, IsInt, MinLength, MaxLength, Min, Max } from 'class-validator';
import { Transform } from 'class-transformer';
import type { AskRequest } from '../../common/types';

// Implements spec: components/schemas/AskRequest
export class AskQuestionDto implements AskRequest {
  @IsString()
  @MinLength(1)   // spec: minLength: 1
  @MaxLength(2000) // spec: maxLength: 2000
  question: string;

  @IsBoolean()
  @IsOptional()
  rememberHistory?: boolean = true; // spec: default: true

  @IsBoolean()
  @IsOptional()
  showSources?: boolean = true; // spec: default: true

  @IsInt()
  @Min(1)   // spec: minimum: 1
  @Max(20)  // spec: maximum: 20
  @IsOptional()
  @Transform(({ value }) => parseInt(value, 10))
  topK?: number = 5; // spec: default: 5
}
