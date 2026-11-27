const fs=require('fs');
const realCli=fs.readFileSync('scripts/art-asset-registry.js','utf8');
const normCli=realCli.replace(/\r\n/g,'\n');
const out=normCli.replace(/assetsDir:\s*path\.join\(repoRoot\(\),\s*'static',\s*'assets'\s*\)/, 'XXX_REPLACED_XXX');
console.log('replaced:', out.indexOf('XXX_REPLACED_XXX') !== -1);
const stillHas = normCli.indexOf("assetsDir: path.join(repoRoot(), 'static', 'assets'),") !== -1;
console.log('original has it:', stillHas);
const out2 = out.indexOf("assetsDir: path.join(repoRoot(), 'static', 'assets'),") !== -1;
console.log('after replace still has:', out2);
