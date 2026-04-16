#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { chromium } = require('playwright');

const BASE_URL = 'https://www.fruugo.co.uk';
const DEFAULT_INPUT = 'fruugo_categories_0325.csv';
const DEFAULT_OUTPUT_DIR = 'fruugo_category_product_links_output';
const DEFAULT_PAGES = 5;
const DEFAULT_PAGE_SIZE = 128;
const DEFAULT_WAIT_MS = 4000;
const DEFAULT_TIMEOUT_MS = 60000;
const FETCH_HELPER_PATH = path.join(__dirname, 'fruugo_fetch_html.js');
const USER_AGENT =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ' +
  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36';

function parseArgs(argv) {
  const args = {
    input: DEFAULT_INPUT,
    outputDir: DEFAULT_OUTPUT_DIR,
    pages: DEFAULT_PAGES,
    pageSize: DEFAULT_PAGE_SIZE,
    waitMs: DEFAULT_WAIT_MS,
    limit: 0,
    startIndex: 1,
    endIndex: 0,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    const next = argv[index + 1];
    if (token === '--input' && next) {
      args.input = next;
      index += 1;
    } else if (token === '--output-dir' && next) {
      args.outputDir = next;
      index += 1;
    } else if (token === '--pages' && next) {
      args.pages = Number.parseInt(next, 10);
      index += 1;
    } else if (token === '--page-size' && next) {
      args.pageSize = Number.parseInt(next, 10);
      index += 1;
    } else if (token === '--wait-ms' && next) {
      args.waitMs = Number.parseInt(next, 10);
      index += 1;
    } else if (token === '--limit' && next) {
      args.limit = Number.parseInt(next, 10);
      index += 1;
    } else if (token === '--start-index' && next) {
      args.startIndex = Number.parseInt(next, 10);
      index += 1;
    } else if (token === '--end-index' && next) {
      args.endIndex = Number.parseInt(next, 10);
      index += 1;
    } else if (token === '--help' || token === '-h') {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`Unknown or incomplete argument: ${token}`);
    }
  }

  if (!Number.isInteger(args.pages) || args.pages <= 0) {
    throw new Error('--pages must be a positive integer');
  }
  if (!Number.isInteger(args.pageSize) || args.pageSize <= 0) {
    throw new Error('--page-size must be a positive integer');
  }
  if (!Number.isInteger(args.waitMs) || args.waitMs < 0) {
    throw new Error('--wait-ms must be a non-negative integer');
  }
  if (!Number.isInteger(args.limit) || args.limit < 0) {
    throw new Error('--limit must be a non-negative integer');
  }
  if (!Number.isInteger(args.startIndex) || args.startIndex <= 0) {
    throw new Error('--start-index must be a positive integer');
  }
  if (!Number.isInteger(args.endIndex) || args.endIndex < 0) {
    throw new Error('--end-index must be a non-negative integer');
  }
  if (args.endIndex > 0 && args.endIndex < args.startIndex) {
    throw new Error('--end-index must be greater than or equal to --start-index');
  }

  return args;
}

function printHelp() {
  console.log(`
Usage:
  node crawl_fruugo_category_product_links.js [options]

Options:
  --input <file>        Category CSV path. Default: ${DEFAULT_INPUT}
  --output-dir <dir>    Output directory. Default: ${DEFAULT_OUTPUT_DIR}
  --pages <n>           Pages per category. Default: ${DEFAULT_PAGES}
  --page-size <n>       Products per page. Default: ${DEFAULT_PAGE_SIZE}
  --wait-ms <n>         Extra wait after page load. Default: ${DEFAULT_WAIT_MS}
  --limit <n>           Only crawl the first n categories. Default: all
  --start-index <n>     Start from the nth category row (1-based). Default: 1
  --end-index <n>       End at the nth category row (1-based). Default: all
  --help, -h            Show this help

Example:
  node crawl_fruugo_category_product_links.js --input fruugo_categories_0325.csv --output-dir 0326/category_links
`.trim());
}

function slugify(value) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 120);
}

function csvEscape(value) {
  const text = String(value ?? '');
  if (/[",\n\r]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function parseCsvLine(line) {
  const values = [];
  let current = '';
  let inQuotes = false;

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    const next = line[index + 1];

    if (char === '"') {
      if (inQuotes && next === '"') {
        current += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === ',' && !inQuotes) {
      values.push(current);
      current = '';
    } else {
      current += char;
    }
  }

  values.push(current);
  return values;
}

function readCategoryCsv(filePath) {
  const raw = fs.readFileSync(filePath, 'utf8').replace(/^\uFEFF/, '');
  const lines = raw.split(/\r?\n/).filter((line) => line.trim());
  if (lines.length < 2) {
    throw new Error(`CSV has no data rows: ${filePath}`);
  }

  const headers = parseCsvLine(lines[0]).map((value) => value.trim());
  const nameIndex = headers.findIndex((value) => value.toLowerCase() === 'category name');
  const urlIndex = headers.findIndex((value) => value.toLowerCase() === 'url');
  const levelIndex = headers.findIndex((value) => value.toLowerCase() === 'level');

  if (nameIndex === -1 || urlIndex === -1 || levelIndex === -1) {
    throw new Error(`CSV must include Category Name, URL, Level headers: ${filePath}`);
  }

  return lines.slice(1).map((line, rowOffset) => {
    const parts = parseCsvLine(line);
    if (parts.length < 3) {
      throw new Error(`Invalid CSV row ${rowOffset + 2}: ${line}`);
    }
    return {
      categoryName: (parts[nameIndex] || '').trim(),
      url: (parts[urlIndex] || '').trim(),
      level: (parts[levelIndex] || '').trim(),
    };
  }).filter((row) => row.categoryName && row.url);
}

function buildCategoryPageUrl(categoryUrl, pageNumber, pageSize) {
  const url = new URL(categoryUrl);
  url.searchParams.set('pageSize', String(pageSize));
  url.searchParams.set('sorting', 'bestsellingdesc');
  if (pageNumber > 1) {
    url.searchParams.set('page', String(pageNumber));
  } else {
    url.searchParams.delete('page');
  }
  return url.toString();
}

function extractProductLinks(html) {
  const regex = /href=["'](?<url>\/[^"'<>]+\/p-\d+(?:-\d+)?(?:\?[^"']*)?)["']/gi;
  const links = [];
  const seen = new Set();

  for (const match of html.matchAll(regex)) {
    const absoluteUrl = new URL(match.groups.url, BASE_URL).toString();
    if (seen.has(absoluteUrl)) {
      continue;
    }
    seen.add(absoluteUrl);
    links.push(absoluteUrl);
  }

  return links;
}

async function launchBrowser() {
  try {
    return await chromium.launch({ headless: true, channel: 'chrome' });
  } catch (error) {
    return chromium.launch({ headless: true });
  }
}

async function fetchHtml(context, url, waitMs) {
  if (fs.existsSync(FETCH_HELPER_PATH)) {
    let lastError = null;
    for (let attempt = 1; attempt <= 4; attempt += 1) {
      try {
        return execFileSync('node', [FETCH_HELPER_PATH, url, String(waitMs)], {
          encoding: 'utf8',
          maxBuffer: 50 * 1024 * 1024,
          timeout: 120000,
        });
      } catch (error) {
        lastError = error;
        if (attempt < 4) {
          console.error(`Helper fetch failed (${attempt}/4): ${url}`);
          await new Promise((resolve) => setTimeout(resolve, attempt * 1000));
        }
      }
    }
    throw lastError;
  }

  let lastError = null;

  for (let attempt = 1; attempt <= 2; attempt += 1) {
    const page = await context.newPage();
    page.setDefaultTimeout(DEFAULT_TIMEOUT_MS);
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: DEFAULT_TIMEOUT_MS });
      if (waitMs > 0) {
        await page.waitForTimeout(waitMs);
      }
      const html = await page.content();
      await page.close();
      return html;
    } catch (error) {
      lastError = error;
      console.error(`Fetch failed (${attempt}/2): ${url}`);
      await page.close().catch(() => {});
    }
  }

  throw lastError;
}

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function writeLines(filePath, lines) {
  const content = lines.length ? `${lines.join('\n')}\n` : '';
  fs.writeFileSync(filePath, content, 'utf8');
}

function buildCombinedCsvLines(combinedRows) {
  return [
    'Category Name,Category URL,Level,Page,Rank In Page,Product URL',
    ...combinedRows.map((row) => [
      row.categoryName,
      row.categoryUrl,
      row.level,
      row.pageNumber,
      row.rankInPage,
      row.productUrl,
    ].map(csvEscape).join(',')),
  ];
}

function buildSummaryCsvLines(summaryRows, pages) {
  const summaryPageHeaders = Array.from(
    { length: pages },
    (_, index) => `Page ${index + 1} Count`,
  );
  const summaryErrorHeaders = Array.from(
    { length: pages },
    (_, index) => `Page ${index + 1} Error`,
  );

  return [
    [
      'Category Name',
      'Category URL',
      'Level',
      'Unique Product Links',
      ...summaryPageHeaders,
      ...summaryErrorHeaders,
      'TXT Path',
    ].join(','),
    ...summaryRows.map((row) => [
      row.categoryName,
      row.categoryUrl,
      row.level,
      row.uniqueLinks,
      ...Array.from({ length: pages }, (_, index) => row.pageCounts[index] ?? 0),
      ...Array.from({ length: pages }, (_, index) => row.pageErrors[index] ?? ''),
      row.txtPath,
    ].map(csvEscape).join(',')),
  ];
}

function loadExistingRows(filePath) {
  if (!fs.existsSync(filePath)) {
    return [];
  }
  const raw = fs.readFileSync(filePath, 'utf8').replace(/^\uFEFF/, '');
  const lines = raw.split(/\r?\n/).filter((line) => line.trim());
  if (lines.length <= 1) {
    return [];
  }
  const headers = parseCsvLine(lines[0]).map((value) => value.trim());
  return lines.slice(1).map((line) => {
    const parts = parseCsvLine(line);
    const row = {};
    headers.forEach((header, index) => {
      row[header] = parts[index] || '';
    });
    return row;
  });
}

function loadExistingOutputState(outputDir, pages) {
  const combinedPath = path.join(outputDir, 'all_category_product_links.csv');
  const summaryPath = path.join(outputDir, 'category_summary.csv');
  const combinedRows = loadExistingRows(combinedPath).map((row) => ({
    categoryName: row['Category Name'] || '',
    categoryUrl: row['Category URL'] || '',
    level: row['Level'] || '',
    pageNumber: Number.parseInt(row['Page'] || '0', 10),
    rankInPage: Number.parseInt(row['Rank In Page'] || '0', 10),
    productUrl: row['Product URL'] || '',
  }));
  const summaryRows = loadExistingRows(summaryPath).map((row) => ({
    categoryName: row['Category Name'] || '',
    categoryUrl: row['Category URL'] || '',
    level: row['Level'] || '',
    uniqueLinks: Number.parseInt(row['Unique Product Links'] || '0', 10),
    pageCounts: Array.from({ length: pages }, (_, index) => Number.parseInt(row[`Page ${index + 1} Count`] || '0', 10)),
    pageErrors: Array.from({ length: pages }, (_, index) => row[`Page ${index + 1} Error`] || ''),
    txtPath: row['TXT Path'] || '',
  }));
  return { combinedRows, summaryRows };
}

function flushOutputs(outputDir, combinedRows, summaryRows, pages) {
  const combinedCsvPath = path.join(outputDir, 'all_category_product_links.csv');
  const summaryCsvPath = path.join(outputDir, 'category_summary.csv');
  writeLines(combinedCsvPath, buildCombinedCsvLines(combinedRows));
  writeLines(summaryCsvPath, buildSummaryCsvLines(summaryRows, pages));
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const categories = readCategoryCsv(args.input);
  const endIndex = args.endIndex > 0 ? Math.min(args.endIndex, categories.length) : categories.length;
  const limitEndIndex = args.limit > 0 ? Math.min(args.limit, categories.length) : categories.length;
  const effectiveEndIndex = Math.min(endIndex, limitEndIndex);
  const selectedCategories = categories.slice(args.startIndex - 1, effectiveEndIndex);

  ensureDir(args.outputDir);
  const txtDir = path.join(args.outputDir, 'txt');
  ensureDir(txtDir);

  const existingState = args.startIndex > 1 ? loadExistingOutputState(args.outputDir, args.pages) : { combinedRows: [], summaryRows: [] };
  const combinedRows = existingState.combinedRows;
  const summaryRows = existingState.summaryRows;

  const useHelper = fs.existsSync(FETCH_HELPER_PATH);
  const browser = useHelper ? null : await launchBrowser();
  const context = useHelper ? null : await browser.newContext({ userAgent: USER_AGENT });

  try {
    for (let categoryIndex = 0; categoryIndex < selectedCategories.length; categoryIndex += 1) {
      const category = selectedCategories[categoryIndex];
      const categorySlug = slugify(category.categoryName || `category_${categoryIndex + 1}`);
      const uniqueLinks = [];
      const categorySeen = new Set();
      const pageCounts = [];
      const pageErrors = [];

      const absoluteCategoryIndex = args.startIndex + categoryIndex;
      console.log(`[${absoluteCategoryIndex}/${categories.length}] ${category.categoryName}`);

      for (let pageNumber = 1; pageNumber <= args.pages; pageNumber += 1) {
        const pageUrl = buildCategoryPageUrl(category.url, pageNumber, args.pageSize);
        try {
          const html = await fetchHtml(context, pageUrl, args.waitMs);
          const links = extractProductLinks(html);
          pageCounts.push(links.length);
          pageErrors.push('');

          console.log(`  page ${pageNumber}: ${links.length} links`);

          for (let rank = 0; rank < links.length; rank += 1) {
            const productUrl = links[rank];
            combinedRows.push({
              categoryName: category.categoryName,
              categoryUrl: category.url,
              level: category.level,
              pageNumber,
              rankInPage: rank + 1,
              productUrl,
            });

            if (!categorySeen.has(productUrl)) {
              categorySeen.add(productUrl);
              uniqueLinks.push(productUrl);
            }
          }
        } catch (error) {
          const message = error && error.message ? error.message : String(error);
          pageCounts.push(0);
          pageErrors.push(message.replace(/\s+/g, ' ').trim());
          console.error(`  page ${pageNumber}: failed`);
        }
      }

      const txtPath = path.join(txtDir, `${categorySlug}.txt`);
      writeLines(txtPath, uniqueLinks);

      summaryRows.push({
        categoryName: category.categoryName,
        categoryUrl: category.url,
        level: category.level,
        uniqueLinks: uniqueLinks.length,
        txtPath,
        pageCounts,
        pageErrors,
      });

      flushOutputs(args.outputDir, combinedRows, summaryRows, args.pages);
    }
  } finally {
    if (context) {
      await context.close();
    }
    if (browser) {
      await browser.close();
    }
  }

  const combinedCsvPath = path.join(args.outputDir, 'all_category_product_links.csv');
  const summaryCsvPath = path.join(args.outputDir, 'category_summary.csv');

  console.log(`\nDone.`);
  console.log(`Combined CSV: ${combinedCsvPath}`);
  console.log(`Summary CSV:  ${summaryCsvPath}`);
  console.log(`TXT dir:      ${txtDir}`);
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : String(error));
  process.exit(1);
});
