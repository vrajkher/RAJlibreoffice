import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { chromium } from 'playwright';
const html=await readFile('../src/raj_libreoffice/panel.html');
const host=`<!doctype html><iframe id="panel" src="/panel" style="width:1100px;height:1500px;border:0"></iframe><script>
let docs=[],files=[],next=1;window.calls=[];
const workspace=()=>({documents:docs.map(x=>({...x})),files:files.map(path=>({path,bytes:100}))});
function tool(name,args){window.calls.push({name,args});let value;const doc=docs.find(x=>x.document===args.document);
if(name==='office_workspace')return workspace();
if(name==='document_create'){value={document:'doc'+next++,kind:args.kind,path:null};docs.push(value);}
else if(name==='writer_insert'){doc.text=(doc.text||'')+args.text;value={inserted_characters:args.text.length};}
else if(name==='writer_read')value={text:doc.text||''};
else if(name==='calc_read')value={data:[['Name','Value'],['UNO','=2+3']]};
else if(name==='calc_write')value={written_cells:4};
else if(name==='document_save'){doc.path=args.path;files.push(args.path);value={saved:true,path:args.path};}
else if(name==='document_close'){docs=docs.filter(x=>x.document!==args.document);value={closed:true};}
else throw Error('Unexpected tool '+name);
return {result:value};}
window.addEventListener('message',event=>{const r=event.data;if(event.source!==document.getElementById('panel').contentWindow)return;
const reply=result=>event.source.postMessage({jsonrpc:'2.0',id:r.id,result},'*');
if(r.method==='ui/initialize')reply({protocolVersion:r.params.protocolVersion,hostInfo:{name:'test-host',version:'1'},hostCapabilities:{serverTools:{}},hostContext:{displayMode:'inline',theme:'light'}});
else if(r.method==='ui/notifications/initialized')event.source.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-result',params:{content:[],structuredContent:workspace()}},'*');
else if(r.method==='tools/call'){try{reply({content:[],structuredContent:tool(r.params.name,r.params.arguments)});}catch(e){reply({isError:true,content:[{type:'text',text:e.message}]});}}
else if(r.id!==undefined)reply({});
});</script>`;
const server=createServer((req,res)=>{res.setHeader('Content-Type','text/html');res.end(req.url==='/panel'?html:host);});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const browser=await chromium.launch({headless:true,...(process.env.RAJ_CHROMIUM_EXECUTABLE?{executablePath:process.env.RAJ_CHROMIUM_EXECUTABLE}:{})});
try{
 const page=await browser.newPage();page.on('console',msg=>{if(msg.type()==='error')console.error(msg.text());});const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto(`http://127.0.0.1:${server.address().port}`);const panel=page.frameLocator('#panel');
 await panel.locator('#create').click();try{await panel.locator('#selection').filter({hasText:'writer'}).waitFor({timeout:5000});}catch(error){console.error(await panel.locator('#message').textContent());console.error(await page.evaluate(()=>window.calls));console.error(errors);throw error;}
 await panel.locator('#text').fill('Hello from the panel');await panel.locator('#apply').click();
 await panel.locator('#preview').filter({hasText:'Hello from the panel'}).waitFor();
 await panel.locator('#path').fill('panel.odt');await panel.locator('#save').click();
 await panel.locator('#files button').filter({hasText:'panel.odt'}).waitFor();
 await panel.locator('#close').click();await panel.locator('#selection').filter({hasText:'Choose a document first'}).waitFor();
 await panel.locator('#kind').selectOption('calc');await panel.locator('#create').click();
 await panel.locator('#selection').filter({hasText:'calc'}).waitFor();await panel.locator('#range').fill('A1:B2');await panel.locator('#read').click();
 await panel.locator('#grid input').nth(3).waitFor();assert.equal(await panel.locator('#grid input').nth(3).inputValue(),'=2+3');
 await panel.locator('#grid input').nth(3).fill('=2+4');await panel.locator('#cells').click();
 await panel.locator('#message').filter({hasText:'Done.'}).waitFor();
 let writes=await page.evaluate(()=>window.calls.filter(x=>x.name==='calc_write'));assert.equal(writes.at(-1).args.formulas,true);assert.equal(writes.at(-1).args.data[1][1],'=2+4');
 await panel.locator('#range').fill('C1:D2');await panel.locator('#cells').click();await panel.locator('#message').filter({hasText:'Read it again'}).waitFor();
 assert.equal((await page.evaluate(()=>window.calls.filter(x=>x.name==='calc_write'))).length,writes.length);
 assert.deepEqual(errors,[]);console.log('Panel passed: create, append, read, save, close, formula editing and stale-range protection.');
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
