/**
 * html2pptx_wrapper.js — Batch renderer for PPTAgent pipeline
 *
 * Usage: node html2pptx_wrapper.js <html_dir> <output_path> [layout]
 * Layout defaults to LAYOUT_16x9.
 *
 * Outputs JSON to stdout with placeholder coordinates for chart injection.
 */
const html2pptx = require('./html2pptx');
const pptxgen = require('pptxgenjs');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const RECYCLE_PAGES = parseInt(process.env.CHROMIUM_RECYCLE_PAGES || '50', 10);
const RECYCLE_SECONDS = parseInt(process.env.CHROMIUM_RECYCLE_SECONDS || '1800', 10);

async function renderSlides(htmlDir, outputPath, layout) {
    const pptx = new pptxgen();
    pptx.layout = layout || 'LAYOUT_16x9';
    const allPlaceholders = [];
    const errors = [];

    const files = fs.readdirSync(htmlDir)
        .filter(f => f.endsWith('.html'))
        .sort();

    if (files.length === 0) {
        throw new Error(`No HTML files found in ${htmlDir}`);
    }

    const launchOptions = {};
    if (process.platform === 'darwin') launchOptions.channel = 'chrome';

    let browser = await chromium.launch(launchOptions);
    let browserStartTime = Date.now();
    let pagesSinceLaunch = 0;

    for (let i = 0; i < files.length; i++) {
        // Recycle browser if we've rendered too many pages or it's been too long
        if (pagesSinceLaunch >= RECYCLE_PAGES ||
            (Date.now() - browserStartTime) / 1000 >= RECYCLE_SECONDS) {
            await browser.close().catch(() => {});
            browser = await chromium.launch(launchOptions);
            browserStartTime = Date.now();
            pagesSinceLaunch = 0;
        }

        const htmlPath = path.join(htmlDir, files[i]);
        try {
            const result = await html2pptx(htmlPath, pptx, {
                tmpDir: htmlDir,
                browser: browser,
            });
            if (result.placeholders && result.placeholders.length > 0) {
                allPlaceholders.push({
                    slide_index: i,
                    file: files[i],
                    items: result.placeholders
                });
            }
        } catch (err) {
            errors.push({ slide_index: i, file: files[i], error: err.message });
        }
        pagesSinceLaunch++;
    }

    await browser.close().catch(() => {});
    await pptx.writeFile({ fileName: outputPath });

    const result = {
        output_file: outputPath,
        slide_count: files.length,
        placeholders: allPlaceholders,
        errors: errors
    };
    process.stdout.write(JSON.stringify(result));
}

const args = process.argv.slice(2);
if (args.length < 2) {
    console.error('Usage: node html2pptx_wrapper.js <html_dir> <output_path> [layout]');
    process.exit(1);
}

renderSlides(args[0], args[1], args[2]).catch(err => {
    console.error('Render failed:', err.message);
    process.exit(1);
});
