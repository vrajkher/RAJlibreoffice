import { App } from '@modelcontextprotocol/ext-apps';
import { OpenAIExtensions } from '@openai/mcp-extensions/app';
const app = new App({name:'RAJ LibreOffice',version:'0.2.0'});
new OpenAIExtensions(app);
const el = id => document.getElementById(id);
let docs=[], selected='', grid=[], gridContext=null;
const native={writer:'odt',calc:'ods',impress:'odp',draw:'odg',math:'odf',base:'odb'};
async function call(name,args={}){
 const output=await app.callServerTool({name,arguments:args});
 if(output.isError) throw new Error(output.content?.filter(x=>x.type==='text').map(x=>x.text).join('\n')||'Operation failed');
 let data=output.structuredContent;
 if(!data){const item=output.content?.find(x=>x.type==='text');if(item)data=JSON.parse(item.text);}
 return data?.result ?? data;
}
async function act(fn){
 document.querySelectorAll('button').forEach(x=>x.disabled=true);
 el('message').textContent='Working…';
 try{await fn();el('message').textContent='Done.';}catch(e){el('message').textContent=e.message;}
 finally{document.querySelectorAll('button').forEach(x=>x.disabled=false);}
}
function current(){const doc=docs.find(x=>x.document===selected);if(!doc)throw new Error('Choose a document first.');return doc;}
function choose(id){selected=id;el('documents').value=id;const doc=docs.find(x=>x.document===id);el('selection').textContent=doc?`${doc.kind} · ${doc.path||'Unsaved document'}`:'Choose a document first.';el('preview').textContent='';el('grid').replaceChildren();grid=[];gridContext=null;el('cells').hidden=doc?.kind!=='calc';if(doc)el('path').value=doc.path?doc.path.split(/[\\/]/).pop():`document.${native[doc.kind]}`;}
function workspace(data){
 docs=data.documents;el('status').textContent=`${docs.length} open document(s)`;
 const select=el('documents');select.replaceChildren(new Option('Choose an open document',''));
 docs.forEach(doc=>select.add(new Option(`${doc.kind}: ${doc.path||'Unsaved'}`,doc.document)));
 el('files').replaceChildren();
 data.files.forEach(file=>{const button=document.createElement('button');button.textContent=file.path;button.addEventListener('click',()=>act(async()=>{const result=await call('document_open',{path:file.path});await refresh();choose(result.document);await read();}));el('files').append(button);});
 el('empty').textContent=data.files.length?'':'No files in the workspace yet. Create a document below.';
 choose(docs.some(x=>x.document===selected)?selected:'');
}
async function refresh(){workspace(await call('office_workspace'));}
async function read(){
 const doc=current();let value;
 if(doc.kind==='writer')value=await call('writer_read',{document:selected,length:20000});
 else if(doc.kind==='calc'){
  const data=await call('calc_read',{document:selected,sheet:Number(el('sheet').value),range:el('range').value,formulas:true});
  if(data.data.reduce((n,row)=>n+row.length,0)>400)throw new Error('Use a smaller range: the panel shows up to 400 cells.');
  gridContext={document:selected,sheet:Number(el('sheet').value),range:el('range').value};
  const table=document.createElement('table');grid=data.data.map(row=>{const tr=document.createElement('tr');const inputs=row.map(value=>{const td=document.createElement('td'),input=document.createElement('input');input.value=value;input.dataset.originalType=typeof value;input.setAttribute('aria-label',`Cell row ${table.rows.length+1}, column ${tr.cells.length+1}`);td.append(input);tr.append(td);return input;});table.append(tr);return inputs;});el('grid').replaceChildren(table);value={message:'Cell values and formulas are shown below. Edit them, then apply cell edits.'};
 }else if(doc.kind==='impress'||doc.kind==='draw')value=await call('presentation_read',{document:selected,page:0});
 else if(doc.kind==='math')value=await call('math_formula',{document:selected});
 else value=await call('base_configure',{document:selected});
 el('preview').textContent=value.text??JSON.stringify(value,null,2);
}
app.ontoolresult=result=>{const data=result.structuredContent?.result??result.structuredContent;if(data?.files&&data?.documents)workspace(data);};
el('refresh').onclick=()=>act(refresh);
el('documents').onchange=()=>choose(el('documents').value);
el('create').onclick=()=>act(async()=>{const result=await call('document_create',{kind:el('kind').value});await refresh();choose(result.document);});
el('read').onclick=()=>act(read);
el('apply').onclick=()=>act(async()=>{const doc=current(),text=el('text').value;if(!text)throw new Error('Enter text first.');if(doc.kind==='writer')await call('writer_insert',{document:selected,text});else if(doc.kind==='impress'||doc.kind==='draw')await call('presentation_shape',{document:selected,page:0,text});else if(doc.kind==='math')await call('math_formula',{document:selected,formula:text});else throw new Error('Use cell edits for Calc or ask the assistant for database operations.');el('text').value='';await read();});
el('cells').onclick=()=>act(async()=>{current();if(!grid.length)throw new Error('Read a cell range first.');if(gridContext.document!==selected||gridContext.sheet!==Number(el('sheet').value)||gridContext.range!==el('range').value)throw new Error('The sheet or range changed. Read it again before applying edits.');await call('calc_write',{...gridContext,formulas:true,data:grid.map(row=>row.map(input=>input.value))});await read();});
el('save').onclick=()=>act(async()=>{current();await call('document_save',{document:selected,path:el('path').value,overwrite:el('overwrite').checked});await refresh();});
el('pdf').onclick=()=>act(async()=>{current();const path=el('path').value.replace(/\.[^.]+$/,'')+'.pdf';await call('document_save',{document:selected,path,format:'pdf',export:true,overwrite:el('overwrite').checked});await refresh();});
el('close').onclick=()=>act(async()=>{current();await call('document_close',{document:selected});selected='';await refresh();});
document.querySelectorAll('button').forEach(x=>x.disabled=true);
try { await app.connect(); document.querySelectorAll('button').forEach(x=>x.disabled=false); }
catch(error) { el('message').textContent='Unable to connect to the host: '+error.message; }
