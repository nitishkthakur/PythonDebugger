// Optional developer checks: node --test tests/editor.test.cjs
// Uses only Node built-ins; the application itself needs only Python.
// This small DOM double checks editing transactions, not browser rendering.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname,'..','debugger.py'),'utf8');
const html = source.match(/PAGE_HTML = r"""([\s\S]*)"""\s*\n\s*if __name__/)[1];
const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m=>m[1]);

function editor(text = '', readonly = false) {
  const ids = new Map(), frames = [], calls = [];
  let doc;
  class Element {
    constructor(tag) {
      this.tagName=tag; this.children=[]; this.style={setProperty(){},removeProperty(){}}; this.dataset={}; this.attributes={}; this.listeners={};
      this._text=''; this._value=''; this._id=''; this.className=''; this.selectionStart=this.selectionEnd=0;
      this.scrollTop=this.scrollLeft=this.offsetLeft=0; this.clientHeight=300; this.clientWidth=600;
      this.classList={contains:k=>this.className.split(' ').includes(k),add:(...ks)=>this.className=[...new Set([...this.className.split(' '),...ks])].join(' '),remove:(...ks)=>this.className=this.className.split(' ').filter(k=>!ks.includes(k)).join(' ')};
    }
    set id(v) { this._id=v; ids.set(v,this); } get id(){return this._id;}
    set value(v) { this._value=String(v); } get value(){return this._value;}
    set textContent(v) { for(const e of [...this.children]) e.remove(); this._text=v; } get textContent(){return this._text;}
    get lastChild(){return this.children.at(-1);}
    get firstChild(){return this.children[0];}
    appendChild(e) { if(e.tagName==='#fragment') {for(const c of [...e.children]) this.appendChild(c);return e;} if(e.parentNode) e.parentNode.children=e.parentNode.children.filter(c=>c!==e);this.children.push(e);e.parentNode=this;return e; }
    insertBefore(e,ref) { const i=this.children.indexOf(ref);this.children.splice(i<0?this.children.length:i,0,e);e.parentNode=this;return e; }
    remove(){for(const c of [...this.children]) c.remove();if(this.parentNode)this.parentNode.children=this.parentNode.children.filter(c=>c!==this);if(this.id)ids.delete(this.id);}
    setAttribute(k,v){this.attributes[k]=v;}
    addEventListener(k,fn){(this.listeners[k]||=[]).push(fn);}
    walk(){return this.children.flatMap(e=>[e,...e.walk()]);}
    matches(s){return s.startsWith('#')?this.id===s.slice(1):s.startsWith('.')?this.classList.contains(s.slice(1)):this.tagName===s;}
    querySelectorAll(s){return this.walk().filter(e=>s.split(',').some(k=>e.matches(k)));}
    querySelector(s){return this.querySelectorAll(s)[0]||null;}
    closest(s){return this.matches(s)?this:this.parentNode?.closest(s)||null;}
    focus(){doc.activeElement=this;} select(){this.setSelectionRange(0,this.value.length);}
    setSelectionRange(s,e){this.selectionStart=Math.max(0,Math.min(s,this.value.length));this.selectionEnd=Math.max(this.selectionStart,Math.min(e,this.value.length));}
    setRangeText(t,s,e){assert(s>=0&&s<=e&&e<=this.value.length);this.value=this.value.slice(0,s)+t+this.value.slice(e);this.setSelectionRange(s+t.length,s+t.length);}
    scrollIntoView(){} getBoundingClientRect(){return {top:0,bottom:20,height:20};}
    getContext(){return {measureText:()=>({width:8})};} click(){this.onclick?.();}
  }
  doc={body:new Element('body'),documentElement:new Element('html'),listeners:{},
    createElement:t=>new Element(t),createDocumentFragment:()=>new Element('#fragment'),createTextNode:t=>{const e=new Element('#text');e.textContent=t;return e;},
    querySelector:s=>s.startsWith('#')?ids.get(s.slice(1))||null:null,querySelectorAll:()=>[],
    getElementById:id=>ids.get(id)||null,addEventListener(k,fn){(this.listeners[k]||=[]).push(fn);}};
  for(const m of html.matchAll(/id="([^"]+)"/g)){const e=new Element('div');e.id=m[1];}
  doc.body.appendChild(ids.get('editor')); ids.get('editor').appendChild(ids.get('code'));
  const prefs={font_size:14,font:'default',line:'normal',theme:'light',accent:'#d71e28',editor_theme:'match',editor_colors:{}};
  const ctx=vm.createContext({document:doc,window:{addEventListener(){}},location:{search:'?t=test'},URLSearchParams,Blob,URL,
    EventSource:class{},setTimeout:()=>1,clearTimeout(){},confirm:()=>true,prompt:()=>null,
    requestAnimationFrame:fn=>{frames.push(fn);return frames.length;},getComputedStyle:()=>({font:'14px monospace',lineHeight:'20',paddingLeft:'8',maxHeight:'110'}),
    fetch:async(url,opts)=>{calls.push({url,body:opts?.body&&JSON.parse(opts.body)});return {json:async()=>({ok:true})};}});
  vm.runInContext(scripts[0].replace('__BOOT__',JSON.stringify({prefs})),ctx);
  vm.runInContext(scripts[1],ctx);
  const run=code=>vm.runInContext(code,ctx), flush=()=>{while(frames.length)frames.shift()();};
  function file(name,value,ro=false){ctx.fixture={name,value,ro};run(String.raw`S.files.set(fixture.name,{path:fixture.name,text:fixture.value,saved:fixture.value,readonly:fixture.ro,lines:fixture.value.split('\n'),html:highlight(fixture.value),selection:[0,0],history:[{text:fixture.value,selection:[0,0]}],historyIndex:0});S.tabs.push(fixture.name);S.active=fixture.name;renderTabs();renderCode();`);flush();}
  file('/test.py',text,readonly);
  const ta=()=>ids.get('edta'), select=(s,e=s)=>{ta().setSelectionRange(s,e);run('updateCursor()');};
  function key(key,extra={}){ctx.event={key,code:key,ctrlKey:false,metaKey:false,altKey:false,shiftKey:false,...extra,target:ta(),preventDefault(){this.defaultPrevented=true;},stopPropagation(){}};run('onEdKey(event)');flush();return ctx.event;}
  function type(value){ctx.typed=value;run(`{const inputTarget=$('#edta'); S.files.get(S.active).beforeSelection=[inputTarget.selectionStart,inputTarget.selectionEnd];inputTarget.setRangeText(typed,inputTarget.selectionStart,inputTarget.selectionEnd,'end');onEdInput({target:inputTarget,inputType:'insertText'});}`);flush();}
  return {run,flush,ctx,ids,ta,select,key,type,file,calls};
}

test('typing groups undo, redo branches, and history survives switching files',()=>{
  const e=editor('x = ');e.select(4);e.type('1');e.type('2');assert.equal(e.ta().value,'x = 12');
  e.run('undoEdit()');assert.equal(e.ta().value,'x = ');e.run('undoEdit(true)');assert.equal(e.ta().value,'x = 12');
  e.file('/other.py','other');e.run("S.active='/test.py';renderCode();undoEdit();");assert.equal(e.ta().value,'x = ');
  e.type('3');e.run('undoEdit(true)');assert.equal(e.ta().value,'x = 3');
});
test('comments, selected-line indentation, duplication and line movement are reversible',()=>{
  const e=editor('a\n    b\nc\n');e.select(0,2);e.run('indentLines()');assert.equal(e.ta().value,'    a\n    b\nc\n');
  e.run('toggleComments()');assert.equal(e.ta().value,'    # a\n    b\nc\n');e.run('toggleComments()');assert.equal(e.ta().value,'    a\n    b\nc\n');
  e.select(0);e.run('moveLines(true)');assert.equal(e.ta().value,'    b\n    a\nc\n');e.run('undoEdit()');assert.equal(e.ta().value,'    a\n    b\nc\n');
  e.select(e.ta().value.length-2);e.run('duplicateLines()');assert.equal(e.ta().value,'    a\n    b\nc\nc\n');
});
test('pairing, empty backspace, strings, comments and indented newline',()=>{
  const e=editor();assert(!e.key('Backspace').defaultPrevented);e.key('(');assert.equal(e.ta().value,'()');assert.equal(e.ta().selectionStart,1);
  e.key('Enter');assert.equal(e.ta().value,'(\n    \n)');e.run('undoEdit()');e.key('Backspace');assert.equal(e.ta().value,'');
  e.file('/string.py','"value"');e.select(3);assert(!e.key('(').defaultPrevented);
  e.file('/comment.py','# comment');e.select(9);assert(!e.key('[').defaultPrevented);
  e.file('/block.py','if enabled:');e.select(11);e.key('Enter');assert.equal(e.ta().value,'if enabled:\n    ');
});
test('literal and regex search, captures, zero-width handling and safe highlighting',()=>{
  const e=editor('a = 1\na = 2\n<tag>');e.ids.get('findtext').value='a';e.run('openFind(true)');assert.equal(e.run('FIND.hits.length'),3);
  e.ids.get('findword').checked=true;e.run('refreshFind()');assert.equal(e.run('FIND.hits.length'),2);
  e.ids.get('replacetext').value='$&';e.run('replaceMatches(true)');assert.equal(e.ta().value,'$& = 1\n$& = 2\n<tag>');e.run('undoEdit()');
  e.ids.get('findword').checked=false;e.ids.get('findregex').checked=true;e.ids.get('findtext').value='(a) = (\\d)';e.ids.get('replacetext').value='$2 = $1';e.run('refreshFind();replaceMatches(true)');assert.equal(e.ta().value,'1 = a\n2 = a\n<tag>');
  e.ids.get('findtext').value='[';e.run('refreshFind()');assert.equal(e.run('FIND.error'),'Invalid regex');
  assert.equal(e.run("replaceNonempty('abc',/(?:)/g,'X',false)"),'abc');
  const markup=e.run("highlight('<tag>',[{start:0,end:5}],0).join('')");assert(!markup.includes('<tag>'));assert.equal(markup.replace(/<[^>]*>/g,''),'&lt;tag&gt;');
});
test('read-only code rejects edits, replacements, history and completion',()=>{
  const e=editor('original',true);e.select(0,8);e.run('toggleComments();indentLines();duplicateLines();undoEdit();suggestWords()');assert.equal(e.ta().value,'original');
  e.ids.get('findtext').value='original';e.ids.get('replacetext').value='changed';e.run('openFind(true);replaceMatches(true)');assert.equal(e.ta().value,'original');
});
test('word suggestions insert only the selected prefix and undo as one edit',()=>{
  const e=editor('customer_total = 10\ncust');e.select(e.ta().value.length);e.run('suggestWords()');assert.equal(e.run('COMPLETE.items[0]'),'customer_total');
  e.key('Enter');assert.equal(e.ta().value,'customer_total = 10\ncustomer_total');e.run('undoEdit()');assert.equal(e.ta().value,'customer_total = 10\ncust');
});
test('saving a snapshot preserves edits made while the save request is pending',async()=>{
  const e=editor('x');e.select(1);e.type('1');let release;
  e.ctx.fetch=async()=>({json:()=>new Promise(resolve=>release=resolve)});
  const saving=e.run('saveFile(S.files.get(S.active))');await new Promise(setImmediate);e.type('2');release({ok:true});await saving;
  assert.equal(e.run('S.files.get(S.active).saved'),'x1');assert.equal(e.ta().value,'x12');assert.equal(e.run('S.files.get(S.active).dirty'),true);
});
test('navigation wraps, replacing one respects captures, and go-to clamps line/column',()=>{
  const e=editor('one 12\none 34\n');e.ids.get('findtext').value='one';e.run('openFind();nextMatch(false,true)');assert.equal(e.ta().selectionStart,0);
  e.run('nextMatch(false,true)');assert.equal(e.ta().selectionStart,7);e.run('nextMatch(false,true)');assert.equal(e.ta().selectionStart,0);
  e.ids.get('findregex').checked=true;e.ids.get('findtext').value='one (\\d+)';e.ids.get('replacetext').value='value=$1';e.run('refreshFind();replaceMatches(false)');assert.equal(e.ta().value,'value=12\none 34\n');
  e.ctx.prompt=()=> '2:3';e.run('goToLine()');assert.equal(e.ta().selectionStart,11);
  e.ctx.prompt=()=> '999:999';e.run('goToLine()');assert.equal(e.ta().selectionStart,e.ta().value.length);
});
test('empty leading lines indent and move correctly; triple-string content is not paired',()=>{
  const e=editor('\na');e.select(0);e.key('Tab');assert.equal(e.ta().value,'    \na');e.run('undoEdit()');e.select(1);e.run('moveLines(false)');assert.equal(e.ta().value,'a\n');
  e.file('/doc.py','"""\ntext\n"""');e.select(6);assert(!e.key('[').defaultPrevented);
});
test('capture replacement expansion matches native JavaScript and skips empty matches',()=>{
  const e=editor();
  for(const replacement of ['$$','$&','$1','$2','$12','$01',"$`|$'",'$<first>']){
    e.ctx.repl=replacement;
    assert.equal(e.run("replaceNonempty('a1 b2',/(?<first>[a-z])(\\d)/g,repl,false)"),e.run("'a1 b2'.replace(/(?<first>[a-z])(\\d)/g,repl)"));
  }
  assert.equal(e.run("replaceNonempty('aba',/a|(?=b)/g,'X',false)"),'XbX');
});
test('save all skips read-only buffers and saved edits remain undoable',async()=>{
  const e=editor('x');e.select(1);e.type('1');e.file('/two.py','y');e.select(1);e.type('2');
  e.run("S.files.set('/library.py',{path:'/library.py',readonly:true,dirty:true,text:'read-only'});");
  await e.run('saveAll()');assert.equal(e.calls.filter(c=>c.url==='/api/save').length,2);
  assert.equal(e.run('[...S.files.values()].some(f=>f.dirty&&!f.readonly)'),false);e.run('undoEdit()');assert.equal(e.ta().value,'y');assert.equal(e.run('S.files.get(S.active).dirty'),true);
});
