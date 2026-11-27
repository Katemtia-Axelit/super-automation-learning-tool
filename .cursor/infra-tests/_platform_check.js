// Simulate the ubuntu-latest CI environment for the guard: the only
// platform-dependent branch was caseFold(), which is now unconditional.
// This test proves the fix by forcing platform to a non-Windows value.
const path = require('path');
const fs = require('fs');
const { spawnSync } = require('child_process');

const HOOK = path.join(__dirname, '..', 'hooks', 'redline-guard.js');
const FIXTURES = path.join(__dirname, 'redline-guard', 'fixtures');

// The guard reads process.platform at call time inside isWindows().
// We cannot change process.platform from outside, so instead we assert
// the *source* no longer gates case folding on the platform, and we
// re-run the full fixture matrix through a platform-shimmed copy.
const src = fs.readFileSync(HOOK, 'utf8');

if (/caseFold[\s\S]{0,200}isWindows\(\)/.test(src)) {
  console.error('FAIL: caseFold still depends on isWindows()');
  process.exit(1);
}
console.log('OK: caseFold is platform-independent');

// Now run the full harness in a child process where process.platform is
// stubbed to 'linux' before the guard module loads.
const shim = path.join(__dirname, '_platform_shim.js');
fs.writeFileSync(shim, "Object.defineProperty(process, 'platform', {value: 'linux'});\n");

const harness = path.join(__dirname, 'redline-guard', 'harness.js');
const r = spawnSync(process.execPath, ['-r', shim, harness], {
  encoding: 'utf8',
});
fs.unlinkSync(shim);

const out = (r.stdout || '') + (r.stderr || '');
const m = out.match(/Total:\s*(\d+)\s+Pass:\s*(\d+)\s+Fail:\s*(\d+)\s+Error:\s*(\d+)/);
if (!m) {
  console.error('FAIL: could not parse harness summary');
  console.error(out.split('\n').slice(-15).join('\n'));
  process.exit(1);
}
console.log(`linux-simulated harness: Total=${m[1]} Pass=${m[2]} Fail=${m[3]} Error=${m[4]}`);
if (m[3] !== '0' || m[4] !== '0') {
  console.error(out.split('\n').filter(l => l.includes('FAIL')).join('\n'));
  process.exit(1);
}
console.log('OK: guard behaves identically on a non-Windows platform');
