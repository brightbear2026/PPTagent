/**
 * render_server.js — Persistent HTTP server for HTML→PPTX rendering.
 *
 * Replaces the per-render subprocess model. Stays running between calls,
 * reusing a single Chromium browser instance across render jobs.
 *
 * Endpoints:
 *   POST /render   { html_dir, output_path, layout? } → JSON result
 *   GET  /health   → { ok: true, browser: "ready"|"closed", uptime_secs }
 *   POST /shutdown → graceful stop
 *
 * Environment:
 *   RENDER_PORT          — listen port (default 19876)
 *   CHROMIUM_RECYCLE_PAGES    — recycle browser after N pages (default 50)
 *   CHROMIUM_RECYCLE_SECONDS  — recycle browser after N seconds (default 1800)
 */

const http = require('http');
const path = require('path');
const fs = require('fs');
const { chromium } = require('playwright');
const pptxgen = require('pptxgenjs');
const html2pptx = require('./html2pptx');

const PORT = parseInt(process.env.RENDER_PORT || '19876', 10);
const RECYCLE_PAGES = parseInt(process.env.CHROMIUM_RECYCLE_PAGES || '50', 10);
const RECYCLE_SECONDS = parseInt(process.env.CHROMIUM_RECYCLE_SECONDS || '1800', 10);

let browser = null;
let browserStartTime = 0;
let pagesSinceLaunch = 0;
const serverStartTime = Date.now();

async function ensureBrowser() {
  const needRecycle = browser &&
    (pagesSinceLaunch >= RECYCLE_PAGES ||
     (Date.now() - browserStartTime) / 1000 >= RECYCLE_SECONDS);
  if (needRecycle) {
    await browser.close().catch(() => {});
    browser = null;
  }
  if (!browser) {
    const opts = {};
    if (process.platform === 'darwin') opts.channel = 'chrome';
    browser = await chromium.launch(opts);
    browserStartTime = Date.now();
    pagesSinceLaunch = 0;
  }
  return browser;
}

async function handleRender(req, res, body) {
  let params;
  try {
    params = JSON.parse(body);
  } catch {
    sendJson(res, 400, { error: 'Invalid JSON body' });
    return;
  }
  const { html_dir, output_path, layout } = params;
  if (!html_dir || !output_path) {
    sendJson(res, 400, { error: 'Missing html_dir or output_path' });
    return;
  }

  try {
    const b = await ensureBrowser();
    const pptx = new pptxgen();
    pptx.layout = layout || 'LAYOUT_16x9';

    const allPlaceholders = [];
    const errors = [];

    const files = fs.readdirSync(html_dir)
      .filter(f => f.endsWith('.html'))
      .sort();

    if (files.length === 0) {
      sendJson(res, 400, { error: `No HTML files found in ${html_dir}` });
      return;
    }

    for (let i = 0; i < files.length; i++) {
      // Re-check recycling mid-batch
      if (pagesSinceLaunch >= RECYCLE_PAGES ||
          (Date.now() - browserStartTime) / 1000 >= RECYCLE_SECONDS) {
        await browser.close().catch(() => {});
        const opts = {};
        if (process.platform === 'darwin') opts.channel = 'chrome';
        browser = await chromium.launch(opts);
        browserStartTime = Date.now();
        pagesSinceLaunch = 0;
      }

      const htmlPath = path.join(html_dir, files[i]);
      try {
        const result = await html2pptx(htmlPath, pptx, {
          tmpDir: html_dir,
          browser: browser,
        });
        if (result.placeholders && result.placeholders.length > 0) {
          allPlaceholders.push({
            slide_index: i,
            file: files[i],
            items: result.placeholders,
          });
        }
      } catch (err) {
        errors.push({ slide_index: i, file: files[i], error: err.message });
      }
      pagesSinceLaunch++;
    }

    await pptx.writeFile({ fileName: output_path });

    sendJson(res, 200, {
      output_file: output_path,
      slide_count: files.length,
      placeholders: allPlaceholders,
      errors: errors,
    });
  } catch (err) {
    // If browser crashed, clear reference so next call re-launches
    browser = null;
    sendJson(res, 500, { error: err.message });
  }
}

function handleHealth(res) {
  sendJson(res, 200, {
    ok: true,
    browser: browser ? 'ready' : 'not_started',
    uptime_secs: Math.round((Date.now() - serverStartTime) / 1000),
    pages_since_launch: pagesSinceLaunch,
  });
}

function handleShutdown(res) {
  sendJson(res, 200, { message: 'shutting down' });
  const close = async () => {
    if (browser) await browser.close().catch(() => {});
    server.close();
    process.exit(0);
  };
  close();
}

function sendJson(res, status, data) {
  const body = JSON.stringify(data);
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(body),
  });
  res.end(body);
}

const server = http.createServer((req, res) => {
  if (req.method === 'GET' && req.url === '/health') {
    handleHealth(res);
    return;
  }
  if (req.method === 'POST' && req.url === '/shutdown') {
    handleShutdown(res);
    return;
  }
  if (req.method === 'POST' && req.url === '/render') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => handleRender(req, res, body));
    return;
  }
  sendJson(res, 404, { error: 'Not found' });
});

server.listen(PORT, '127.0.0.1', () => {
  // Signal readiness to parent process
  if (process.send) process.send({ ready: true, port: PORT });
  // Also write to stderr for subprocess mode detection
  process.stderr.write(`render_server listening on ${PORT}\n`);
});

server.on('error', (err) => {
  process.stderr.write(`server error: ${err.message}\n`);
  if (err.code === 'EADDRINUSE') {
    process.exit(1);
  }
});

process.on('SIGTERM', async () => {
  if (browser) await browser.close().catch(() => {});
  server.close();
  process.exit(0);
});

process.on('SIGINT', async () => {
  if (browser) await browser.close().catch(() => {});
  server.close();
  process.exit(0);
});
