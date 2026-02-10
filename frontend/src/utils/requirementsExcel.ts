/**
 * Excel export/import utilities for RFP requirements.
 */

import * as XLSX from 'xlsx';
import type { RFPRequirement } from '../types';

const HEADERS = ['ID', 'Description', 'Category', 'Mandatory', 'Priority'];
const VALID_CATEGORIES = ['technical', 'management', 'cost', 'experience', 'compliance', 'other'] as const;
const VALID_PRIORITIES = ['high', 'medium', 'low'] as const;

/**
 * Export requirements to an Excel file and trigger download.
 */
export function exportRequirementsToExcel(requirements: RFPRequirement[], filename = 'rfp_requirements.xlsx') {
  const rows = requirements.map((req) => [
    req.id,
    req.description,
    req.category,
    req.is_mandatory ? 'Yes' : 'No',
    req.priority ?? 'medium',
  ]);

  const ws = XLSX.utils.aoa_to_sheet([HEADERS, ...rows]);

  // Set column widths
  ws['!cols'] = [
    { wch: 12 },  // ID
    { wch: 60 },  // Description
    { wch: 14 },  // Category
    { wch: 12 },  // Mandatory
    { wch: 10 },  // Priority
  ];

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Requirements');
  XLSX.writeFile(wb, filename);
}

/**
 * Fuzzy match a column name against known patterns.
 * Returns the canonical field name or null if no match.
 */
function matchColumn(header: string): 'id' | 'description' | 'category' | 'mandatory' | 'priority' | null {
  const h = header.toLowerCase().replace(/[^a-z0-9]/g, '');

  // ID patterns: "id", "req id", "requirement id", "#", "number", "reqid", "requirementid"
  if (
    h === 'id' ||
    h === 'reqid' ||
    h === 'requirementid' ||
    h === 'reqno' ||
    h === 'number' ||
    h === 'no' ||
    h === 'requirementnumber' ||
    h === 'sourcecode' ||
    h === 'sourceid' ||
    h === 'source' ||
    h === 'code' ||
    h === 'codeid'
  ) return 'id';

  // Description patterns
  if (h.includes('description') || h.includes('desc') || h === 'requirement' || h === 'text' || h === 'detail' || h === 'details' || h === 'requirementtext' || h === 'requirementdescription') return 'description';

  // Category patterns
  if (
    h.includes('category') ||
    h.includes('type') ||
    h === 'area' ||
    h === 'section' ||
    h === 'domain' ||
    h === 'function'
  ) return 'category';

  // Mandatory patterns
  if (h.includes('mandatory') || h.includes('required') || h === 'mustmeet' || h === 'musthave' || h === 'obligatory') return 'mandatory';

  // Priority patterns
  if (h.includes('priority') || h.includes('importance') || h === 'level' || h === 'criticality' || h === 'weight') return 'priority';

  return null;
}

export interface ImportResult {
  requirements: RFPRequirement[];
  filename: string;
  totalRows: number;
  mappedColumns: string[];
}

/**
 * Parse an Excel file and return requirements with metadata.
 * Flexibly matches column headers to handle various formats.
 */
export function importRequirementsFromExcel(file: File): Promise<ImportResult> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = new Uint8Array(e.target?.result as ArrayBuffer);
        const workbook = XLSX.read(data, { type: 'array' });
        const sheetName = (() => {
          let bestSheet = workbook.SheetNames[0] ?? '';
          let bestRowCount = -1;
          for (const name of workbook.SheetNames) {
            const sheet = workbook.Sheets[name];
            if (!sheet) continue;
            const matrix = XLSX.utils.sheet_to_json<Array<string | number | boolean>>(sheet, {
              header: 1,
              defval: '',
            });
            const nonEmptyRows = matrix.filter((row) =>
              row.some((cell) => String(cell ?? '').trim().length > 0)
            ).length;
            if (nonEmptyRows > bestRowCount) {
              bestRowCount = nonEmptyRows;
              bestSheet = name;
            }
          }
          return bestSheet;
        })();
        if (!sheetName) {
          reject(new Error('No sheets found in Excel file'));
          return;
        }
        const sheet = workbook.Sheets[sheetName];
        const matrix = XLSX.utils.sheet_to_json<Array<string | number | boolean>>(sheet, {
          header: 1,
          defval: '',
        });

        if (matrix.length === 0) {
          reject(new Error('Excel file is empty'));
          return;
        }

        const maxHeaderScan = Math.min(50, matrix.length);
        let headerRowIndex = 0;
        let bestScore = -1;
        for (let i = 0; i < maxHeaderScan; i += 1) {
          const row = matrix[i].map((cell) => String(cell).trim());
          const matched = row.map((cell) => matchColumn(cell)).filter(Boolean);
          const matchCount = matched.length;
          const uniqueMatches = new Set(matched).size;
          const nonEmptyCount = row.filter((cell) => cell.length > 0).length;
          const hasRequirementHeader = row.some((cell) => /requirement|description/i.test(cell));
          const hasIdHeader = row.some((cell) => /id|source\s*code|req/i.test(cell));
          const keywordBoost = (hasRequirementHeader ? 1 : 0) + (hasIdHeader ? 1 : 0);
          const score = uniqueMatches * 10 + keywordBoost * 5 + Math.min(nonEmptyCount, 10);
          const isCandidate = matchCount >= 2 || (matchCount === 1 && hasRequirementHeader);

          if (isCandidate && score > bestScore) {
            bestScore = score;
            headerRowIndex = i;
          }
        }

        let headerRow = matrix[headerRowIndex].map((cell) => String(cell).trim());
        if (headerRow.filter(Boolean).length === 0) {
          const fallbackIndex = matrix.findIndex((row) => row.some((cell) => String(cell ?? '').trim().length > 0));
          if (fallbackIndex >= 0) {
            headerRowIndex = fallbackIndex;
            headerRow = matrix[headerRowIndex].map((cell) => String(cell).trim());
          }
        }
        const dataRows = matrix.slice(headerRowIndex + 1);
        const rows = dataRows
          .filter((row) => row.some((cell) => String(cell ?? '').trim().length > 0))
          .map((row) => {
            const record: Record<string, string> = {};
            headerRow.forEach((header, idx) => {
              if (!header) return;
              record[header] = String(row[idx] ?? '').trim();
            });
            return record;
          });

        if (rows.length === 0) {
          reject(new Error('Excel file has no data rows'));
          return;
        }

        // Build a column mapping from the actual headers
        const actualHeaders = headerRow.filter(Boolean);
        const columnMap: Record<string, string> = {}; // canonical field -> actual header
        const mappedColumns: string[] = [];

        for (const header of actualHeaders) {
          const field = matchColumn(header);
          if (field && !columnMap[field]) {
            columnMap[field] = header;
            mappedColumns.push(`${header} -> ${field}`);
          }
        }

        // If no description column found, use the first text-heavy column
        if (!columnMap['description'] && actualHeaders.length > 0) {
          // Find the column with the longest average text
          let bestCol = actualHeaders[0];
          let bestLen = 0;
          for (const col of actualHeaders) {
            const avgLen = rows.reduce((sum, row) => sum + String(row[col] || '').length, 0) / rows.length;
            if (avgLen > bestLen) {
              bestLen = avgLen;
              bestCol = col;
            }
          }
          columnMap['description'] = bestCol;
          mappedColumns.push(`${bestCol} -> description (auto-detected)`);
        }

        const getValue = (row: Record<string, string>, field: string): string => {
          const header = columnMap[field];
          if (!header) return '';
          return String(row[header] ?? '').trim();
        };

        const requirements: RFPRequirement[] = rows.map((row, idx) => {
          const id = getValue(row, 'id') || `REQ-${String(idx + 1).padStart(3, '0')}`;
          const description = getValue(row, 'description');
          const categoryRaw = getValue(row, 'category').trim();
          const categoryLower = categoryRaw.toLowerCase();
          const category = VALID_CATEGORIES.includes(categoryLower as typeof VALID_CATEGORIES[number])
            ? categoryLower
            : categoryRaw || 'other';
          const mandatoryRaw = getValue(row, 'mandatory').toLowerCase();
          const is_mandatory = mandatoryRaw === 'yes' || mandatoryRaw === 'true' || mandatoryRaw === '1' || mandatoryRaw === 'y';
          const priorityRaw = getValue(row, 'priority').toLowerCase();
          const moSCoWMap: Record<string, RFPRequirement['priority']> = {
            musthave: 'high',
            shouldhave: 'medium',
            couldhave: 'low',
            must: 'high',
            should: 'medium',
            could: 'low',
          };
          const normalizedPriority = priorityRaw.replace(/[^a-z]/g, '');
          const mappedPriority = moSCoWMap[normalizedPriority];
          const priority = mappedPriority
            ?? (VALID_PRIORITIES.includes(priorityRaw as typeof VALID_PRIORITIES[number])
              ? (priorityRaw as RFPRequirement['priority'])
              : 'medium');

          return { id, description, category, is_mandatory, priority };
        });

        // Filter out rows with empty descriptions (likely blank rows)
        const filtered = requirements.filter(r => r.description.length > 0);

        resolve({
          requirements: filtered.length > 0 ? filtered : requirements,
          filename: file.name,
          totalRows: rows.length,
          mappedColumns,
        });
      } catch (err) {
        reject(new Error(`Failed to parse Excel file: ${err instanceof Error ? err.message : 'Unknown error'}`));
      }
    };
    reader.onerror = () => reject(new Error('Failed to read file'));
    reader.readAsArrayBuffer(file);
  });
}
