const fs = require('fs');
const path = require('path');
const appJs = fs.readFileSync(path.join(__dirname, 'static', 'app.js'), 'utf-8');

function extractFunction(source, name) {
  const re = new RegExp('function\\s+' + name + '\\s*\\([^)]*\\)\\s*\\{');
  const m = source.match(re);
  if (!m) return null;
  let depth = 0;
  for (let i = m.index + m[0].length - 1; i < source.length; i += 1) {
    const ch = source[i];
    if (ch === '{') depth += 1;
    else if (ch === '}') { depth -= 1; if (depth === 0) return source.slice(m.index, i + 1); }
  }
  return null;
}
function extractAsyncFunction(source, name) {
  const re = new RegExp('async\\s+function\\s+' + name + '\\s*\\([^)]*\\)\\s*\\{');
  const m = source.match(re);
  if (!m) return null;
  let depth = 0;
  for (let i = m.index + m[0].length - 1; i < source.length; i += 1) {
    const ch = source[i];
    if (ch === '{') depth += 1;
    else if (ch === '}') { depth -= 1; if (depth === 0) return source.slice(m.index, i + 1); }
  }
  return null;
}
const rmr = extractFunction(appJs, 'renderMultiResults');
const amc = extractFunction(appJs, 'activateMultiCard');
const dgm = extractAsyncFunction(appJs, 'drawGachaMulti');
console.log('rmr length:', rmr.length, 'starts:', rmr.slice(0, 50));
console.log('amc length:', amc.length, 'starts:', amc.slice(0, 50));
console.log('dgm length:', dgm.length, 'starts:', dgm.slice(0, 50));
console.log('dgm ends:', dgm.slice(-50));

const bundle = rmr + '\n' + amc + '\n' + dgm;
console.log('bundle length:', bundle.length);
try { new Function(bundle); console.log('3-fn bundle parse OK'); }
catch(e) { console.log('3-fn bundle ERR:', e.message); }

const api = `async function api(url, opts) {
  opts = opts || {};
  var r = await fetch(url, Object.assign({ headers: { 'Content-Type': 'application/json' } }, opts));
  var data = {};
  try { data = await r.json(); } catch(e) {}
  return data;
}`;
const fullBundle = api + '\n' + bundle;
console.log('full bundle length:', fullBundle.length);
try { new Function(fullBundle); console.log('full bundle parse OK'); }
catch(e) { console.log('full bundle ERR:', e.message); }
