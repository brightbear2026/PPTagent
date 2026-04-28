/**
 * html2pptx - Convert HTML slide to pptxgenjs slide with positioned elements
 *
 * Forked from Anthropic Skills (anthropics/skills/skills/pptx/scripts/html2pptx.js)
 * Original license: MIT
 *
 * USAGE:
 * const pptx = new pptxgen();
 * pptx.layout = 'LAYOUT_16x9';
 * const { slide, placeholders } = await html2pptx('slide.html', pptx);
 * await pptx.writeFile('output.pptx');
 */
const { chromium } = require('playwright');
const path = require('path');

const PT_PER_PX = 0.75;
const PX_PER_IN = 96;
const EMU_PER_IN = 914400;

async function getBodyDimensions(page) {
  const bodyDimensions = await page.evaluate(() => {
    const body = document.body;
    const style = window.getComputedStyle(body);
    return {
      width: parseFloat(style.width),
      height: parseFloat(style.height),
      scrollWidth: body.scrollWidth,
      scrollHeight: body.scrollHeight
    };
  });

  const errors = [];
  const widthOverflowPx = Math.max(0, bodyDimensions.scrollWidth - bodyDimensions.width - 1);
  const heightOverflowPx = Math.max(0, bodyDimensions.scrollHeight - bodyDimensions.height - 1);
  const widthOverflowPt = widthOverflowPx * PT_PER_PX;
  const heightOverflowPt = heightOverflowPx * PT_PER_PX;

  if (widthOverflowPt > 0 || heightOverflowPt > 0) {
    const directions = [];
    if (widthOverflowPt > 0) directions.push(`${widthOverflowPt.toFixed(1)}pt horizontally`);
    if (heightOverflowPt > 0) directions.push(`${heightOverflowPt.toFixed(1)}pt vertically`);
    const reminder = heightOverflowPt > 0 ? ' (Remember: leave 0.5" margin at bottom of slide)' : '';
    errors.push(`HTML content overflows body by ${directions.join(' and ')}${reminder}`);
  }
  return { ...bodyDimensions, errors };
}

function validateDimensions(bodyDimensions, pres) {
  const errors = [];
  const widthInches = bodyDimensions.width / PX_PER_IN;
  const heightInches = bodyDimensions.height / PX_PER_IN;
  if (pres.presLayout) {
    const layoutWidth = pres.presLayout.width / EMU_PER_IN;
    const layoutHeight = pres.presLayout.height / EMU_PER_IN;
    if (Math.abs(layoutWidth - widthInches) > 0.1 || Math.abs(layoutHeight - heightInches) > 0.1) {
      errors.push(
        `HTML dimensions (${widthInches.toFixed(1)}" x ${heightInches.toFixed(1)}") ` +
        `don't match presentation layout (${layoutWidth.toFixed(1)}" x ${layoutHeight.toFixed(1)}")`
      );
    }
  }
  return errors;
}

function validateTextBoxPosition(slideData, bodyDimensions) {
  const errors = [];
  const slideHeightInches = bodyDimensions.height / PX_PER_IN;
  const minBottomMargin = 0.5;
  for (const el of slideData.elements) {
    if (['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'list'].includes(el.type)) {
      const fontSize = el.style?.fontSize || 0;
      const bottomEdge = el.position.y + el.position.h;
      const distanceFromBottom = slideHeightInches - bottomEdge;
      if (fontSize > 12 && distanceFromBottom < minBottomMargin) {
        const getText = () => {
          if (typeof el.text === 'string') return el.text;
          if (Array.isArray(el.text)) return el.text.find(t => t.text)?.text || '';
          if (Array.isArray(el.items)) return el.items.find(item => item.text)?.text || '';
          return '';
        };
        const txt = getText();
        const textPrefix = txt.substring(0, 50) + (txt.length > 50 ? '...' : '');
        errors.push(
          `Text box "${textPrefix}" ends too close to bottom edge ` +
          `(${distanceFromBottom.toFixed(2)}" from bottom, minimum ${minBottomMargin}" required)`
        );
      }
    }
  }
  return errors;
}

async function addBackground(slideData, targetSlide, tmpDir) {
  if (slideData.background.type === 'image' && slideData.background.path) {
    let imagePath = slideData.background.path.startsWith('file://')
      ? slideData.background.path.replace('file://', '')
      : slideData.background.path;
    targetSlide.background = { path: imagePath };
  } else if (slideData.background.type === 'color' && slideData.background.value) {
    targetSlide.background = { color: slideData.background.value };
  }
}

function addElements(slideData, targetSlide, pres) {
  const CJK_RE = /[一-鿿　-〿＀-￯]/;

  function safeCjkFont(originalFont, text) {
    if (!text || typeof text !== 'string') return originalFont;
    if (!CJK_RE.test(text)) return originalFont;
    return 'Microsoft YaHei';  // English name for cross-platform Office
  }

  for (const el of slideData.elements) {
    if (el.type === 'image') {
      let imagePath = el.src.startsWith('file://') ? el.src.replace('file://', '') : el.src;
      targetSlide.addImage({
        path: imagePath,
        x: el.position.x, y: el.position.y,
        w: el.position.w, h: el.position.h
      });
    } else if (el.type === 'line') {
      targetSlide.addShape(pres.ShapeType.line, {
        x: el.x1, y: el.y1,
        w: el.x2 - el.x1, h: el.y2 - el.y1,
        line: { color: el.color, width: el.width }
      });
    } else if (el.type === 'shape') {
      const shapeOptions = {
        x: el.position.x, y: el.position.y,
        w: el.position.w, h: el.position.h,
        shape: el.shape.rectRadius > 0 ? pres.ShapeType.roundRect : pres.ShapeType.rect
      };
      if (el.shape.fill) {
        shapeOptions.fill = { color: el.shape.fill };
        if (el.shape.transparency != null) shapeOptions.fill.transparency = el.shape.transparency;
      }
      if (el.shape.line) shapeOptions.line = el.shape.line;
      if (el.shape.rectRadius > 0) shapeOptions.rectRadius = el.shape.rectRadius;
      if (el.shape.shadow) shapeOptions.shadow = el.shape.shadow;
      targetSlide.addText(el.text || '', shapeOptions);
    } else if (el.type === 'list') {
      const listFont = safeCjkFont(el.style.fontFace, el.items.map(r => r.text || '').join(''));
      const listOptions = {
        x: el.position.x, y: el.position.y,
        w: el.position.w, h: el.position.h,
        fontSize: el.style.fontSize,
        fontFace: listFont,
        color: el.style.color,
        align: el.style.align,
        valign: 'top',
        lineSpacing: el.style.lineSpacing,
        paraSpaceBefore: el.style.paraSpaceBefore,
        paraSpaceAfter: el.style.paraSpaceAfter,
        autoFit: true
      };
      if (el.style.margin) listOptions.margin = el.style.margin;
      targetSlide.addText(el.items, listOptions);
    } else {
      const lineHeight = el.style.lineSpacing || el.style.fontSize * 1.2;
      const isSingleLine = el.position.h <= lineHeight * 1.5;
      let adjustedX = el.position.x;
      let adjustedW = el.position.w;

      if (isSingleLine) {
        const widthIncrease = el.position.w * 0.02;
        const align = el.style.align;
        if (align === 'center') {
          adjustedX = el.position.x - (widthIncrease / 2);
          adjustedW = el.position.w + widthIncrease;
        } else if (align === 'right') {
          adjustedX = el.position.x - widthIncrease;
          adjustedW = el.position.w + widthIncrease;
        } else {
          adjustedW = el.position.w + widthIncrease;
        }
      }

      const elText = typeof el.text === 'string' ? el.text : (Array.isArray(el.text) ? el.text.map(r => r.text || '').join('') : '');
      const elFont = safeCjkFont(el.style.fontFace, elText);
      const textOptions = {
        x: adjustedX, y: el.position.y,
        w: adjustedW, h: el.position.h,
        fontSize: el.style.fontSize,
        fontFace: elFont,
        color: el.style.color,
        bold: el.style.bold,
        italic: el.style.italic,
        underline: el.style.underline,
        valign: 'top',
        lineSpacing: el.style.lineSpacing,
        paraSpaceBefore: el.style.paraSpaceBefore,
        paraSpaceAfter: el.style.paraSpaceAfter,
        inset: 0,
        autoFit: true
      };
      if (el.style.align) textOptions.align = el.style.align;
      if (el.style.margin) textOptions.margin = el.style.margin;
      if (el.style.rotate !== undefined) textOptions.rotate = el.style.rotate;
      if (el.style.transparency !== null && el.style.transparency !== undefined) {
        textOptions.transparency = el.style.transparency;
      }
      targetSlide.addText(el.text, textOptions);
    }
  }
}

async function extractSlideData(page) {
  return await page.evaluate(() => {
    const PT_PER_PX = 0.75;
    const PX_PER_IN = 96;
    const SINGLE_WEIGHT_FONTS = ['impact'];

    const shouldSkipBold = (fontFamily) => {
      if (!fontFamily) return false;
      const normalizedFont = fontFamily.toLowerCase().replace(/['"]/g, '').split(',')[0].trim();
      return SINGLE_WEIGHT_FONTS.includes(normalizedFont);
    };

    const pxToInch = (px) => px / PX_PER_IN;
    const pxToPoints = (pxStr) => parseFloat(pxStr) * PT_PER_PX;

    const rgbToHex = (rgbStr) => {
      if (rgbStr === 'rgba(0, 0, 0, 0)' || rgbStr === 'transparent') return 'FFFFFF';
      const match = rgbStr.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
      if (!match) return 'FFFFFF';
      return match.slice(1).map(n => parseInt(n).toString(16).padStart(2, '0')).join('');
    };

    const extractAlpha = (rgbStr) => {
      const match = rgbStr.match(/rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)/);
      if (!match || !match[4]) return null;
      return Math.round((1 - parseFloat(match[4])) * 100);
    };

    const applyTextTransform = (text, textTransform) => {
      if (textTransform === 'uppercase') return text.toUpperCase();
      if (textTransform === 'lowercase') return text.toLowerCase();
      if (textTransform === 'capitalize') return text.replace(/\b\w/g, c => c.toUpperCase());
      return text;
    };

    const getRotation = (transform, writingMode) => {
      let angle = 0;
      if (writingMode === 'vertical-rl') angle = 90;
      else if (writingMode === 'vertical-lr') angle = 270;

      if (transform && transform !== 'none') {
        const rotateMatch = transform.match(/rotate\((-?\d+(?:\.\d+)?)deg\)/);
        if (rotateMatch) {
          angle += parseFloat(rotateMatch[1]);
        } else {
          const matrixMatch = transform.match(/matrix\(([^)]+)\)/);
          if (matrixMatch) {
            const values = matrixMatch[1].split(',').map(parseFloat);
            angle += Math.round(Math.atan2(values[1], values[0]) * (180 / Math.PI));
          }
        }
      }
      angle = angle % 360;
      if (angle < 0) angle += 360;
      return angle === 0 ? null : angle;
    };

    const getPositionAndSize = (el, rect, rotation) => {
      if (rotation === null) {
        return { x: rect.left, y: rect.top, w: rect.width, h: rect.height };
      }
      const isVertical = rotation === 90 || rotation === 270;
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      if (isVertical) {
        return { x: centerX - rect.height / 2, y: centerY - rect.width / 2, w: rect.height, h: rect.width };
      }
      return { x: centerX - el.offsetWidth / 2, y: centerY - el.offsetHeight / 2, w: el.offsetWidth, h: el.offsetHeight };
    };

    const parseBoxShadow = (boxShadow) => {
      if (!boxShadow || boxShadow === 'none') return null;
      if (boxShadow.match(/inset/)) return null;
      const colorMatch = boxShadow.match(/rgba?\([^)]+\)/);
      const parts = boxShadow.match(/([-\d.]+)(px|pt)/g);
      if (!parts || parts.length < 2) return null;
      const offsetX = parseFloat(parts[0]);
      const offsetY = parseFloat(parts[1]);
      const blur = parts.length > 2 ? parseFloat(parts[2]) : 0;
      let angle = 0;
      if (offsetX !== 0 || offsetY !== 0) {
        angle = Math.atan2(offsetY, offsetX) * (180 / Math.PI);
        if (angle < 0) angle += 360;
      }
      const offset = Math.sqrt(offsetX * offsetX + offsetY * offsetY) * PT_PER_PX;
      let opacity = 0.5;
      if (colorMatch) {
        const opacityMatch = colorMatch[0].match(/[\d.]+\)$/);
        if (opacityMatch) opacity = parseFloat(opacityMatch[0].replace(')', ''));
      }
      return {
        type: 'outer', angle: Math.round(angle),
        blur: blur * 0.75, color: colorMatch ? rgbToHex(colorMatch[0]) : '000000',
        offset, opacity
      };
    };

    const parseInlineFormatting = (element, baseOptions = {}, runs = [], baseTextTransform = (x) => x) => {
      let prevNodeIsText = false;
      element.childNodes.forEach((node) => {
        let textTransform = baseTextTransform;
        const isText = node.nodeType === Node.TEXT_NODE || node.tagName === 'BR';
        if (isText) {
          const text = node.tagName === 'BR' ? '\n' : textTransform(node.textContent.replace(/\s+/g, ' '));
          const prevRun = runs[runs.length - 1];
          if (prevNodeIsText && prevRun) {
            prevRun.text += text;
          } else {
            runs.push({ text, options: { ...baseOptions } });
          }
        } else if (node.nodeType === Node.ELEMENT_NODE && node.textContent.trim()) {
          const options = { ...baseOptions };
          const computed = window.getComputedStyle(node);
          if (['SPAN', 'B', 'STRONG', 'I', 'EM', 'U'].includes(node.tagName)) {
            const isBold = computed.fontWeight === 'bold' || parseInt(computed.fontWeight) >= 600;
            if (isBold && !shouldSkipBold(computed.fontFamily)) options.bold = true;
            if (computed.fontStyle === 'italic') options.italic = true;
            if (computed.textDecoration && computed.textDecoration.includes('underline')) options.underline = true;
            if (computed.color && computed.color !== 'rgb(0, 0, 0)') {
              options.color = rgbToHex(computed.color);
              const transparency = extractAlpha(computed.color);
              if (transparency !== null) options.transparency = transparency;
            }
            if (computed.fontSize) options.fontSize = pxToPoints(computed.fontSize);
            if (computed.textTransform && computed.textTransform !== 'none') {
              const transformStr = computed.textTransform;
              textTransform = (text) => applyTextTransform(text, transformStr);
            }
            parseInlineFormatting(node, options, runs, textTransform);
          }
        }
        prevNodeIsText = isText;
      });
      if (runs.length > 0) {
        runs[0].text = runs[0].text.replace(/^\s+/, '');
        runs[runs.length - 1].text = runs[runs.length - 1].text.replace(/\s+$/, '');
      }
      return runs.filter(r => r.text.length > 0);
    };

    const body = document.body;
    const bodyStyle = window.getComputedStyle(body);
    const bgImage = bodyStyle.backgroundImage;
    const bgColor = bodyStyle.backgroundColor;
    const errors = [];

    if (bgImage && (bgImage.includes('linear-gradient') || bgImage.includes('radial-gradient'))) {
      errors.push('CSS gradients are not supported. Use Sharp to rasterize gradients as PNG images first.');
    }

    let background;
    if (bgImage && bgImage !== 'none') {
      const urlMatch = bgImage.match(/url\(["']?([^"')]+)["']?\)/);
      background = urlMatch ? { type: 'image', path: urlMatch[1] } : { type: 'color', value: rgbToHex(bgColor) };
    } else {
      background = { type: 'color', value: rgbToHex(bgColor) };
    }

    const elements = [];
    const placeholders = [];
    const textTags = ['P', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'UL', 'OL', 'LI'];
    const processed = new Set();

    document.querySelectorAll('*').forEach((el) => {
      if (processed.has(el)) return;

      if (textTags.includes(el.tagName)) {
        const computed = window.getComputedStyle(el);
        const hasBg = computed.backgroundColor && computed.backgroundColor !== 'rgba(0, 0, 0, 0)';
        const hasBorder = [computed.borderTopWidth, computed.borderRightWidth, computed.borderBottomWidth, computed.borderLeftWidth]
          .some(b => parseFloat(b) > 0);
        const hasShadow = computed.boxShadow && computed.boxShadow !== 'none';
        if (hasBg || hasBorder || hasShadow) {
          errors.push(`Text element <${el.tagName.toLowerCase()}> has ${hasBg ? 'background' : hasBorder ? 'border' : 'shadow'}. Only <div> elements support backgrounds/borders/shadows.`);
          return;
        }
      }

      if (el.className && el.className.includes('placeholder')) {
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) {
          errors.push(`Placeholder "${el.id || 'unnamed'}" has zero dimensions.`);
        } else {
          placeholders.push({
            id: el.id || `placeholder-${placeholders.length}`,
            x: pxToInch(rect.left), y: pxToInch(rect.top),
            w: pxToInch(rect.width), h: pxToInch(rect.height)
          });
        }
        processed.add(el);
        return;
      }

      if (el.tagName === 'IMG') {
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
          elements.push({
            type: 'image', src: el.src,
            position: { x: pxToInch(rect.left), y: pxToInch(rect.top), w: pxToInch(rect.width), h: pxToInch(rect.height) }
          });
          processed.add(el);
          return;
        }
      }

      const isContainer = el.tagName === 'DIV' && !textTags.includes(el.tagName);
      if (isContainer) {
        const computed = window.getComputedStyle(el);
        const hasBg = computed.backgroundColor && computed.backgroundColor !== 'rgba(0, 0, 0, 0)';

        for (const node of el.childNodes) {
          if (node.nodeType === Node.TEXT_NODE) {
            const text = node.textContent.trim();
            if (text) {
              errors.push(`DIV contains unwrapped text "${text.substring(0, 50)}${text.length > 50 ? '...' : ''}". Wrap in <p> or <h1>-<h6>.`);
            }
          }
        }

        const bgImg = computed.backgroundImage;
        if (bgImg && bgImg !== 'none') {
          errors.push('Background images on DIV elements are not supported.');
          return;
        }

        const borders = [computed.borderTopWidth, computed.borderRightWidth, computed.borderBottomWidth, computed.borderLeftWidth].map(b => parseFloat(b) || 0);
        const hasBorder = borders.some(b => b > 0);
        const hasUniformBorder = hasBorder && borders.every(b => b === borders[0]);
        const borderLines = [];

        if (hasBorder && !hasUniformBorder) {
          const rect = el.getBoundingClientRect();
          const x = pxToInch(rect.left), y = pxToInch(rect.top);
          const w = pxToInch(rect.width), h = pxToInch(rect.height);
          if (parseFloat(computed.borderTopWidth) > 0) {
            const widthPt = pxToPoints(computed.borderTopWidth);
            const inset = (widthPt / 72) / 2;
            borderLines.push({ type: 'line', x1: x, y1: y + inset, x2: x + w, y2: y + inset, width: widthPt, color: rgbToHex(computed.borderTopColor) });
          }
          if (parseFloat(computed.borderRightWidth) > 0) {
            const widthPt = pxToPoints(computed.borderRightWidth);
            const inset = (widthPt / 72) / 2;
            borderLines.push({ type: 'line', x1: x + w - inset, y1: y, x2: x + w - inset, y2: y + h, width: widthPt, color: rgbToHex(computed.borderRightColor) });
          }
          if (parseFloat(computed.borderBottomWidth) > 0) {
            const widthPt = pxToPoints(computed.borderBottomWidth);
            const inset = (widthPt / 72) / 2;
            borderLines.push({ type: 'line', x1: x, y1: y + h - inset, x2: x + w, y2: y + h - inset, width: widthPt, color: rgbToHex(computed.borderBottomColor) });
          }
          if (parseFloat(computed.borderLeftWidth) > 0) {
            const widthPt = pxToPoints(computed.borderLeftWidth);
            const inset = (widthPt / 72) / 2;
            borderLines.push({ type: 'line', x1: x + inset, y1: y, x2: x + inset, y2: y + h, width: widthPt, color: rgbToHex(computed.borderLeftColor) });
          }
        }

        if (hasBg || hasBorder) {
          const rect = el.getBoundingClientRect();
          if (rect.width > 0 && rect.height > 0) {
            const shadow = parseBoxShadow(computed.boxShadow);
            if (hasBg || hasUniformBorder) {
              elements.push({
                type: 'shape', text: '',
                position: { x: pxToInch(rect.left), y: pxToInch(rect.top), w: pxToInch(rect.width), h: pxToInch(rect.height) },
                shape: {
                  fill: hasBg ? rgbToHex(computed.backgroundColor) : null,
                  transparency: hasBg ? extractAlpha(computed.backgroundColor) : null,
                  line: hasUniformBorder ? { color: rgbToHex(computed.borderColor), width: pxToPoints(computed.borderWidth) } : null,
                  rectRadius: (() => {
                    const radius = computed.borderRadius;
                    const radiusValue = parseFloat(radius);
                    if (radiusValue === 0) return 0;
                    if (radius.includes('%')) {
                      if (radiusValue >= 50) return 1;
                      return (radiusValue / 100) * pxToInch(Math.min(rect.width, rect.height));
                    }
                    if (radius.includes('pt')) return radiusValue / 72;
                    return radiusValue / PX_PER_IN;
                  })(),
                  shadow
                }
              });
            }
            elements.push(...borderLines);
            processed.add(el);
            return;
          }
        }
      }

      if (el.tagName === 'UL' || el.tagName === 'OL') {
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;
        const liElements = Array.from(el.querySelectorAll('li'));
        const items = [];
        const ulComputed = window.getComputedStyle(el);
        const ulPaddingLeftPt = pxToPoints(ulComputed.paddingLeft);
        const marginLeft = ulPaddingLeftPt * 0.5;
        const textIndent = ulPaddingLeftPt * 0.5;
        liElements.forEach((li, idx) => {
          const isLast = idx === liElements.length - 1;
          const runs = parseInlineFormatting(li, { breakLine: false });
          if (runs.length > 0) {
            runs[0].text = runs[0].text.replace(/^[•\-\*▪▸]\s*/, '');
            runs[0].options.bullet = { indent: textIndent };
          }
          if (runs.length > 0 && !isLast) {
            runs[runs.length - 1].options.breakLine = true;
          }
          items.push(...runs);
        });
        const computed = window.getComputedStyle(liElements[0] || el);
        elements.push({
          type: 'list', items,
          position: { x: pxToInch(rect.left), y: pxToInch(rect.top), w: pxToInch(rect.width), h: pxToInch(rect.height) },
          style: {
            fontSize: pxToPoints(computed.fontSize),
            fontFace: computed.fontFamily.split(',')[0].replace(/['"]/g, '').trim(),
            color: rgbToHex(computed.color),
            transparency: extractAlpha(computed.color),
            align: computed.textAlign === 'start' ? 'left' : computed.textAlign,
            lineSpacing: computed.lineHeight && computed.lineHeight !== 'normal' ? pxToPoints(computed.lineHeight) : null,
            paraSpaceBefore: 0,
            paraSpaceAfter: pxToPoints(computed.marginBottom),
            margin: [marginLeft, 0, 0, 0]
          }
        });
        liElements.forEach(li => processed.add(li));
        processed.add(el);
        return;
      }

      if (!textTags.includes(el.tagName)) return;
      const rect = el.getBoundingClientRect();
      const text = el.textContent.trim();
      if (rect.width === 0 || rect.height === 0 || !text) return;

      if (el.tagName !== 'LI' && /^[•\-\*▪▸○●◆◇■□]\s/.test(text.trimStart())) {
        errors.push(`Text element <${el.tagName.toLowerCase()}> starts with bullet symbol. Use <ul>/<ol> instead.`);
        return;
      }

      const computed = window.getComputedStyle(el);
      const rotation = getRotation(computed.transform, computed.writingMode);
      const { x, y, w, h } = getPositionAndSize(el, rect, rotation);

      const baseStyle = {
        fontSize: pxToPoints(computed.fontSize),
        fontFace: computed.fontFamily.split(',')[0].replace(/['"]/g, '').trim(),
        color: rgbToHex(computed.color),
        align: computed.textAlign === 'start' ? 'left' : computed.textAlign,
        lineSpacing: pxToPoints(computed.lineHeight),
        paraSpaceBefore: pxToPoints(computed.marginTop),
        paraSpaceAfter: pxToPoints(computed.marginBottom),
        margin: [pxToPoints(computed.paddingLeft), pxToPoints(computed.paddingRight), pxToPoints(computed.paddingBottom), pxToPoints(computed.paddingTop)]
      };

      const transparency = extractAlpha(computed.color);
      if (transparency !== null) baseStyle.transparency = transparency;
      if (rotation !== null) baseStyle.rotate = rotation;

      const hasFormatting = el.querySelector('b, i, u, strong, em, span, br');
      if (hasFormatting) {
        const transformStr = computed.textTransform;
        const runs = parseInlineFormatting(el, {}, [], (str) => applyTextTransform(str, transformStr));
        const adjustedStyle = { ...baseStyle };
        if (adjustedStyle.lineSpacing) {
          const maxFontSize = Math.max(adjustedStyle.fontSize, ...runs.map(r => r.options?.fontSize || 0));
          if (maxFontSize > adjustedStyle.fontSize) {
            adjustedStyle.lineSpacing = maxFontSize * (adjustedStyle.lineSpacing / adjustedStyle.fontSize);
          }
        }
        elements.push({ type: el.tagName.toLowerCase(), text: runs, position: { x: pxToInch(x), y: pxToInch(y), w: pxToInch(w), h: pxToInch(h) }, style: adjustedStyle });
      } else {
        const textTransform = computed.textTransform;
        const transformedText = applyTextTransform(text, textTransform);
        const isBold = computed.fontWeight === 'bold' || parseInt(computed.fontWeight) >= 600;
        elements.push({
          type: el.tagName.toLowerCase(), text: transformedText,
          position: { x: pxToInch(x), y: pxToInch(y), w: pxToInch(w), h: pxToInch(h) },
          style: { ...baseStyle, bold: isBold && !shouldSkipBold(computed.fontFamily), italic: computed.fontStyle === 'italic', underline: computed.textDecoration.includes('underline') }
        });
      }
      processed.add(el);
    });

    return { background, elements, placeholders, errors };
  });
}

async function html2pptx(htmlFile, pres, options = {}) {
  const { tmpDir = process.env.TMPDIR || '/tmp', slide = null, browser = null } = options;

  const ownBrowser = !browser;
  let launchedBrowser = browser;

  try {
    if (!launchedBrowser) {
      const launchOptions = { env: { TMPDIR: tmpDir } };
      if (process.platform === 'darwin') launchOptions.channel = 'chrome';
      launchedBrowser = await chromium.launch(launchOptions);
    }

    let bodyDimensions, slideData;
    const filePath = path.isAbsolute(htmlFile) ? htmlFile : path.join(process.cwd(), htmlFile);
    const validationErrors = [];

    let page;
    try {
      page = await launchedBrowser.newPage();
      await page.goto(`file://${filePath}`);
      bodyDimensions = await getBodyDimensions(page);
      await page.setViewportSize({ width: Math.round(bodyDimensions.width), height: Math.round(bodyDimensions.height) });
      slideData = await extractSlideData(page);
    } finally {
      if (page) await page.close().catch(() => {});
    }

    if (bodyDimensions.errors?.length) validationErrors.push(...bodyDimensions.errors);
    const dimErrors = validateDimensions(bodyDimensions, pres);
    if (dimErrors.length) validationErrors.push(...dimErrors);
    const posErrors = validateTextBoxPosition(slideData, bodyDimensions);
    if (posErrors.length) validationErrors.push(...posErrors);
    if (slideData.errors?.length) validationErrors.push(...slideData.errors);

    if (validationErrors.length) {
      const msg = validationErrors.length === 1
        ? validationErrors[0]
        : `Multiple validation errors:\n${validationErrors.map((e, i) => ` ${i + 1}. ${e}`).join('\n')}`;
      throw new Error(msg);
    }

    const targetSlide = slide || pres.addSlide();
    await addBackground(slideData, targetSlide, tmpDir);
    addElements(slideData, targetSlide, pres);
    return { slide: targetSlide, placeholders: slideData.placeholders };
  } catch (error) {
    if (!error.message.startsWith(htmlFile)) throw new Error(`${htmlFile}: ${error.message}`);
    throw error;
  } finally {
    if (ownBrowser && launchedBrowser) await launchedBrowser.close().catch(() => {});
  }
}

module.exports = html2pptx;
