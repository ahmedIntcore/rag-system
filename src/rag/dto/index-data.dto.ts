import { ApiPropertyOptional } from '@nestjs/swagger';
import { IsBoolean, IsOptional, IsString } from 'class-validator';

export class IndexDataDto {
  @ApiPropertyOptional({
    description: 'Google Sheets worksheet tab name. Leave empty for the first sheet.',
    example: 'Sheet1',
  })
  @IsString()
  @IsOptional()
  sheetName?: string;

  @ApiPropertyOptional({
    description: 'Google Drive folder ID to index documents from.',
    example: '1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms',
  })
  @IsString()
  @IsOptional()
  driveFolderId?: string;

  @ApiPropertyOptional({ description: 'Include Google Sheets data in the index', default: true })
  @IsBoolean()
  @IsOptional()
  includeSheets?: boolean = true;

  @ApiPropertyOptional({ description: 'Include Google Drive documents in the index', default: false })
  @IsBoolean()
  @IsOptional()
  includeDrive?: boolean = false;

  @ApiPropertyOptional({ description: 'Rebuild index from scratch even if a saved index exists', default: true })
  @IsBoolean()
  @IsOptional()
  forceReindex?: boolean = true;
}
