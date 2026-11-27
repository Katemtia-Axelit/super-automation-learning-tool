#!/usr/bin/env node
/**
 * probe-skill-manifest.js
 * Read-only Node probe: validates skill manifests and required paths.
 * Exit 0 = all checks pass, Exit != 0 = failure.
 */

const fs = require('fs');
const path = require('path');

const PROJECT_ROOT = path.resolve(__dirname, '../../..');

const REQUIRED_SKILLS = [
  { relPath: '.cursor/skills/inspect-project-state/SKILL.md', contractId: 'LT_INSPECT_STATE_V1' },
  { relPath: '.cursor/skills/verify-current-behavior/SKILL.md', contractId: 'LT_VERIFY_BEHAVIOR_V1' }
];

const REQUIRED_RULES = ['.cursor/rules/runtime-cwd.mdc', '.cursor/rules/data-redlines.mdc'];
const REQUIRED_DOCS = ['docs/CURRENT_PROJECT_STATE.md', 'docs/ARCHITECTURE.md'];

function readFrontmatter(content) {
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!match) return {};
  const fm = {};
  match[1].split(/\r?\n/).forEach(line => {
    const [key, ...rest] = line.split(':');
    if (key && rest.length > 0) fm[key.trim()] = rest.join(':').trim();
  });
  return fm;
}

let failures = [];
console.log('=== Skill Manifest Probe ===\n');

for (const skill of REQUIRED_SKILLS) {
  const fullPath = path.join(PROJECT_ROOT, skill.relPath);
  console.log('Checking: ' + skill.relPath);
  if (!fs.existsSync(fullPath)) {
    failures.push('MISSING: ' + skill.relPath);
    continue;
  }
  const content = fs.readFileSync(fullPath, 'utf-8');
  const fm = readFrontmatter(content);
  const missing = [];
  if (!fm.name) missing.push('name');
  if (!fm.description) missing.push('description');
  if (fm['disable-model-invocation'] !== 'true') missing.push('disable-model-invocation');
  if (missing.length > 0) failures.push(skill.relPath + ': missing ' + missing.join(', '));
  if (!content.includes(skill.contractId)) failures.push(skill.relPath + ': missing ' + skill.contractId);
  console.log('  name: ' + (fm.name || '(MISSING)'));
  console.log('  disable-model-invocation: ' + (fm['disable-model-invocation'] || '(MISSING)'));
  console.log('  contract: ' + skill.contractId + ' ' + (content.includes(skill.contractId) ? 'OK' : 'FAIL'));
}

console.log('\nChecking rule files:');
for (const rule of REQUIRED_RULES) {
  const fullPath = path.join(PROJECT_ROOT, rule);
  console.log('  ' + rule + ': ' + (fs.existsSync(fullPath) ? 'exists' : 'MISSING'));
  if (!fs.existsSync(fullPath)) failures.push('MISSING: ' + rule);
}

console.log('\nChecking skill-referenced docs:');
for (const doc of REQUIRED_DOCS) {
  const fullPath = path.join(PROJECT_ROOT, doc);
  console.log('  ' + doc + ': ' + (fs.existsSync(fullPath) ? 'exists' : 'MISSING'));
  if (!fs.existsSync(fullPath)) failures.push('MISSING: ' + doc);
}

console.log('\n=== Summary ===');
if (failures.length === 0) {
  console.log('All checks PASSED (exit 0)');
  process.exit(0);
} else {
  console.log('FAILURES (' + failures.length + '):');
  failures.forEach(function(f) { console.log('  - ' + f); });
  process.exit(1);
}
