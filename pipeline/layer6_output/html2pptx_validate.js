#!/usr/bin/env node
/**
 * html2pptx_validate.js — Single-slide dry-run validator.
 *
 * Usage:  node html2pptx_validate.js <html_file>
 *
 * Loads the HTML in Chromium, runs the same extraction & dimension checks
 * as html2pptx.js, but does NOT produce a .pptx.
 * Outputs JSON to stdout:  { ok: boolean, errors: string[] }
 */

const path = require('path');
const { chromium } = require('playwright');

const PX_PER_IN = 96;
const PT_PER_PX = 0.75;
const EXPECTED_W = 960;
const EXPECTED_H = 540;

async function validate(htmlFile) {
  const filePath = path.isAbsolute(htmlFile) ? htmlFile : path.join(process.cwd(), htmlFile);
  const errors = [];
  let browser;

  try {
    const launchOptions = {};
    if (process.platform === 'darwin') launchOptions.channel = 'chrome';
    browser = await chromium.launch(launchOptions);
    const page = await browser.newPage();
    await page.goto(`file://${filePath}`);

    // Dimension check
    const dims = await page.evaluate(() => {
      const body = document.body;
      const style = window.getComputedStyle(body);
      return {
        width: parseFloat(style.width),
        height: parseFloat(style.height),
        scrollWidth: body.scrollWidth,
        scrollHeight: body.scrollHeight,
      };
    });

    if (Math.abs(dims.width - 960) > 2 || Math.abs(dims.height - 540) > 2) {
      errors.push(`dimensions ${dims.width.toFixed(0)}x${dims.height.toFixed(0)} expected 960x540`);
    }

    const hOverflow = Math.max(0, dims.scrollHeight - dims.height - 1);
    const wOverflow = Math.max(0, dims.scrollWidth - dims.width - 1);
    if (hOverflow > 0) errors.push(`overflow ${hOverflow}px vertically`);
    if (wOverflow > 0) errors.push(`overflow ${wOverflow}px horizontally`);

    // Content check: walk DOM for text elements
    const contentInfo = await page.evaluate(() => {
      const textEls = document.querySelectorAll('P, H1, H2, H3, H4, H5, H6, LI');
      let visibleCount = 0;
      const issues = [];
      for (const el of textEls) {
        const rect = el.getBoundingClientRect();
        if (rect.height === 0 && rect.width === 0) continue; // hidden
        if (rect.height === 0) {
          issues.push(`zero-height text: <${el.tagName}> "${el.textContent.slice(0, 30)}"`);
          continue;
        }
        visibleCount++;
      }
      return { visibleCount, issues };
    });

    for (const iss of contentInfo.issues) errors.push(iss);

    if (contentInfo.visibleCount === 0) {
      // Check if there's at least some content
      const hasDivContent = await page.evaluate(() => {
        const divs = document.querySelectorAll('DIV');
        let total = 0;
        for (const d of divs) {
          if (d.textContent.trim()) total += d.textContent.trim().length;
        }
        return total;
      });
      if (hasDivContent === 0) errors.push('empty slide: no visible text content');
    }

    // Forbidden elements check
    const forbidden = await page.evaluate(() => {
      const tags = ['SVG', 'IFRAME', 'VIDEO', 'CANVAS', 'FORM'];
      const found = [];
      for (const tag of tags) {
        const els = document.getElementsByTagName(tag);
        if (els.length > 0) found.push(tag.toLowerCase());
      }
      return found;
    });
    for (const tag of forbidden) errors.push(`forbidden element: <${tag}>`);

  } catch (e) {
    errors.push(`browser error: ${e.message}`);
  } finally {
    if (browser) await browser.close();
  }

  const result = { ok: errors.length === 0, errors };
  process.stdout.write(JSON.stringify(result));
}

const htmlFile = process.argv[2];
if (!htmlFile) {
  process.stdout.write(JSON.stringify({ ok: false, errors: ['usage: node html2pptx_validate.js <html_file>'] }));
  process.exit(1);
}

validate(htmlFile).catch(e => {
  process.stdout.write(JSON.stringify({ ok: false, errors: [`fatal: ${e.message}`] }));
  process.exit(1);
});
