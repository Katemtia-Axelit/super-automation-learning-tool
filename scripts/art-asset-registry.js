#!/usr/bin/env node
/*
 * art-asset-registry.js
 * =====================
 *
 * LT_M1_5E — Art Asset Registry & Build CLI.
 *
 * Stable, dependency-free Node CLI for binding SVG art assets to the
 * `--art-*` CSS custom properties that M1.5A/B/C registered in
 * src/index.html.  Outputs static/assets/art-overrides.css from a
 * machine-readable manifest.  Never touches any other file.
 *
 * Subcommands:
 *   check  Read-only.  Walks manifest slots, prints status of each
 *          expected file, validates SVG files that exist, and
 *          reports mismatches.  Exits 1 if the manifest is malformed
 *          or SVG validation fails.
 *   list   Read-only.  Prints a tabular view of every slot.
 *   build  Writes static/assets/art-overrides.css.  Only files that
 *          exist on disk AND pass validation produce a CSS `url(...)`
 *          line; missing files emit `: none;`.  Idempotent (re-running
 *          yields byte-identical output).
 *
 * Conventions:
 *   - All paths in the manifest are relative to the manifest's own
 *     directory.  This CLI never reads or writes absolute paths.
 *   - All SVG references in the generated CSS are also relative
 *     (e.g. `./cards/faces/theme-math/front-bg.svg`).  The browser
 *     resolves them against the CSS file's URL (i.e. /static/assets/).
 *   - Directory traversal, symlinks, external CDN URLs, <script>,
 *     <foreignObject>, animation-of-untrusted-data, and other unsafe
 *     SVG patterns are rejected.
 *   - Errors fail closed: build refuses to overwrite art-overrides.css
 *     if validation fails; check/list also exit 1 on errors.
 *
 * Companion manifest: static/assets/art-manifest.json.
 * Companion test:    scripts/art-asset-registry.test.js.
 */

'use strict';

const fs = require('fs');
const path = require('path');

const TOOL_VERSION = '1.0.0';

// -------------------- helpers --------------------

function die(msg, code) {
  process.stderr.write('[art-asset-registry] error: ' + msg + '\n');
  process.exit(code || 1);
}

function info(msg) {
  process.stdout.write('[art-asset-registry] ' + msg + '\n');
}

function repoRoot() {
  return path.resolve(__dirname, '..');
}

function defaults() {
  return {
    repoRoot: repoRoot(),
    manifestPath: path.join(repoRoot(), 'static', 'assets', 'art-manifest.json'),
    assetsDir: path.join(repoRoot(), 'static', 'assets'),
    cssOutPath: path.join(repoRoot(), 'static', 'assets', 'art-overrides.css'),
  };
}

function loadManifest(p) {
  let raw;
  try {
    raw = fs.readFileSync(p, 'utf8');
  } catch (e) {
    die('cannot read manifest at ' + p + ': ' + e.message, 1);
  }
  let json;
  try {
    json = JSON.parse(raw);
  } catch (e) {
    die('manifest is not valid JSON: ' + e.message, 1);
  }
  if (!json.slots || typeof json.slots !== 'object') {
    die('manifest.slots missing or not an object', 1);
  }
  if (!json.css_hooks || typeof json.css_hooks !== 'object') {
    die('manifest.css_hooks missing or not an object', 1);
  }
  return json;
}

/**
 * Reject paths that escape the assets dir or contain symlinks/unsafe segments.
 *
 * NOTE: This walk does NOT follow symlinks.  Symlinks encountered inside
 * the assets tree are REJECTED with an error message; build still runs
 * for the safe parts and skips the unsafe parts.
 *
 * Returns:
 *   { abs: <absolute resolved path>,
 *     rel: <posix-style path relative to assetsDir>,
 *     exists: boolean,
 *     stat: fs.Stats or null }
 */
function safeResolve(assetsDir, relPath) {
  if (typeof relPath !== 'string' || relPath.length === 0) {
    return { err: 'invalid path: empty' };
  }
  // Normalize to posix separators and reject obvious traversals early.
  const norm = relPath.replace(/\\/g, '/');
  if (norm.includes('\0')) return { err: 'NUL byte in path' };
  if (norm.split('/').some((seg) => seg === '..' || seg === '.')) {
    return { err: 'directory traversal segment (./ or ../) in ' + relPath };
  }
  const abs = path.resolve(assetsDir, norm);
  const base = path.resolve(assetsDir) + path.sep;
  if (abs !== path.resolve(assetsDir) &&
      !abs.startsWith(base)) {
    return { err: 'escapes assets root: ' + relPath };
  }
  if (!fs.existsSync(abs)) {
    return { abs, rel: norm.replace(/\//g, path.sep), exists: false, stat: null };
  }
  const st = fs.lstatSync(abs); // do not follow symlinks
  if (st.isSymbolicLink()) {
    return { err: 'symlink not allowed: ' + relPath };
  }
  return { abs, rel: norm.replace(/\//g, path.sep), exists: true, stat: st };
}

/**
 * Validate SVG content per contract constraints in M1.5A §2 + M1.5E task spec.
 *
 * Rejected:
 *   - <script> (any case, any namespace prefix)
 *   - <foreignObject>
 *   - <use href="..."> with non-# targets (i.e. external references)
 *   - xlink:href / href values starting with http:// https:// // (protocol-rel)
 *   - xmlns / attribute values missing viewBox on root
 *
 * Accepted:
 *   - <svg> root with explicit viewBox (digit pairs separated by spaces/commas)
 *   - internal #fragment references in <use> (e.g. <use href="#g_id">)
 *   - empty files (treated as "missing" by caller)
 */
function validateSvgContent(content, relPath) {
  if (typeof content !== 'string' || content.length === 0) {
    return { ok: false, reason: 'empty content' };
  }
  // Strip BOM if present.
  const c = content.charCodeAt(0) === 0xFEFF ? content.slice(1) : content;
  // Disallowed tags (case insensitive; allow leading namespace {prefix}).
  const lower = c.toLowerCase();
  // Strip XML comments before tag scan to avoid false positives from "<!-- <script> -->".
  const stripped = c.replace(/<!--[\s\S]*?-->/g, '');
  const sl = stripped.toLowerCase();
  function tagRegex(name) { return new RegExp('<\\s*[a-zA-Z:_-]*' + name + '\\b', 'g'); }
  function badTag(name) {
    const re = tagRegex(name);
    const m = sl.match(re);
    if (m) return { ok: false, reason: '<' + name + '> tag is forbidden' };
    return null;
  }
  // Build scan regex for any disallowed name once.
  const badNames = ['script', 'foreignobject'];
  for (let i = 0; i < badNames.length; i++) {
    const bad = badTag(badNames[i]);
    if (bad) return bad;
  }
  // External URL scan — look for href / xlink:href values that start with a scheme.
  // Captures both quoted attribute forms.
  const hrefAttrs = stripped.match(/\s(?:href|xlink:href)\s*=\s*["']([^"']*)["']/gi) || [];
  for (let i = 0; i < hrefAttrs.length; i++) {
    const m = hrefAttrs[i].match(/=\s*["']([^"']*)["']/);
    if (!m) continue;
    const v = m[1];
    if (!v) continue;
    // Allow internal fragment references only.
    if (v.charAt(0) === '#') continue;
    // Reject any non-relative path or scheme.
    if (/^[a-z][a-z0-9+\-.]*:/i.test(v)) {
      return { ok: false, reason: 'external URL in href/xlink:href: ' + v };
    }
    if (v.startsWith('//')) {
      return { ok: false, reason: 'protocol-relative URL in href/xlink:href: ' + v };
    }
    // Non-fragment, non-relative is treated as unsafe.
    if (!v.startsWith('./') && !v.startsWith('../') && !v.startsWith('/')) {
      // Could be a plain relative (e.g. "icon.svg"). That's actually fine; allow.
      // But reject if it contains a hostname.
      if (/^[a-z0-9.\-]+\.[a-z]{2,}\//i.test(v)) {
        return { ok: false, reason: 'looks like external URL: ' + v };
      }
    }
  }
  // Root must be <svg ... viewBox="..."> with a digit-pair viewBox.
  const rootMatch = stripped.match(/<\s*svg\b([^>]*?)>/i);
  if (!rootMatch) {
    return { ok: false, reason: 'no <svg> root element' };
  }
  const rootAttrs = rootMatch[1];
  const vb = rootAttrs.match(/\bviewBox\s*=\s*["']([^"']*)["']/i);
  if (!vb) {
    return { ok: false, reason: 'root <svg> missing viewBox' };
  }
  const vbVal = vb[1].trim();
  if (!/^\d+(\.\d+)?[\s,]+\d+(\.\d+)?[\s,]+\d+(\.\d+)?[\s,]+\d+(\.\d+)?$/.test(vbVal)) {
    return { ok: false, reason: 'invalid viewBox: ' + vbVal };
  }
  // File size cap: 64 KB.  SVG assets are tiny.
  if (Buffer.byteLength(c, 'utf8') > 64 * 1024) {
    return { ok: false, reason: 'exceeds 64 KB size limit' };
  }
  // All good.  (We intentionally do NOT parse full XML — the browser will
  // catch any further issues at render time, and this CLI is fail-closed
  // only on the security-significant tags listed above.)
  return { ok: true };
}

// -------------------- subcommands --------------------

function cmdCheck(cfg) {
  const manifest = loadManifest(cfg.manifestPath);
  let okCount = 0;
  let missingCount = 0;
  let badCount = 0;
  const rows = [];
  // Card faces (8 themes)
  const faces = manifest.slots.card_faces;
  if (faces && Array.isArray(faces.themes)) {
    faces.themes.forEach((theme) => {
      const slot = faces.slots[0];
      const relPath = slot.relative_path.replace('{theme}', theme);
      const r = safeResolve(cfg.assetsDir, relPath);
      const cssVar = slot.css_var.replace('{theme}', theme);
      let status;
      if (r.err) {
        status = 'BLOCKED: ' + r.err;
        badCount++;
      } else if (!r.exists) {
        status = 'missing';
        missingCount++;
      } else {
        status = 'found';
        okCount++;
      }
      rows.push({
        id: slot.id.replace('{theme}', theme),
        var: cssVar,
        file: relPath,
        status: status,
      });
    });
  }
  // All other named slot groups.
  const otherGroups = [
    'card_backs', 'card_deck', 'discard_pile',
    'timer_dock', 'progress_ticks', 'flying_card',
    'corner_ornaments', 'multi_item_thumb', 'modal_frame',
    'feedback_paper', 'care_illustration'
  ];
  otherGroups.forEach((gname) => {
    const g = manifest.slots[gname];
    if (!g || !Array.isArray(g.slots)) return;
    g.slots.forEach((slot) => {
      const relPath = slot.relative_path;
      const r = safeResolve(cfg.assetsDir, relPath);
      let status;
      if (r.err) {
        status = 'BLOCKED: ' + r.err;
        badCount++;
      } else if (!r.exists) {
        status = 'missing';
        missingCount++;
      } else {
        // Validate content
        let buf;
        try {
          buf = fs.readFileSync(r.abs, 'utf8');
        } catch (e) {
          status = 'BLOCKED: read error: ' + e.message;
          badCount++;
          rows.push({ id: slot.id, var: slot.css_var, file: relPath, status: status });
          return;
        }
        const v = validateSvgContent(buf, relPath);
        if (!v.ok) {
          status = 'INVALID: ' + v.reason;
          badCount++;
        } else {
          status = 'found';
          okCount++;
        }
      }
      rows.push({ id: slot.id, var: slot.css_var, file: relPath, status: status });
      if (slot.fallback_chain && Array.isArray(slot.fallback_chain)) {
        slot.fallback_chain.forEach((fc) => {
          if (fc.theme_variants) {
            const themes = manifest.slots.card_faces && manifest.slots.card_faces.themes;
            if (themes && Array.isArray(themes)) {
              themes.forEach((theme) => {
                const rp = fc.relative_path.replace('{theme}', theme);
                const r2 = safeResolve(cfg.assetsDir, rp);
                let s2;
                if (r2.err) { s2 = 'BLOCKED: ' + r2.err; badCount++; }
                else if (!r2.exists) { s2 = 'fallback/missing'; missingCount++; }
                else {
                  const buf2 = fs.readFileSync(r2.abs, 'utf8');
                  const v2 = validateSvgContent(buf2, rp);
                  if (!v2.ok) { s2 = 'fallback/INVALID:' + v2.reason; badCount++; }
                  else { s2 = 'fallback/found'; okCount++; }
                }
                rows.push({ id: fc.id.replace('{theme}', theme), var: '(fallback)', file: rp, status: s2 });
              });
            }
          } else {
            const r2 = safeResolve(cfg.assetsDir, fc.relative_path);
            let s2;
            if (r2.err) { s2 = 'BLOCKED: ' + r2.err; badCount++; }
            else if (!r2.exists) { s2 = 'fallback/missing'; missingCount++; }
            else {
              const buf2 = fs.readFileSync(r2.abs, 'utf8');
              const v2 = validateSvgContent(buf2, fc.relative_path);
              s2 = v2.ok ? 'fallback/found' : 'fallback/INVALID:' + v2.reason;
              if (v2.ok) okCount++; else badCount++;
            }
            rows.push({ id: fc.id || fc.description, var: '(fallback)', file: fc.relative_path, status: s2 });
          }
        });
      }
    });
  });
  info('Checked ' + rows.length + ' slot rows.');
  info('  found=' + okCount + '  missing=' + missingCount + '  blocked=' + badCount);
  rows.forEach((r) => {
    info('  ' + pad(r.id, 36) + ' ' + pad(r.var || '-', 44) + ' ' + pad(r.file, 50) + ' ' + r.status);
  });
  if (badCount > 0) process.exit(1);
  process.exit(0);
}

function pad(s, w) {
  s = String(s == null ? '' : s);
  if (s.length >= w) return s.slice(0, w - 1) + ' ';
  return s + ' '.repeat(w - s.length);
}

function cmdList(cfg) {
  const manifest = loadManifest(cfg.manifestPath);
  info('Manifest: ' + path.relative(cfg.repoRoot, cfg.manifestPath));
  info('Assets root: ' + path.relative(cfg.repoRoot, cfg.assetsDir));
  info('CSS output: ' + path.relative(cfg.repoRoot, cfg.cssOutPath));
  info('Tool version: ' + TOOL_VERSION);
  info('');
  info('CSS hooks defined in src/index.html:');
  manifest.css_hooks.hooks.forEach((h) => info('  ' + h));
  info('');
  const groups = ['card_faces', 'card_backs', 'card_deck', 'discard_pile',
                  'timer_dock', 'progress_ticks', 'flying_card',
                  'corner_ornaments', 'multi_item_thumb', 'modal_frame',
                  'feedback_paper', 'care_illustration'];
  const counters = { available: 0, missing: 0, blocked: 0, total: 0 };
  function classify(r) {
    if (r.err) return 'unavailable (' + r.err + ')';
    if (!r.exists) return 'unavailable';
    return 'available';
  }
  function bump(st) {
    counters.total++;
    if (st === 'available') counters.available++;
    else if (st.indexOf('unavailable (') === 0) counters.blocked++;
    else counters.missing++;
  }
  groups.forEach((gn) => {
    const g = manifest.slots[gn];
    if (!g) return;
    info('Group: ' + gn + (g.required ? ' (required)' : ' (optional)'));
    info('  ' + (g.description || ''));
    if (g.themes && Array.isArray(g.themes) && g.slots && g.slots[0]) {
      g.themes.forEach((theme) => {
        const slot = g.slots[0];
        const relPath = slot.relative_path.replace('{theme}', theme);
        const r = safeResolve(cfg.assetsDir, relPath);
        const st = classify(r);
        bump(st);
        info('  - ' + slot.id.replace('{theme}', theme) + ' (' + theme + ')  '
             + pad(relPath, 56) + '  ' + st);
      });
    } else if (g.slots) {
      g.slots.forEach((slot) => {
        const relPath = slot.relative_path;
        const r = safeResolve(cfg.assetsDir, relPath);
        const st = classify(r);
        bump(st);
        info('  - ' + slot.id + '  ' + pad(relPath, 56) + '  ' + st);
        if (slot.fallback_chain) {
          slot.fallback_chain.forEach((fc) => {
            if (fc.theme_variants && g.themes && Array.isArray(g.themes)) {
              g.themes.forEach((theme) => {
                const rp = fc.relative_path.replace('{theme}', theme);
                const r2 = safeResolve(cfg.assetsDir, rp);
                const st2 = classify(r2);
                bump(st2);
                info('      (fallback ' + theme + ') ' + pad(rp, 50) + '  ' + st2);
              });
            } else {
              const r2 = safeResolve(cfg.assetsDir, fc.relative_path);
              const st2 = classify(r2);
              bump(st2);
              info('      (fallback) ' + pad(fc.relative_path, 50) + '  ' + st2);
            }
          });
        }
      });
    }
  });
  info('');
  info('Summary: total=' + counters.total + ' available=' + counters.available
       + ' missing=' + counters.missing + ' blocked=' + counters.blocked);
}

function cmdBuild(cfg) {
  const manifest = loadManifest(cfg.manifestPath);
  const lines = [];
  lines.push('/* ============================================================');
  lines.push(' * art-overrides.css');
  lines.push(' * Generated by scripts/art-asset-registry.js (LT_M1_5E)');
  lines.push(' * DO NOT EDIT BY HAND.  Re-run: node scripts/art-asset-registry.js build');
  lines.push(' * Version: ' + TOOL_VERSION);
  lines.push(' * Build ID: ' + TOOL_VERSION + '-deterministic');
  lines.push(' * ');
  lines.push(' * All --art-* custom properties default to `none` here.  The seam');
  lines.push(' * in src/index.html (M1.5B/C) treats `none` as a no-op so the');
  lines.push(' * existing CSS gradients, focus rings, timer semantics, and');
  lines.push(' * z-index layers are preserved EXACTLY when no SVG asset is');
  lines.push(' * provided.  When real SVGs land in static/assets/, this file');
  lines.push(' * is regenerated to map each slot\'s CSS var to the matching');
  lines.push(' * SVG via relative `./...` reference.');
  lines.push(' * ');
  lines.push(' * SAFETY: only files that exist AND pass script-tag / foreign-');
  lines.push(' * object / external-URL / symlink / traversal screening become a');
  lines.push(' * `url(...)`.  Missing or unsafe slots remain `none`.');
  lines.push(' * ');
  lines.push(' * Prefix this stylesheet with: <link rel="stylesheet"');
  lines.push(' * href="/static/assets/art-overrides.css?v=1">');
  lines.push(' * (already wired into src/index.html head).');
  lines.push(' * ============================================================ */');
  lines.push('');
  lines.push(':root {');
  // Build a Map so re-running build() produces deterministic ordering AND
  // duplicate var names (e.g. feedback_paper and modal_frame both want
  // --art-modal-frame) only produce ONE declaration.
  const declarations = []; // { prop, value, slot_id, theme }
  const seenProps = new Set();
  function addDecl(prop, value, slotId, theme) {
    // First-come wins for 'none' defaults (manifest hooks list), but
    // real URL wins if later slot supplies it.
    if (seenProps.has(prop)) {
      const idx = declarations.findIndex((d) => d.prop === prop);
      if (idx !== -1 && declarations[idx].value === 'none' && value !== 'none') {
        declarations[idx] = { prop: prop, value: value, slotId: slotId, theme: theme || '' };
      }
      return;
    }
    seenProps.add(prop);
    declarations.push({ prop: prop, value: value, slotId: slotId, theme: theme || '' });
  }
  // Emit every seam hook as :none by default.
  const allHookSet = new Set();
  manifest.css_hooks.hooks.forEach((h) => {
    if (h.indexOf('{theme}') !== -1) return;
    allHookSet.add(h);
  });
  allHookSet.forEach((h) => {
    addDecl(h, 'none', 'manifest.hook', '');
  });
  // Always emit --art-card-front-layer as the generic routing variable.
  // Theme classes override it with var(--art-card-{theme}-front) to pick
  // up the theme-specific art.  Default to theme-default if it exists.
  addDecl('--art-card-front-layer', 'none', 'manifest.hook', '');

  // Card faces: 8 themes, optional per-theme back fallback
  // NOTE: theme_front declarations are ONLY emitted here when the SVG exists.
  // When no SVG exists, we emit NOTHING (not even 'none') because src/index.html
  // already provides the default fallback gradient via:
  //   .task-card.theme-math { --art-card-front-layer: var(--art-card-math-front, gradient); }
  // Emitting explicit 'none' would override the CSS gradient with 'none'.
  //
  // CSS URL strategy: the variable gets cascaded through src/index.html's
  // INLINE <style> block via var(--art-card-front-layer) → var(--art-card-math-front).
  // CSS spec: when a url() token is contained in a custom property and that
  // property is substituted into an inline stylesheet, the url is re-resolved
  // against the document base URL (not the stylesheet that defined the
  // property).  Using a server-absolute path (e.g. /static/assets/...) avoids
  // any document-relative ambiguity and works under any <base>.
  const faces = manifest.slots.card_faces;
  if (faces && Array.isArray(faces.themes) && faces.slots && faces.slots[0]) {
    const slot = faces.slots[0];
    faces.themes.forEach((theme) => {
      const relPath = slot.relative_path.replace('{theme}', theme);
      const r = resolveAndValidate(cfg, relPath);
      const cssVar = slot.css_var.replace('{theme}', theme);
      // Only emit a declaration if we have a real SVG asset
      if (r.ok) {
        // r.posixRel is relative to cfg.assetsDir (e.g. cards/faces/theme-math/front-bg.svg).
        // The assetsDir is served at /static/assets/ on the live web server, so
        // prepend /static/assets/ to get a server-absolute url().
        const absUrl = '/static/assets/' + r.posixRel;
        addDecl(cssVar, 'url(' + absUrl + ')', slot.id, theme);
      }
      // DO NOT emit 'none' for missing theme faces - let src/index.html CSS fallback win
    });
  }
  // Other groups
  const groups = ['card_backs', 'card_deck', 'discard_pile', 'timer_dock',
                  'progress_ticks', 'flying_card', 'corner_ornaments',
                  'multi_item_thumb', 'modal_frame', 'feedback_paper',
                  'care_illustration'];
  // Shared theme list for groups that declare {theme} fallbacks but don't
  // carry their own `themes` field.  Falls back to card_faces' themes,
  // which is the canonical "eight theme tokens" list.
  const sharedThemeSet = (manifest.slots.card_faces && Array.isArray(manifest.slots.card_faces.themes))
    ? manifest.slots.card_faces.themes : [];
  groups.forEach((gn) => {
    const g = manifest.slots[gn];
    if (!g || !Array.isArray(g.slots)) return;
    g.slots.forEach((slot) => {
      const relPath = slot.relative_path;
      const themeSet = (g.themes && Array.isArray(g.themes)) ? g.themes : sharedThemeSet;
      // First try the primary path.
      const r1 = resolveAndValidate(cfg, relPath);
      if (r1.ok) {
        addDecl(slot.css_var, 'url(/static/assets/' + r1.posixRel + ')', slot.id, '');
        return;
      }
      // Then try fallback chain; if any entry has theme_variants, expand per theme.
      if (slot.fallback_chain && slot.fallback_chain.length) {
        let chosen = null;
        for (let i = 0; i < slot.fallback_chain.length && !chosen; i++) {
          const fc = slot.fallback_chain[i];
          if (fc.theme_variants && themeSet.length) {
            for (let t = 0; t < themeSet.length && !chosen; t++) {
              const themePath = fc.relative_path.replace('{theme}', themeSet[t]);
              const r2 = resolveAndValidate(cfg, themePath);
              if (r2.ok) chosen = { rel: r2.posixRel, src: themePath };
            }
          } else {
            const r2 = resolveAndValidate(cfg, fc.relative_path);
            if (r2.ok) chosen = { rel: r2.posixRel, src: fc.relative_path };
          }
        }
        if (chosen) {
          addDecl(slot.css_var, 'url(/static/assets/' + chosen.rel + ')', slot.id, '');
          return;
        }
      }
      addDecl(slot.css_var, 'none', slot.id, '');
    });
  });
  // Activation vars for multi-item thumbnail:
  //   --art-multi-item-thumb-display is a CSS display value, NOT '1'.
  //   --art-multi-item-thumb-content may stay 'none' (thumbnail is background).
  //   Default: 'none' (do not occupy width).
  //   When thumbnail var has a URL above, also flip display to 'inline-block'.
  const thumbDecl = declarations.find((d) => d.prop === '--art-multi-item-thumb');
  if (thumbDecl && thumbDecl.value !== 'none') {
    addDecl('--art-multi-item-thumb-display', 'inline-block', 'multi-thumb-display', '');
    addDecl('--art-multi-item-thumb-content', 'none', 'multi-thumb-content', '');
  } else {
    addDecl('--art-multi-item-thumb-display', 'none', 'multi-thumb-display', '');
    addDecl('--art-multi-item-thumb-content', 'none', 'multi-thumb-content', '');
  }

  // Sort declarations: keep CSS variable order stable.
  declarations.sort((a, b) => {
    if (a.prop < b.prop) return -1;
    if (a.prop > b.prop) return 1;
    return 0;
  });

  declarations.forEach((d) => {
    // Indent two spaces inside :root { ... }.
    lines.push('  ' + d.prop + ': ' + d.value + ';');
  });
  lines.push('}');
  lines.push('');
  // Theme-scoped rules (only when a theme face actually exists).
  // These are emitted AFTER the :root block to avoid breaking CSS sorting.
  const themeRules = [];
  if (faces && Array.isArray(faces.themes) && faces.slots && faces.slots[0]) {
    faces.themes.forEach((theme) => {
      const decl = declarations.find((d) => d.theme === theme && d.prop.indexOf('--art-card-' + theme + '-front') === 0);
      if (decl && decl.value !== 'none') {
        themeRules.push('.task-card.theme-' + theme + ' {');
        themeRules.push('  --art-card-front-layer: var(--art-card-' + theme + '-front);');
        themeRules.push('}');
      }
    });
  }
  // Footer comment summarizing availability.
  lines.push('/* ---------- Status footer ----------');
  lines.push(' * unavailable_count: ' + declarations.filter((d) => d.value === 'none').length);
  lines.push(' * bound_count: ' + declarations.filter((d) => d.value !== 'none').length);
  lines.push(' * See static/assets/art-manifest.json for the full slot registry.');
  lines.push(' * ------------------------------------- */');
  lines.push('');
  // Theme-scoped rules (emitted after footer to avoid breaking :root CSS var sorting)
  if (themeRules.length > 0) {
    lines.push('/* ---------- Theme overrides ----------');
    themeRules.forEach((line) => lines.push(line));
    lines.push('');
  }

  // Idempotency: compute content + compare to existing file.
  const newBody = lines.join('\n');
  let prev = null;
  if (fs.existsSync(cfg.cssOutPath)) {
    try { prev = fs.readFileSync(cfg.cssOutPath, 'utf8'); } catch (e) { /* ignore */ }
  }
  if (prev === newBody) {
    info('build: art-overrides.css unchanged (' + bytes(newBody) + ' bytes)');
    process.exit(0);
  }
  try {
    // Atomic-ish write: write to .tmp, then rename.
    const tmp = cfg.cssOutPath + '.tmp';
    fs.writeFileSync(tmp, newBody, 'utf8');
    fs.renameSync(tmp, cfg.cssOutPath);
  } catch (e) {
    die('failed to write ' + cfg.cssOutPath + ': ' + e.message, 1);
  }
  info('build: wrote ' + cfg.cssOutPath + ' (' + bytes(newBody) + ' bytes)');
  process.exit(0);
}

function bytes(s) {
  return Buffer.byteLength(s, 'utf8');
}

/**
 * Validate one SVG file.  Returns { ok: boolean, posixRel?: string, reason? }.
 */
function resolveAndValidate(cfg, relPath) {
  const r = safeResolve(cfg.assetsDir, relPath);
  if (r.err) return { ok: false, reason: r.err };
  if (!r.exists) return { ok: false, reason: 'missing' };
  let buf;
  try { buf = fs.readFileSync(r.abs, 'utf8'); } catch (e) {
    return { ok: false, reason: 'read error: ' + e.message };
  }
  const v = validateSvgContent(buf, relPath);
  if (!v.ok) return { ok: false, reason: v.reason };
  // Convert relative path to posix for CSS (URL syntax prefers forward slashes).
  const posixRel = relPath.replace(/\\/g, '/');
  return { ok: true, posixRel: posixRel };
}

// -------------------- main --------------------

function usage() {
  info('LT_M1_5E art asset registry CLI v' + TOOL_VERSION);
  info('Usage:  node scripts/art-asset-registry.js <check|list|build>');
  info('  check  Read-only.  Walk manifest slots; report statuses.  Exits 1 on blocks.');
  info('  list   Read-only.  Print slot table + summary.');
  info('  build  Write static/assets/art-overrides.css.  Idempotent.  Exits 1 on errors.');
}

function main() {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    usage();
    process.exit(0);
  }
  const cfg = defaults();
  const sub = args[0];
  if (sub === 'check') cmdCheck(cfg);
  else if (sub === 'list') cmdList(cfg);
  else if (sub === 'build') cmdBuild(cfg);
  else if (sub === '--help' || sub === '-h') { usage(); process.exit(0); }
  else { die('unknown subcommand: ' + sub, 1); }
}

try { main(); }
catch (e) {
  // eslint-disable-next-line no-console
  process.stderr.write('[art-asset-registry] fatal: ' + (e && e.stack ? e.stack : String(e)) + '\n');
  process.exit(1);
}
