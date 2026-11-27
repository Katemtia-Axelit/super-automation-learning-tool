// Direct check: just import the spec and run buildMiniBundle with mocked fs.
const fs = require('fs');
const path = require('path');

const specCode = fs.readFileSync(path.join(__dirname, 'tests/e2e/gacha-multidraw-safe.spec.js'), 'utf-8');

const startMatch = specCode.match(/function extractFunction/);
const endMarker = 'const MINIBUNDLE = buildMiniBundle();';
const endIdx = specCode.indexOf(endMarker) + endMarker.length;
const startIdx = startMatch.index;
const fnCode = specCode.substring(startIdx, endIdx);

const wrapped = fnCode + '\nreturn MINIBUNDLE;';
const APP_JS_PATH = path.join(__dirname, 'static', 'app.js');
const MINIBUNDLE = new Function('fs', 'path', 'APP_JS_PATH', wrapped)(fs, path, APP_JS_PATH);
console.log('--- bundle length:', MINIBUNDLE.length);
try { new Function(MINIBUNDLE); console.log('PARSE OK'); }
catch(e) { console.log('PARSE ERR:', e.message); }
console.log('--- bundle last 300 chars ---');
console.log(MINIBUNDLE.slice(-300));
console.log('--- lines containing await ---');
MINIBUNDLE.split('\n').forEach((line, i) => {
  if (line.includes('await')) console.log(i+1, line);
});
