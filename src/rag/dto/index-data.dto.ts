// Implements spec: components/schemas/IndexRequest
// All fields are optional (spec has no "required" list for this schema).

import { IsBoolean, IsOptional, IsString } from 'class-validator';
import type { IndexRequest } from '../../common/types';

export class IndexDataDto implements IndexRequest {
  @IsString()
  @IsOptional()
  sheetName?: string | null; // spec: nullable: true

  @IsString()
  @IsOptional()
  driveFolderId?: string | null; // spec: nullable: true

  @IsBoolean()
  @IsOptional()
  includeSheets?: boolean = true; // spec: default: true

  @IsBoolean()
  @IsOptional()
  includeDrive?: boolean = false; // spec: default: false

  @IsBoolean()
  @IsOptional()
  forceReindex?: boolean = true; // spec: default: true
}
