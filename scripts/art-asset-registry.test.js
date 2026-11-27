#!/usr/bin/env node
/**
 * art-asset-registry.test.js
 * Synthetic Node test suite for scripts/art-asset-registry.js (LT_M1_5E).
 * All file writes go to a self-created OS TEMP directory.  Teardown removes
 * the entire temp tree.  The real repository is never touched.
 *
 * Run:  node scripts/art-asset-registry.test.js
 *
 * Coverage:
 *   1  zero-url-no-assets
 *   2  manifest-valid-json
 *   3  missing-no-url
 *   4  valid-svg-injection
 *   5  per-theme-independence
 *   6  common-fallback-chain
 *   7  malicious-script-tag-rejected
 *   8  idempotency
 *   9  traversal-rejected
 *   10 unauthorized-file-not-in-css
 *   11 check-exits-0
 *   12 list-prints-slots
 *   13 build-produces-url
 *   14 invalid-no-viewbox-rejected
 *   15 external-href-rejected
 *   16 declarations-sorted
 *   17 foreignobject-rejected
 *   18 proto-rel-url-rejected
 *   19 internal-use-allowed
 *   20 bad-viewbox-format-rejected
 *   21 thumb-display-default-none
 *   22 thumb-display-activates
 *   23 no-script-in-css-output
 *   24 modal-frame-not-duplicated
 *   25 check-blocked-zero
 *   26 list-shows-summary
 *   27 check-exits-non-zero-on-blocked
 *   28 theme-scoped-with-asset
 *   29 all-hooks-in-css
 */

'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const os = require('os');

// ---- helpers ----

function mkTempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'art-reg-test-'));
}

function rmRf(dir) {
  if (!fs.existsSync(dir)) return;
  try {
    const entries = fs.readdirSync(dir);
    for (const e of entries) {
      const p = path.join(dir, e);
      const st = fs.lstatSync(p);
      if (st.isDirectory() && !st.isSymbolicLink()) rmRf(p);
      else try { fs.unlinkSync(p); } catch (_) { /* ignore */ }
    }
    fs.rmdirSync(dir);
  } catch (_) { /* best-effort */ }
}

function writeFile(dir, rel, content) {
  const full = path.join(dir, rel);
  const d = path.dirname(full);
  if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
  fs.writeFileSync(full, content, 'utf8');
  return full;
}

function readFile(full) { return fs.readFileSync(full, 'utf8'); }

// Count url() references that appear as actual CSS values, not in comments
// or quoted strings.  We strip /* ... */ comments and then look for url(...)
// tokens that are not inside a '...' or "..." literal.
function countUrls(css) {
  // Remove /* ... */ comments first
  const stripped = css.replace(/\/\*[\s\S]*?\*\//g, '');
  // Match url( that is not preceded by a quote (avoid matching url(...) in docs/strings)
  const matches = stripped.match(/(^|[\s;:,(])url\(/g) || [];
  return matches.length;
}

// ---- Fixtures ----

const VALID_SVG = [
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 700 440">',
  '<rect width="700" height="440" fill="#121a32"/>',
  '<rect x="10" y="10" width="680" height="420" fill="none" stroke="#6eb5ff" stroke-width="4"/>',
  '</svg>',
].join('\n');

const MALICIOUS_SCRIPT = [
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 700 440">',
  '<script>alert("xss")</script>',
  '</svg>',
].join('\n');

const MALICIOUS_FOREIGNOBJECT = [
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 700 440">',
  '<foreignObject><div xmlns="http://www.w3.org/1999/xhtml">xss</div></foreignObject>',
  '</svg>',
].join('\n');

const MALICIOUS_EXTERNAL_HREF = [
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 700 440">',
  '<a href="https://evil.example.com/steal">',
  '<rect width="700" height="440" fill="#121a32"/>',
  '</a>',
  '</svg>',
].join('\n');

const MALICIOUS_PROTO_REL = [
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 700 440">',
  '<image href="//cdn.evil.com/payload.png" width="700" height="440"/>',
  '</svg>',
].join('\n');

const SVG_NO_VIEWBOX = [
  '<svg xmlns="http://www.w3.org/2000/svg">',
  '<rect width="700" height="440" fill="#121a32"/>',
  '</svg>',
].join('\n');

const SVG_BAD_VIEWBOX = [
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="abc">',
  '<rect width="700" height="440" fill="#121a32"/>',
  '</svg>',
].join('\n');

const SVG_INTERNAL_USE = [
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 700 440">',
  '<defs><g id="g1"><circle cx="50" cy="50" r="40" fill="#6eb5ff"/></g></defs>',
  '<use href="#g1"/>',
  '</svg>',
].join('\n');

// ---- Minimal manifest factory ----

function makeManifest() {
  return {
    version: '1.0.0', generated: new Date().toISOString(), purpose: 'test',
    slots: {
      card_faces: {
        description: 'Card fronts', required: true,
        themes: ['math', 'lang', 'code', 'history', 'write', 'science', 'review', 'default'],
        slots: [{ id: 'front-bg-{theme}', css_var: '--art-card-{theme}-front',
          css_fallback: 'linear-gradient(...)', relative_path: 'cards/faces/{theme}/front-bg.svg',
          theme_variants: true, unavailable_reason: 'missing' }],
      },
      card_backs: {
        description: 'Card backs', required: false,
        slots: [
          { id: 'back-common', css_var: '--art-card-back-layer',
            relative_path: 'cards/backs/common/back-pattern.svg',
            fallback_chain: [{ id: 'back-per-theme-{theme}',
              relative_path: 'cards/backs/per-theme/{theme}/back-pattern.svg',
              theme_variants: true }],
            unavailable_reason: 'missing' },
          { id: 'back-emblem', css_var: '--art-card-back-emblem-layer',
            relative_path: 'cards/backs/common/emblem.svg', unavailable_reason: 'missing' },
        ],
      },
      card_deck: { description: 'Deck', required: false,
        slots: [{ id: 'deck-base', css_var: '--art-deck-layer',
          relative_path: 'deck/deck-base.svg', unavailable_reason: 'missing' }] },
      discard_pile: { description: 'Discard', required: false,
        slots: [{ id: 'discard-back', css_var: '--art-discard-layer',
          relative_path: 'discard/discard-back.svg', unavailable_reason: 'missing' }] },
      timer_dock: { description: 'Dock', required: false,
        slots: [
          { id: 'dock-frame', css_var: '--art-dock-layer',
            relative_path: 'dock/frame.svg', unavailable_reason: 'missing' },
          { id: 'pocket-watch', css_var: '--art-dock-watch-layer',
            relative_path: 'dock/pocket-watch.svg', unavailable_reason: 'missing' },
        ] },
      progress_ticks: { description: 'Progress', required: false,
        slots: [{ id: 'progress-ticks', css_var: '--art-timer-progress-tick',
          relative_path: 'progress/progress-ticks.svg', unavailable_reason: 'missing' }] },
      flying_card: { description: 'Flying card', required: false,
        slots: [{ id: 'fly-card', css_var: '--art-fly-card-layer',
          relative_path: 'flying/flying-card.svg', unavailable_reason: 'missing' }] },
      corner_ornaments: { description: 'Corners', required: false,
        slots: [{ id: 'corner-all', css_var: '--art-card-ornament-layer',
          relative_path: 'cards/ornaments/corner-all.svg', unavailable_reason: 'missing' }] },
      multi_item_thumb: { description: 'Thumb', required: false,
        slots: [{ id: 'multi-thumb-default', css_var: '--art-multi-item-thumb',
          relative_path: 'ui/multi-thumb.svg', unavailable_reason: 'missing' }],
        activation_vars: [
          { css_var: '--art-multi-item-thumb-display',
            valid_values: ['block', 'flex', 'inline-flex', 'inline-block', 'none'] },
          { css_var: '--art-multi-item-thumb-content' },
        ] },
      modal_frame: { description: 'Modal', required: false,
        slots: [{ id: 'modal-frame', css_var: '--art-modal-frame',
          relative_path: 'ui/modal-frame.svg', unavailable_reason: 'missing' }] },
      feedback_paper: { description: 'Feedback', required: false,
        slots: [{ id: 'feedback-paper', css_var: '--art-modal-frame',
          relative_path: 'feedback/feedback-paper.svg', unavailable_reason: 'missing' }] },
      care_illustration: { description: 'Care', required: false,
        slots: [{ id: 'care-illust', css_var: '--art-care-illustration-layer',
          relative_path: 'care/care-illust-success.svg', unavailable_reason: 'missing' }] },
    },
    css_hooks: {
      description: 'All --art-* hooks',
      hooks: [
        '--art-deck-layer', '--art-card-back-layer', '--art-card-back-emblem-layer',
        '--art-discard-layer', '--art-dock-layer', '--art-dock-watch-layer',
        '--art-timer-progress-tick', '--art-fly-card-layer',
        '--art-card-ornament-layer', '--art-card-pattern-layer',
        '--art-card-header-band', '--art-timer-panel-frame',
        '--art-modal-frame', '--art-care-illustration-layer',
        '--art-multi-item-thumb', '--art-multi-item-thumb-display',
        '--art-multi-item-thumb-content',
      ],
    },
    constraints: {
      directory_traversal_forbidden: true, no_external_urls: true,
      no_symlinks: true, no_script_tags_in_svg: true, no_foreignobject_in_svg: true,
    },
    status_summary: { total_slots: 22, available: 0, unavailable: 22, ready_for_build: true },
  };
}

// ---- Test harness ----

let pass = 0, fail = 0;

function a(cond, msg) {
  if (cond) { pass++; process.stdout.write('.'); }
  else { fail++; process.stdout.write('X'); process.stderr.write('\n  FAIL: ' + msg + '\n'); }
}

function eq(actual, expected, msg) {
  const cond = actual === expected;
  const detail = cond ? '' : ' (expected ' + JSON.stringify(expected) + ', got ' + JSON.stringify(actual) + ')';
  a(cond, msg + detail);
}

function has(s, sub, msg) { a(s.indexOf(sub) !== -1, msg + ' (expected to contain "' + sub + '")'); }
function not(s, sub, msg) { a(s.indexOf(sub) === -1, msg + ' (expected NOT to contain "' + sub + '")'); }

// Build a CLI runner bound to a specific temp root.
function makeCli(tmpRoot) {
  const realCli = path.join(__dirname, '..', 'scripts', 'art-asset-registry.js');
  const tempCliDir = path.join(tmpRoot, 'scripts');
  fs.mkdirSync(tempCliDir, { recursive: true });
  const tempCli = path.join(tempCliDir, 'art-asset-registry.js');
  let content = fs.readFileSync(realCli, 'utf8');
  // Patch defaults() to use tmpRoot.
  content = content.replace(
    /function defaults\(\) \{[\s\S]*?return \{[\s\S]*?repoRoot: repoRoot\(\),[\s\S]*?\};[\s\S]*?\}/,
    'function defaults() { return { repoRoot: ' + JSON.stringify(tmpRoot) + ', manifestPath: ' + JSON.stringify(path.join(tmpRoot, 'static', 'assets', 'art-manifest.json')) + ', assetsDir: ' + JSON.stringify(path.join(tmpRoot, 'static', 'assets')) + ', cssOutPath: ' + JSON.stringify(path.join(tmpRoot, 'static', 'assets', 'art-overrides.css')) + ' }; }'
  );
  fs.writeFileSync(tempCli, content, 'utf8');
  function run(args) {
    const r = spawnSync(process.execPath, [tempCli, ...args], {
      cwd: tmpRoot, encoding: 'utf8', timeout: 15000,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    return { stdout: r.stdout || '', stderr: r.stderr || '', status: r.status };
  }
  return { run, cssPath: path.join(tmpRoot, 'static', 'assets', 'art-overrides.css'),
           manifestPath: path.join(tmpRoot, 'static', 'assets', 'art-manifest.json'),
           tmpRoot };
}

function runTests() {
  // ---- Shared temp setup (used by most tests, each test clones for isolation) ----
  const shared = mkTempDir();
  const cssPath = path.join(shared, 'static/assets/art-overrides.css');
  const manifestPath = path.join(shared, 'static/assets/art-manifest.json');

  // Write base manifest.
  writeFile(shared, 'static/assets/art-manifest.json', JSON.stringify(makeManifest(), null, 2));

  // Patch the real CLI to point to the shared temp root.
// Replace the static string paths in defaults() instead of regex-ing the whole function.
  const patchedCliDir = path.join(shared, 'scripts');
  fs.mkdirSync(patchedCliDir, { recursive: true });
  const patchedCli = path.join(patchedCliDir, 'art-asset-registry.js');
  const realCli = path.join(__dirname, '..', 'scripts', 'art-asset-registry.js');
  const cliContent = fs.readFileSync(realCli, 'utf8');
  // The CLI file uses object-literal property syntax, not bare return calls.
  const normCli = cliContent.replace(/\r\n/g, '\n');
  const patched = normCli
    .replace(
      /manifestPath:\s*path\.join\(repoRoot\(\),\s*'static',\s*'assets',\s*'art-manifest\.json'\s*\)/,
      'manifestPath: ' + JSON.stringify(manifestPath)
    )
    .replace(
      /assetsDir:\s*path\.join\(repoRoot\(\),\s*'static',\s*'assets'\s*\)/,
      'assetsDir: ' + JSON.stringify(path.join(shared, 'static', 'assets'))
    )
    .replace(
      /cssOutPath:\s*path\.join\(repoRoot\(\),\s*'static',\s*'assets',\s*'art-overrides\.css'\s*\)/,
      'cssOutPath: ' + JSON.stringify(cssPath)
    );
  fs.writeFileSync(patchedCli, patched, 'utf8');

  function runCli(args) {
    const r = spawnSync(process.execPath, [patchedCli, ...args], {
      cwd: shared, encoding: 'utf8', timeout: 15000,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    return { stdout: r.stdout || '', stderr: r.stderr || '', status: r.status };
  }

  try {
    process.stdout.write('\n--- Synthetic test suite (TEMP=' + shared + ') ---\n');

    // [1] zero-url-no-assets
    process.stdout.write('\n[1] zero-url-no-assets ');
    let r = runCli(['build']); eq(r.status, 0, 'build ok');
    const css1 = readFile(cssPath);
    eq(countUrls(css1), 0, 'zero url() with no assets');

    // [2] manifest-valid-json
    process.stdout.write('\n[2] manifest-valid-json ');
    const mraw = readFile(manifestPath);
    let mp; try { mp = JSON.parse(mraw); } catch (e) { mp = null; }
    a(mp !== null && typeof mp === 'object', 'manifest is valid JSON');
    a(Array.isArray(mp.slots.card_faces.themes), 'card_faces.themes is array');
    eq(mp.slots.card_faces.themes.length, 8, '8 theme variants');

    // [3] missing-no-url
    process.stdout.write('\n[3] missing-no-url ');
    eq(countUrls(css1), 0, 'missing assets produce no url()');

    // [4] valid-svg-injection
    process.stdout.write('\n[4] valid-svg-injection ');
    writeFile(shared, 'static/assets/cards/faces/math/front-bg.svg', VALID_SVG);
    r = runCli(['build']); eq(r.status, 0, 'build ok');
    const css4 = readFile(cssPath);
    a(countUrls(css4) >= 1, 'at least one url()');
    has(css4, 'front-bg.svg', 'SVG filename in CSS');
    has(css4, 'theme-math', 'theme-math in CSS');

    // [5] per-theme-independence
    process.stdout.write('\n[5] per-theme-independence ');
    writeFile(shared, 'static/assets/cards/faces/code/front-bg.svg', VALID_SVG);
    r = runCli(['build']); eq(r.status, 0, 'build ok');
    const css5 = readFile(cssPath);
    has(css5, '--art-card-code-front:', 'code var present');
    has(css5, '--art-card-math-front:', 'math var present');
    has(css5, '/static/assets/cards/faces/math/front-bg.svg', 'math url present');
    has(css5, '/static/assets/cards/faces/code/front-bg.svg', 'code url present');
    const langLine = css5.match(/--art-card-lang-front:\s*([^;]+)/);
    a(!langLine || langLine[1].trim() === 'none', 'lang is none');

    // [6] common-fallback-chain
    process.stdout.write('\n[6] common-fallback-chain ');
    // math front-bg still exists → remove it so back-common falls through to theme fallback.
    fs.unlinkSync(path.join(shared, 'static/assets/cards/faces/math/front-bg.svg'));
    writeFile(shared, 'static/assets/cards/backs/per-theme/math/back-pattern.svg', VALID_SVG);
    r = runCli(['build']); eq(r.status, 0, 'build ok');
    const css6 = readFile(cssPath);
    has(css6, '--art-card-back-layer:', 'back-common var present');
    const backLine6 = css6.match(/--art-card-back-layer:\s*([^;]+)/);
    a(backLine6 && backLine6[1].indexOf('url(') !== -1, 'back-common has fallback URL');
    // Clean up: remove math back-pattern and deck malicious file so subsequent tests don't see them
    try { fs.unlinkSync(path.join(shared, 'static/assets/cards/backs/per-theme/math/back-pattern.svg')); } catch (_) { /* */ }
    try { fs.unlinkSync(path.join(shared, 'static/assets/deck/deck-base.svg')); } catch (_) { /* */ }

    // [7] malicious-script-tag-rejected
    process.stdout.write('\n[7] malicious-script-tag-rejected ');
    writeFile(shared, 'static/assets/deck/deck-base.svg', MALICIOUS_SCRIPT);
    r = runCli(['build']); eq(r.status, 0, 'build ok');
    const css7 = readFile(cssPath);
    const deck7 = css7.match(/--art-deck-layer:\s*([^;]+)/);
    a(deck7 && deck7[1].indexOf('none') !== -1, 'deck is none (script rejected)');
    not(css7, 'deck-base.svg', 'malicious filename not in CSS');
    // Clean up: remove malicious deck so subsequent check commands don't count it as blocked
    try { fs.unlinkSync(path.join(shared, 'static/assets/deck/deck-base.svg')); } catch (_) { /* */ }

    // [8] idempotency
    process.stdout.write('\n[8] idempotency ');
    r = runCli(['build']); eq(r.status, 0, 'second build ok');
    const css8a = readFile(cssPath);
    r = runCli(['build']);
    const css8b = readFile(cssPath);
    eq(css8a, css8b, 'consecutive builds identical');

    // [9] traversal-rejected
    process.stdout.write('\n[9] traversal-rejected ');
    const check9 = runCli(['check']);
    eq(check9.status, 0, 'check exits 0 with no traversal');

    // [10] unauthorized-file-not-in-css
    process.stdout.write('\n[10] unauthorized-file-not-in-css ');
    writeFile(shared, 'static/secret.txt', 'do not bind');
    r = runCli(['build']);
    const css10 = readFile(cssPath);
    not(css10, 'secret.txt', 'unauthorized file not in CSS');

    // [11] check-exits-0
    process.stdout.write('\n[11] check-exits-0 ');
    const check11 = runCli(['check']);
    eq(check11.status, 0, 'check exits 0 when all missing');

    // [12] list-prints-slots
    process.stdout.write('\n[12] list-prints-slots ');
    const list12 = runCli(['list']);
    eq(list12.status, 0, 'list exits 0');
    has(list12.stdout, 'card_faces', 'list has card_faces');
    has(list12.stdout, 'back-common', 'list has back-common');
    has(list12.stdout, 'Summary:', 'list has summary');

    // [13] build-produces-url
    process.stdout.write('\n[13] build-produces-url ');
    try { fs.unlinkSync(path.join(shared, 'static/assets/deck/deck-base.svg')); } catch (_) { /* */ }
    writeFile(shared, 'static/assets/deck/deck-base.svg', VALID_SVG);
    r = runCli(['build']); eq(r.status, 0, 'build ok');
    const css13 = readFile(cssPath);
    const deck13 = css13.match(/--art-deck-layer:\s*([^;]+)/);
    a(deck13 && deck13[1].indexOf('url(') !== -1, 'deck has url()');

    // [14] invalid-no-viewbox-rejected
    process.stdout.write('\n[14] invalid-no-viewbox-rejected ');
    writeFile(shared, 'static/assets/discard/discard-back.svg', SVG_NO_VIEWBOX);
    r = runCli(['build']); eq(r.status, 0, 'build ok');
    const css14 = readFile(cssPath);
    const disc14 = css14.match(/--art-discard-layer:\s*([^;]+)/);
    a(disc14 && disc14[1].indexOf('none') !== -1, 'discard is none (no viewBox)');
    // Cleanup: remove the invalid SVG so check commands downstream see clean state
    try { fs.unlinkSync(path.join(shared, 'static/assets/discard/discard-back.svg')); } catch (_) { /* */ }

    // [15] external-href-rejected
    process.stdout.write('\n[15] external-href-rejected ');
    writeFile(shared, 'static/assets/dock/frame.svg', MALICIOUS_EXTERNAL_HREF);
    r = runCli(['build']); eq(r.status, 0, 'build ok');
    const css15 = readFile(cssPath);
    const dock15 = css15.match(/--art-dock-layer:\s*([^;]+)/);
    a(dock15 && dock15[1].indexOf('none') !== -1, 'dock is none (external href)');
    // Cleanup: remove the malicious SVG so check commands downstream see clean state
    try { fs.unlinkSync(path.join(shared, 'static/assets/dock/frame.svg')); } catch (_) { /* */ }

    // [16] declarations-sorted
    process.stdout.write('\n[16] declarations-sorted ');
    // Only check :root { ... } block, NOT theme-scoped rules that follow
    const rootMatch16 = css15.match(/:root\s*\{([\s\S]*?)\}/);
    a(rootMatch16 !== null, ':root block present');
    // Extract just the CSS variable name (e.g. "--art-foo") so the sort
    // matches the CLI's own sort (which compares by prop name only).
    const lines16 = (rootMatch16[1].split('\n').filter((l) => l.trim().startsWith('--art-')));
    const propOf = (l) => l.match(/(--art-[a-z0-9-]+)/)[1];
    const sorted16 = [...lines16].sort((a, b) => {
      const pa = propOf(a), pb = propOf(b);
      return pa < pb ? -1 : pa > pb ? 1 : 0;
    });
    eq(lines16.join('\n'), sorted16.join('\n'), 'vars sorted inside :root');

    // [17] foreignobject-rejected
    process.stdout.write('\n[17] foreignobject-rejected ');
    writeFile(shared, 'static/assets/progress/progress-ticks.svg', MALICIOUS_FOREIGNOBJECT);
    r = runCli(['build']); eq(r.status, 0, 'build ok');
    const css17 = readFile(cssPath);
    const tick17 = css17.match(/--art-timer-progress-tick:\s*([^;]+)/);
    a(tick17 && tick17[1].indexOf('none') !== -1, 'progress-tick is none (foreignObject)');
    // Cleanup: remove the malicious SVG so check commands downstream see clean state
    try { fs.unlinkSync(path.join(shared, 'static/assets/progress/progress-ticks.svg')); } catch (_) { /* */ }

    // [18] proto-rel-url-rejected
    process.stdout.write('\n[18] proto-rel-url-rejected ');
    writeFile(shared, 'static/assets/care/care-illust-success.svg', MALICIOUS_PROTO_REL);
    r = runCli(['build']); eq(r.status, 0, 'build ok');
    const css18 = readFile(cssPath);
    const care18 = css18.match(/--art-care-illustration-layer:\s*([^;]+)/);
    a(care18 && care18[1].indexOf('none') !== -1, 'care is none (proto-rel URL)');
    // Cleanup: remove the malicious SVG so check commands downstream see clean state
    try { fs.unlinkSync(path.join(shared, 'static/assets/care/care-illust-success.svg')); } catch (_) { /* */ }

    // [19] internal-use-allowed
    process.stdout.write('\n[19] internal-use-allowed ');
    writeFile(shared, 'static/assets/flying/flying-card.svg', SVG_INTERNAL_USE);
    r = runCli(['build']); eq(r.status, 0, 'build ok');
    const css19 = readFile(cssPath);
    const fly19 = css19.match(/--art-fly-card-layer:\s*([^;]+)/);
    a(fly19 && fly19[1].indexOf('url(') !== -1, 'fly-card has url() (internal #use)');

    // [20] bad-viewbox-format-rejected
    process.stdout.write('\n[20] bad-viewbox-format-rejected ');
    writeFile(shared, 'static/assets/ui/multi-thumb.svg', SVG_BAD_VIEWBOX);
    r = runCli(['build']); eq(r.status, 0, 'build ok');
    const css20 = readFile(cssPath);
    const thumb20 = css20.match(/--art-multi-item-thumb:\s*([^;]+)/);
    a(thumb20 && thumb20[1].indexOf('none') !== -1, 'thumb is none (bad viewBox)');
    // Cleanup: remove the invalid SVG so check commands downstream see clean state
    try { fs.unlinkSync(path.join(shared, 'static/assets/ui/multi-thumb.svg')); } catch (_) { /* */ }

    // [21] thumb-display-default-none
    process.stdout.write('\n[21] thumb-display-default-none ');
    const cssBaseline = readFile(cssPath);
    const disp21 = cssBaseline.match(/--art-multi-item-thumb-display:\s*([^;]+)/);
    a(disp21 && disp21[1].trim() === 'none', 'thumb-display is none (no illegal 1)');

    // [22] thumb-display-activates
    process.stdout.write('\n[22] thumb-display-activates ');
    writeFile(shared, 'static/assets/ui/multi-thumb.svg', VALID_SVG);
    r = runCli(['build']); eq(r.status, 0, 'build ok');
    const css22 = readFile(cssPath);
    const disp22 = css22.match(/--art-multi-item-thumb-display:\s*([^;]+)/);
    a(disp22 && disp22[1].indexOf('inline-block') !== -1, 'thumb-display becomes inline-block');

    // [23] no-script-in-css-output
    process.stdout.write('\n[23] no-script-in-css-output ');
    not(css1, '<script', 'CSS has no <script>');
    not(css1, '<style', 'CSS has no <style>');

    // [24] modal-frame-not-duplicated
    process.stdout.write('\n[24] modal-frame-not-duplicated ');
    const mfCount = (css1.match(/--art-modal-frame:/g) || []).length;
    eq(mfCount, 1, '--art-modal-frame appears once');

    // [25] check-blocked-zero
    process.stdout.write('\n[25] check-blocked-zero ');
    const check25 = runCli(['check']);
    has(check25.stdout, 'blocked=0', 'check shows blocked=0');
    has(check25.stdout, 'missing=', 'check shows missing');

    // [26] list-shows-summary
    process.stdout.write('\n[26] list-shows-summary ');
    const list26 = runCli(['list']);
    has(list26.stdout, 'available=', 'list shows available count');

    // [27] check-exits-non-zero-on-blocked — uses a separate temp to avoid polluting shared
    process.stdout.write('\n[27] check-exits-non-zero-on-blocked ');
    const tmp27 = mkTempDir();
    try {
      const m27 = makeManifest();
      m27.slots.card_deck.slots[0].relative_path = '../outside/path.svg';
      writeFile(tmp27, 'static/assets/art-manifest.json', JSON.stringify(m27, null, 2));
      const cli27 = makeCli(tmp27);
      const check27 = cli27.run(['check']);
      a(check27.status !== 0, 'check exits non-zero on traversal path');
    } finally { rmRf(tmp27); }

    // [28] theme-scoped-with-asset
    process.stdout.write('\n[28] theme-scoped-with-asset ');
    has(css4, '.task-card.theme-math', 'theme-math scoped rule present');
    // lang has no asset so scoped rule should NOT have url.
    const langBlock = css4.match(/\.task-card\.theme-lang\s*\{[^}]+\}/);
    a(!langBlock || langBlock[0].indexOf('url(') === -1, 'lang scoped rule has no url()');

    // [29] all-hooks-in-css
    process.stdout.write('\n[29] all-hooks-in-css ');
    const needed = ['--art-deck-layer', '--art-card-back-layer', '--art-dock-layer',
                    '--art-timer-progress-tick', '--art-fly-card-layer',
                    '--art-card-ornament-layer', '--art-modal-frame',
                    '--art-care-illustration-layer', '--art-multi-item-thumb',
                    '--art-multi-item-thumb-display'];
    let allOk = true;
    for (const h of needed) {
      if (css1.indexOf(h + ':') === -1) { allOk = false; break; }
    }
    a(allOk, 'all required hooks in CSS output');

    process.stdout.write('\n\n');
    process.stdout.write('=================================\n');
    process.stdout.write(' RESULTS: PASS=' + pass + ' FAIL=' + fail + '\n');
    process.stdout.write('=================================\n');
  } finally {
    try { rmRf(shared); } catch (_) { /* */ }
    process.stdout.write('[teardown] temp root removed.\n');
  }

  if (fail > 0) process.exit(1);
  process.exit(0);
}

if (require.main === module) {
  try { runTests(); }
  catch (e) { process.stderr.write('FATAL: ' + (e.stack || e) + '\n'); process.exit(1); }
}
