import { build } from 'esbuild';
import { readFile, readdir, writeFile } from 'node:fs/promises';
const result = await build({entryPoints:['panel.js'],bundle:true,minify:true,format:'esm',write:false,target:'es2022',legalComments:'inline',metafile:true});
const html = (await readFile('panel.html','utf8')).replace('<!-- SCRIPT -->', () => '<script type="module">' + result.outputFiles[0].text.replaceAll('</script', '<\\/script') + '</script>');
await writeFile('../src/raj_libreoffice/panel.html', html);
const packages=new Set();
for(const input of Object.keys(result.metafile.inputs)){
 if(!input.includes('node_modules/'))continue;
 const relative=input.split('node_modules/').at(-1).split('/');
 packages.add('node_modules/'+(relative[0].startsWith('@')?relative.slice(0,2).join('/'):relative[0]));
}
let notices='Client libraries bundled in the RAJ LibreOffice workspace panel\n\n';
for(const path of [...packages].sort()){
 const info=JSON.parse(await readFile(path+'/package.json','utf8'));
 notices+=`${info.name} ${info.version} (${info.license||'See license below'})\n`;
 for(const name of (await readdir(path)).filter(x=>/^(license|copying|notice)(\.|$)/i.test(x)).sort()){
  notices+=await readFile(path+'/'+name,'utf8');notices+='\n';
 }
 notices+='\n';
}
await writeFile('../src/raj_libreoffice/THIRD_PARTY_NOTICES.txt',notices);
