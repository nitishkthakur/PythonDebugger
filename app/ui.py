"""Local debugger browser page and embedded help; no remote assets."""

PAGE_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>debugger.py</title>
<style>
:root{--fs:14px;--lh:20px;--left:250px;--right:380px;--cons:210px;
 --mono:Consolas,Menlo,"DejaVu Sans Mono",monospace;
 --bg:#ececec;--pn:#fff;--bd:#b4b4b4;--tx:#1c1c1c;--dim:#777;--hd:#dcdcdc;--hv:#f0f0f0;--gut:#f4f4f4;--gbd:#ddd;
 --btn:#e2e2e2;--btnh:#d0d0d0;--btnbd:#888;--inp:#fff;--sub:#f3f3f3;--spl:#c4c4c4;--cd:#f0f0f0;--sel:#d4d4d4;--off:#aaa;
 --kw:#000;--st:#666;--cm:#999;--nm:#333;
 --ac:#d71e28;--ac-d:#a3141c;--ac-m:#f0b3b6;--ac-l:#fbe4e5;--ac-xl:#fdf3f3}
:root[data-theme=dark]{color-scheme:dark;
 --bg:#161616;--pn:#202020;--bd:#444;--tx:#e4e4e4;--dim:#9a9a9a;--hd:#2c2c2c;--hv:#2b2b2b;--gut:#262626;--gbd:#363636;
 --btn:#363636;--btnh:#464646;--btnbd:#666;--inp:#171717;--sub:#292929;--spl:#363636;--cd:#333;--sel:#3a3a3a;--off:#666;
 --kw:#fff;--st:#b4b4b4;--cm:#7d7d7d;--nm:#cfcfcf}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--tx);font:var(--fs)/1.4 system-ui,-apple-system,"Segoe UI",sans-serif}
body{display:grid;grid-template-rows:auto auto auto minmax(0,1fr)}
input,button,textarea,select{font:inherit;color:inherit}
input[type=text],input[type=number],select,textarea.fld{border:1px solid var(--bd);background:var(--inp);padding:2px 4px;min-width:0}
button{border:1px solid var(--btnbd);background:var(--btn);padding:2px .6em;cursor:pointer}
button:hover:not(:disabled){background:var(--btnh)}
button:disabled{color:var(--off);border-color:var(--bd);cursor:default;opacity:.7}
button.mini{padding:0 .35em;font-size:.92em;margin-left:.5em}
#cfg{border-top:3px solid var(--bd)}
body[data-state=running] #cfg{border-top-color:var(--dim)}
body[data-state=paused] #cfg{border-top-color:var(--ac)}
body[data-state=paused] #status{color:var(--ac)}
#cfg,#ctl{display:flex;gap:.6em;align-items:center;padding:.3em .5em;border-bottom:1px solid var(--bd);flex-wrap:wrap}
#cfg label{display:flex;gap:.3em;align-items:center;white-space:nowrap}
#cfg label.grow{flex:1 1 16em}#cfg label.grow input{flex:1;min-width:0;width:100%}
#brun:not(:disabled){background:var(--ac);border-color:var(--ac-d);color:#fff}
#brun:not(:disabled):hover{background:var(--ac-d)}
#bcont:not(:disabled){border-color:var(--ac);color:var(--ac-d)}
#status{margin-left:auto;font-weight:bold}
#main{display:grid;grid-template-columns:var(--left) 4px minmax(0,1fr) 4px var(--right);min-height:0}
.panel{background:var(--pn);min-height:0;min-width:0;display:flex;flex-direction:column;overflow:hidden}
.ph{background:var(--hd);border-bottom:1px solid var(--bd);padding:.1em .5em;font-weight:bold;text-transform:uppercase;font-size:.8em;letter-spacing:.06em;flex:none}
.pb{overflow:auto;flex:1;min-height:0}
.split{background:var(--spl);cursor:col-resize}.split.h{cursor:row-resize}
.split:hover{background:var(--ac-m)}
#center{display:grid;grid-template-rows:auto minmax(0,1fr) 4px var(--cons);min-height:0;min-width:0}
/* tree */
.ti{white-space:nowrap;cursor:pointer;padding:0 .3em;user-select:none}.ti:hover{background:var(--hv)}
.ti.dir{font-weight:bold}.ti .tg{display:inline-block;width:1em;color:var(--dim)}
.ti.run{box-shadow:inset 3px 0 var(--ac);background:var(--ac-xl)}
.ti.run::after{content:' ▶';color:var(--ac);font-size:.8em}
/* tabs */
#tabbar{display:flex;align-items:stretch;background:var(--hd);border-bottom:1px solid var(--bd);min-width:0}
#tabs{display:flex;overflow-x:auto;flex:1;min-width:0}
.tab{padding:.15em .6em;border-right:1px solid var(--bd);cursor:pointer;white-space:nowrap;color:var(--dim)}
.tab.on{background:var(--pn);color:var(--tx);font-weight:bold;box-shadow:inset 0 2px var(--ac)}
.tab .x{margin-left:.5em;color:var(--dim)}.tab .x:hover{color:var(--tx)}
.tab .dot{color:var(--ac);margin-right:.2em}
#edinfo{align-self:center;padding:0 .6em;color:var(--dim);white-space:nowrap}
#edinfo.mod{color:var(--ac-d);font-weight:bold}
#toast{align-self:center;padding:0 .6em;color:var(--ac-d);white-space:nowrap}
#bsave{margin:.15em .4em;align-self:center}
/* code + editor */
#code{overflow:auto;background:var(--pn);min-height:0;position:relative}
.edroot{position:relative;display:inline-block;min-width:100%;vertical-align:top}
.line{display:flex;width:max-content;min-width:100%;white-space:pre;height:var(--lh);line-height:var(--lh);tab-size:4;-moz-tab-size:4}
.gut{flex:none;width:5em;display:flex;align-items:center;justify-content:flex-end;gap:.3em;padding-right:.5em;color:var(--dim);background:var(--gut);border-right:1px solid var(--gbd);cursor:pointer;user-select:none;position:sticky;left:0;z-index:2}
.gut b{font-weight:normal}
.gut i{width:.8em;height:.8em;border-radius:50%;display:inline-block}
.gut:hover i{background:var(--ac-m)}
.line.bp .gut i{background:var(--ac)}
.src{padding-left:8px}
.line.caller{background:var(--ac-xl)}
.line.trail{background:var(--ac-xl);box-shadow:inset 3px 0 var(--ac-m)}
.line.trail .gut::before{content:'·';color:var(--ac);font-weight:bold}
.line.cur{background:var(--ac-l);box-shadow:inset 3px 0 var(--ac)}
.line.cur.flash{animation:flash .9s ease-out}
@keyframes flash{0%{background:var(--ac-m)}100%{background:var(--ac-l)}}
.line.cur .gut{color:var(--ac-d);font-weight:bold;background:var(--ac-l)}
.line.cur .gut b::before{content:'▶ ';color:var(--ac);font-size:.75em}
.line.exc{background:repeating-linear-gradient(45deg,var(--ac-m),var(--ac-m) 4px,var(--ac-l) 4px,var(--ac-l) 8px);box-shadow:inset 4px 0 var(--ac-d)}
.line.exc .gut{color:var(--ac-d);font-weight:bold}
.k{font-weight:bold;color:var(--kw)}.s{color:var(--st)}.c{color:var(--cm);font-style:italic}.n{color:var(--nm);text-decoration:underline dotted var(--cm)}
.edta{position:absolute;top:0;bottom:0;left:5em;right:0;margin:0;border:0;outline:0;resize:none;background:transparent;color:transparent;
 caret-color:var(--tx);font:inherit;line-height:var(--lh);padding:0 0 0 8px;white-space:pre;overflow:hidden;tab-size:4;-moz-tab-size:4}
.edta::selection{background:rgba(128,128,128,.38);color:transparent}
.msg{padding:.8em;color:var(--dim)}
/* console */
#cons{display:flex;flex-direction:column;background:var(--pn);border-top:1px solid var(--bd);min-height:0}
#out{flex:1;overflow:auto;margin:0;padding:.3em .5em;white-space:pre-wrap;word-break:break-all;min-height:0}
#out .err{color:var(--ac-d);font-style:italic}#out .sys{color:var(--dim)}#out .in{color:var(--tx);font-weight:bold}#out .bad{color:var(--ac-d);background:var(--ac-l)}
#prompt{display:flex;gap:.3em;border-top:1px solid var(--bd);padding:.15em .5em;align-items:flex-start;background:var(--gut);flex:none}
#in{flex:1;border:0;outline:0;resize:none;background:transparent;font-family:inherit;min-height:1.4em;max-height:8em;padding:0;overflow:auto}
/* variables */
.vrow{white-space:nowrap;cursor:default;padding:0 .3em;display:flex;gap:.5em;align-items:baseline}
.vrow.ex{cursor:pointer}.vrow:hover{background:var(--hv)}
.vrow .tg{width:.9em;flex:none;color:var(--dim)}
.vrow .nm{font-weight:bold}.vrow .ty{color:var(--dim);font-size:.82em}
.vrow .vl{overflow:hidden;text-overflow:ellipsis;min-width:0}
.vrow.chg .vl{background:var(--ac-l);outline:1px solid var(--ac-m);color:var(--ac-d)}
.vrow.er .vl{color:var(--ac-d);font-style:italic}.vrow.more{color:var(--dim);cursor:pointer}
.sub{font-weight:bold;color:var(--dim);padding:.1em .3em;background:var(--sub);border-top:1px solid var(--gbd);border-bottom:1px solid var(--gbd);font-size:.8em;text-transform:uppercase}
.frm{padding:0 .5em;white-space:nowrap;cursor:pointer}.frm:hover{background:var(--hv)}
.frm.on{background:var(--ac-l);font-weight:bold;box-shadow:inset 3px 0 var(--ac)}.frm.lib{color:var(--off)}
.frm .fl{color:var(--dim)}
#rt{display:flex;flex-direction:column;min-height:0}
#rt .panel{flex:none}
#stackp{max-height:150px}#watchp{max-height:130px}#varp{flex:1 !important}
#wadd{display:flex;border-top:1px solid var(--gbd);flex:none}#wadd input{flex:1;border:0;padding:.15em .5em;outline:0;background:var(--inp)}
.wx{color:var(--dim);cursor:pointer;margin-left:auto;padding-left:.5em}
/* manual & settings */
.man{padding:.4em 1.6em 1.4em;line-height:1.55;max-width:62em}
.man h2{font-size:.95em;text-transform:uppercase;letter-spacing:.06em;border-bottom:2px solid var(--ac);padding-bottom:.1em;margin:1.3em 0 .4em}
.man p{margin:.25em 0}.man ul{margin:.25em 0;padding-left:1.5em}
.man kbd{border:1px solid var(--dim);border-bottom-width:2px;background:var(--gut);padding:0 .3em;font:inherit;white-space:nowrap}
.man table{border-collapse:collapse;margin:.3em 0}.man td,.man th{border:1px solid var(--gbd);padding:.15em .6em;text-align:left;vertical-align:top}
.man th{background:var(--hd)}.man code{background:var(--cd);padding:0 .25em}
.man .sw{display:inline-block;width:.85em;height:.85em;border-radius:50%;background:var(--ac);vertical-align:-1px}
.man .nt{background:var(--ac-xl);border-left:3px solid var(--ac);padding:.2em .6em;margin:.5em 0}
.srow{display:grid;grid-template-columns:11em 1fr;gap:.6em;align-items:center;padding:.35em 0;border-bottom:1px solid var(--gbd)}
.srow>label{font-weight:bold}.sctl{display:flex;gap:.4em;align-items:center;flex-wrap:wrap}
.sctl input[type=number]{width:4.5em}.sctl textarea{width:100%;min-height:6em;font-family:inherit}
.sw2{width:1.6em;height:1.6em;border:2px solid transparent;border-radius:50%;padding:0;cursor:pointer;outline:1px solid var(--bd)}
.sw2.on{border-color:var(--tx)}
.tgl.on{background:var(--ac);border-color:var(--ac-d);color:#fff}
/* hover tooltip */
#tip{position:fixed;z-index:20;display:none;max-width:40em;max-height:70vh;overflow:auto;background:var(--pn);border:1px solid var(--tx);border-top:3px solid var(--ac);
 padding:.4em .7em;box-shadow:0 4px 14px rgba(0,0,0,.3);font-size:.93em;line-height:1.45}
#tip .h{font-weight:bold}#tip .kind{color:var(--ac-d);font-weight:normal;margin-left:.5em;text-transform:uppercase;font-size:.8em;letter-spacing:.05em}
#tip .sig{background:var(--cd);padding:.1em .4em;margin:.25em 0;white-space:pre-wrap;word-break:break-word}
#tip .doc{color:var(--dim);white-space:pre-wrap;margin:.25em 0}
#tip a{color:var(--ac-d);cursor:pointer;text-decoration:underline dotted}#tip a:hover{background:var(--ac-l)}
#tip .mro{margin-top:.35em;border-top:1px solid var(--gbd);padding-top:.25em}
#tip .mro div{padding-left:.2em}#tip .mro .def{font-weight:bold}#tip .mro .def::before{content:'● ';color:var(--ac)}
#tip .lbl{color:var(--dim);font-size:.82em;text-transform:uppercase;letter-spacing:.05em}
/* modal */
#modal{position:fixed;inset:0;background:rgba(0,0,0,.4);display:none;align-items:center;justify-content:center;z-index:10}
#modal.on{display:flex}
#mbox{background:var(--pn);border:2px solid var(--tx);border-top:3px solid var(--ac);width:min(92vw,70em);max-height:88vh;display:flex;flex-direction:column}
#mbox .ph{display:flex;gap:.6em;align-items:center;text-transform:none;font-size:1em}
#mbox .ph .sp{flex:1}
#mbody{overflow:auto;padding:0;min-height:5em}
table.t{border-collapse:collapse}
table.t th,table.t td{border:1px solid var(--gbd);padding:.05em .5em;white-space:nowrap;text-align:right}
table.t thead th{position:sticky;top:0;background:var(--hd);z-index:1}
table.t th.i{position:sticky;left:0;background:var(--sub);text-align:left}
table.t .dt{font-weight:normal;color:var(--dim);font-size:.82em;display:block}
/* Workspace chrome: all assets and fonts are local. */
:root{--ed-bg:var(--pn);--ed-text:var(--tx);--ed-gutter:var(--gut);--ed-muted:var(--dim)}
#brand{display:flex;align-items:center;gap:12px;padding:12px 18px;background:var(--pn);border-bottom:1px solid var(--bd)}
#brand .logo{display:grid;place-items:center;width:30px;height:30px;border-radius:9px;background:var(--ac-l);color:var(--ac-d);font:bold 14px var(--mono)}
#brand strong{font-size:15px;letter-spacing:-.4px}#brand .tagline{color:var(--dim);font-size:12px}
.offline{margin-left:auto;display:flex;align-items:center;gap:7px;color:var(--dim);font-size:11px;letter-spacing:.06em;text-transform:uppercase}
.offline::before{content:'';width:6px;height:6px;border-radius:50%;background:var(--ac)}
#cfg{background:var(--pn);border-top:0;padding:10px 18px;gap:8px 12px}
#cfg label{font-size:.84em;color:var(--dim)}#cfg label input{color:var(--tx)}
#cfg input[type=text]{padding:6px 8px;border-radius:6px}#cfg input[type=checkbox]{accent-color:var(--ac)}
#ctl{background:var(--pn);padding:9px 18px;gap:6px}
button{border-radius:6px;padding:5px 10px;background:var(--btn);border-color:var(--bd);font-size:.88em;line-height:1.4}
button:focus-visible,select:focus-visible,input:focus-visible,textarea.fld:focus-visible{outline:2px solid var(--ac);outline-offset:2px}
button kbd{font:10px var(--mono);opacity:.65;margin-left:6px}
#ctl .divider{height:20px;width:1px;background:var(--bd);margin:0 5px}
#brun:not(:disabled){background:var(--ac-d);border-color:var(--ac-d)}
#status{border-radius:20px;background:var(--sub);padding:4px 10px;font-size:.8em;max-width:30vw;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ph{padding:9px 12px;background:var(--pn);font-size:10px;letter-spacing:.1em;color:var(--dim);border-bottom-color:var(--gbd)}
#main{padding:10px;gap:0;grid-template-columns:var(--left) 8px minmax(0,1fr) 8px var(--right)}
#files,#center,#rt{border:1px solid var(--bd);border-radius:8px;overflow:hidden;background:var(--pn)}
.split{background:transparent;position:relative}.split::after{content:'';position:absolute;inset:25% 3px;border-radius:3px;background:var(--bd)}
.split.h::after{inset:3px 40%}.split:hover{background:var(--ac-xl)}
#center{grid-template-rows:auto minmax(0,1fr) 8px var(--cons)}
.ti{padding-top:4px;padding-bottom:4px;font-size:.9em}.ti.dir{font-weight:600}.ti .tg{margin-right:4px}
#tabbar{background:var(--sub);min-height:38px}.tab{padding:9px 14px;font-size:.85em;border-right:0}.tab.on{font-weight:600}
#edinfo,#toast{font-size:.75em}#toast{max-width:20vw;overflow:hidden;text-overflow:ellipsis}
#code,.theme-preview{background:var(--ed-bg);color:var(--ed-text);font-family:var(--mono)}
.gut{background:var(--ed-gutter);color:var(--ed-muted);border-color:var(--gbd)}
.edta{caret-color:var(--ed-text)}
#code .line.cur,#code .line.cur .gut{background:var(--ed-mark);color:var(--ed-text)}
#code .line.caller,#code .line.trail{background:var(--ed-mark)}
#code .line.exc{background:repeating-linear-gradient(45deg,var(--ed-mark-strong),var(--ed-mark-strong) 4px,var(--ed-mark) 4px,var(--ed-mark) 8px)}
@keyframes flash{0%{background:var(--ed-mark-strong)}100%{background:var(--ed-mark)}}
.n{text-decoration:none}.k{font-weight:600}
#out,#in,.vrow,.frm,table.t{font-family:var(--mono)}
#prompt{padding:7px 12px;color:var(--dim)}#cons .ph span{display:none}
#out{padding:10px 12px;line-height:1.55;font-size:.9em}
.vrow,.frm{padding-top:4px;padding-bottom:4px;font-size:.88em}.sub{padding:6px 10px;letter-spacing:.05em}
#wadd input{padding:9px 12px;font-size:.85em}#rt .panel+.panel{border-top:1px solid var(--bd)}
#stackp{max-height:190px}#watchp{max-height:180px}
#modal{background:rgba(0,0,0,.45);backdrop-filter:blur(3px)}
#mbox{border:1px solid var(--bd);border-radius:12px;box-shadow:0 20px 80px #0005;max-width:900px}
#mbox>.ph{padding:12px 18px;color:var(--tx);letter-spacing:0}#mclose{font-size:12px}
.man{padding:0 24px 24px}.man h2{text-transform:none;letter-spacing:0;font-size:1em;border-bottom:1px solid var(--bd);padding-bottom:10px;margin-top:24px}
.srow{grid-template-columns:140px 1fr;padding:12px 0}.srow>label{font-weight:500;font-size:.9em}
.sctl select{padding:5px 8px;border-radius:6px}.sctl input[type=text]{padding:5px 8px;border-radius:6px}
.theme-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;width:100%}
.theme-card{display:flex;align-items:center;gap:8px;text-align:left;padding:10px;border:1px solid var(--bd);background:var(--pn)}
.theme-card[aria-pressed=true]{border-color:var(--ac);box-shadow:0 0 0 1px var(--ac);background:var(--ac-xl)}
.theme-dots{display:flex;gap:3px}.theme-dots i{display:block;width:10px;height:20px;border-radius:3px}
.theme-preview{margin:12px 0;padding:16px;border:1px solid var(--bd);border-radius:8px;line-height:1.6;white-space:pre;overflow:auto;font-size:13px}
.color-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;width:100%}
.color-item{display:flex;align-items:center;gap:8px;padding:6px 8px;border:1px solid var(--bd);border-radius:6px;font-size:12px}
.color-item input{width:26px;height:26px;padding:0;border:0;background:transparent;cursor:pointer}.color-item code{margin-left:auto;color:var(--dim);font-size:11px}
.style-note{font-size:.85em;color:var(--dim);margin:8px 0}.style-error{color:var(--ac-d);font-size:.85em;min-height:1.4em}
#tip{border-radius:8px}#winp::placeholder,#in::placeholder{color:var(--dim)}
[hidden]{display:none !important}
#center{grid-template-rows:minmax(0,1fr) 8px var(--cons)}
#editor{display:flex;flex-direction:column;min-height:0;min-width:0;position:relative;overflow:hidden}
#editor #code{flex:1}
#edittools,#findbar,#editorstatus{flex:none;border-bottom:1px solid var(--gbd);background:var(--pn)}
#edittools{display:flex;flex-wrap:wrap;align-items:center;gap:5px;padding:5px 8px}
#edittools button{font-size:11px;padding:3px 7px}#edittools .hint{margin-left:auto;font-size:11px;color:var(--dim)}
#findbar{padding:8px 10px;background:var(--sub);font-size:12px}
.findrow{display:flex;align-items:center;flex-wrap:wrap;gap:6px}.findrow+.findrow{margin-top:7px}
.findrow input[type=text]{flex:1;min-width:100px;padding:5px 8px;border-radius:5px;font-family:var(--mono)}
.findrow button{font-size:11px}.findrow label{display:flex;align-items:center;gap:3px;color:var(--dim);font-size:11px}
#findcount{min-width:65px;color:var(--dim);font-size:11px}#findcount.error{color:var(--ac-d)}
#editorstatus{display:flex;align-items:center;gap:14px;padding:5px 10px;border-bottom:0;border-top:1px solid var(--gbd);font-size:11px;color:var(--dim)}
#cursorpos{margin-left:auto}#editorstatus button{padding:0 5px;font-size:11px}
mark.find-hit{background:var(--ed-mark-strong);color:inherit;outline:1px solid var(--ac-m);border-radius:2px}
mark.find-hit.current{outline:2px solid var(--ac)}
#completions{position:absolute;top:76px;left:70px;z-index:5;background:var(--pn);border:1px solid var(--bd);border-radius:8px;box-shadow:0 8px 25px #0003;min-width:230px;max-width:80%;overflow:hidden}
#completions .label{padding:6px 10px;font-size:10px;color:var(--dim)}
#completions button{display:block;width:100%;text-align:left;border:0;border-radius:0;font:12px var(--mono);padding:6px 12px}
#completions button.on{background:var(--ac-l);color:var(--ac-d)}
@media(max-width:1100px){:root{--left:190px;--right:280px}#cfg label.grow{flex-basis:100%}#ctl button kbd,#brand .tagline{display:none}#ctl .divider{margin:0 2px}}
@media(max-width:760px){:root{--left:130px;--right:210px}#brand,#cfg,#ctl{padding-left:10px;padding-right:10px}#main{padding:5px}#status{max-width:180px}.theme-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.srow{grid-template-columns:1fr}.color-grid{grid-template-columns:1fr}}
</style>
<script nonce="__NONCE__">
const BOOT = __BOOT__;
const FONTS = {default: 'Consolas,Menlo,"DejaVu Sans Mono",monospace', courier: '"Courier New",Courier,monospace',
  lucida: '"Lucida Console",Monaco,monospace', system: 'ui-monospace,SFMono-Regular,Menlo,Consolas,monospace',
  sans: 'system-ui,"Segoe UI",Arial,sans-serif'};
const hex2rgb = h => { h = h.replace('#', ''); if (h.length === 3) h = h.split('').map(c => c + c).join(''); const n = parseInt(h, 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; };
const mix = (a, b, t) => '#' + a.map((v, i) => Math.round(v * (1 - t) + b[i] * t).toString(16).padStart(2, '0')).join('');
// Named palettes contain only literal colors. There are no remote stylesheets,
// font downloads, plugins, or arbitrary CSS in the styling system.
const THEMES = {
  light: {label:'Daylight', dark:false, bg:'#eef1f5', panel:'#ffffff', text:'#243047', muted:'#59677c', border:'#d8dee8',
    code:'#ffffff', ink:'#243047', gutter:'#f6f8fb', tokens:['#7c3aed','#157347','#64748b','#b45309']},
  dark: {label:'Graphite', dark:true, bg:'#17191e', panel:'#202329', text:'#e1e5ed', muted:'#a0a9b9', border:'#353b46',
    code:'#202329', ink:'#e1e5ed', gutter:'#242830', tokens:['#c4a0ff','#9bd5a5','#9ba8bc','#f2bd80']},
  midnight: {label:'Midnight', dark:true, bg:'#0d1424', panel:'#131e33', text:'#dbe7ff', muted:'#9aaed0', border:'#293a58',
    code:'#101a2d', ink:'#dbe7ff', gutter:'#162238', tokens:['#bba6ff','#7dd3c3','#91a4c4','#ffcb8b']},
  sepia: {label:'Parchment', dark:false, bg:'#e9e1d2', panel:'#faf4e8', text:'#493c2b', muted:'#78674f', border:'#d5c8af',
    code:'#faf4e8', ink:'#493c2b', gutter:'#f0e7d6', tokens:['#8055a5','#466b35','#796c57','#9c471f']},
  forest: {label:'Forest', dark:true, bg:'#101c19', panel:'#182922', text:'#dcebe0', muted:'#a0b9a9', border:'#304a3e',
    code:'#15251e', ink:'#dcebe0', gutter:'#1a2e25', tokens:['#d4b4ef','#b5d88a','#9db5a5','#f0c492']},
  contrast: {label:'High contrast', dark:true, bg:'#000000', panel:'#080808', text:'#ffffff', muted:'#c6c6c6', border:'#888888',
    code:'#000000', ink:'#ffffff', gutter:'#121212', tokens:['#ffff00','#68ffaf','#c6c6c6','#70d7ff']}
};
const EDITOR_FIELDS = [['background','Background'],['text','Text'],['keyword','Keywords'],['string','Strings'],['comment','Comments'],['number','Numbers'],['gutter','Gutter']];
const validColor = v => typeof v === 'string' && /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(v);
function editorColors(p) {
  const t = THEMES[p.editor_theme === 'match' ? p.theme : p.editor_theme] || THEMES.light;
  const c = {background:t.code, text:t.ink, keyword:t.tokens[0], string:t.tokens[1], comment:t.tokens[2], number:t.tokens[3], gutter:t.gutter};
  for (const [k] of EDITOR_FIELDS) if (validColor((p.editor_colors || {})[k])) c[k] = p.editor_colors[k];
  return c;
}
function applyPrefs(p) {
  const root = document.documentElement, r = root.style, t = THEMES[p.theme] || THEMES.light, dark = t.dark;
  r.setProperty('--fs', p.font_size + 'px');
  r.setProperty('--mono', FONTS[p.font] || FONTS.default);
  r.setProperty('--lh', Math.round(p.font_size * ({compact: 1.3, normal: 1.45, relaxed: 1.7}[p.line] || 1.45)) + 'px');
  root.dataset.theme = dark ? 'dark' : 'light';
  const W = [255,255,255], bg = hex2rgb(t.panel), tint = v => mix(bg, hex2rgb(t.text), v);
  const vars = {bg:t.bg, pn:t.panel, bd:t.border, tx:t.text, dim:t.muted, hd:tint(.035), hv:tint(.07), gut:t.gutter,
    gbd:t.border, btn:tint(.035), btnh:tint(.1), btnbd:t.border, inp:t.panel, sub:tint(.035), spl:t.border, cd:tint(.07), sel:tint(.15), off:t.muted};
  for (const [k,v] of Object.entries(vars)) r.setProperty('--' + k, v);
  const a = hex2rgb(validColor(p.accent) ? p.accent : '#d71e28');
  r.setProperty('--ac', mix(a, a, 0));
  r.setProperty('--ac-d', dark ? mix(a, W, .4) : mix(a, [0, 0, 0], .3));
  r.setProperty('--ac-m', dark ? mix(a, bg, .5) : mix(a, W, .7));
  r.setProperty('--ac-l', dark ? mix(a, bg, .75) : mix(a, W, .88));
  r.setProperty('--ac-xl', dark ? mix(a, bg, .88) : mix(a, W, .95));
  const c = editorColors(p);
  for (const [k,v] of Object.entries({'ed-bg':c.background, 'ed-text':c.text, 'ed-gutter':c.gutter,
    'ed-muted':c.comment, kw:c.keyword, st:c.string, cm:c.comment, nm:c.number})) r.setProperty('--' + k, v);
  r.setProperty('--ed-mark', mix(a, hex2rgb(c.background), .88));
  r.setProperty('--ed-mark-strong', mix(a, hex2rgb(c.background), .7));
  for (const k of ['left', 'right', 'cons']) { if (p.layout && p.layout[k]) r.setProperty('--' + k, p.layout[k] + 'px'); else r.removeProperty('--' + k); }
}
applyPrefs(BOOT.prefs);   // before first paint
</script></head><body>
<header id="brand"><span class="logo" aria-hidden="true">Py</span><strong>PythonDebugger</strong><span class="tagline">Python debugger &amp; editor</span><span class="offline" title="All assets are embedded. Debugger connections stay on this computer.">Offline · local only</span></header>
<div id="cfg">
  <label class="grow">Folder <input type="text" id="root" size="20"></label><button id="bopen">Open</button><button id="bbrowse">Browse…</button>
  <label>Script <input type="text" id="script" size="22"></label>
  <label>Args <input type="text" id="args" size="14"></label>
  <label>Python <input type="text" id="python" size="20"></label>
  <label><input type="checkbox" id="soe">stop on entry</label>
  <label><input type="checkbox" id="jmc" checked>just my code</label>
</div>
<div id="ctl">
  <button id="brun">▶ Run</button><button id="bcont" title="F8">Continue <kbd>F8</kbd></button><span class="divider"></span><button id="bnext" title="F10">Step Over <kbd>F10</kbd></button>
  <button id="bstep" title="F11">Step Into <kbd>F11</kbd></button><button id="bout" title="Shift+F11">Step Out <kbd>⇧F11</kbd></button><span class="divider"></span>
  <button id="bstop">Stop</button><button id="brestart">Restart</button>
  <span id="status">idle</span><button id="bfm" title="Smaller text only (Ctrl and minus)">A−</button><button id="bfp" title="Larger text only (Ctrl and plus)">A+</button><button id="bset" title="Font size, theme, environment">⚙ Settings</button><button id="bhelp" title="F1">? Help</button>
</div>
<div id="main">
  <div class="panel" id="files"><div class="ph">Files</div><div class="pb" id="tree"></div></div>
  <div class="split" data-v="--left" data-d="1"></div>
  <div id="center">
    <div id="editor">
    <div id="tabbar"><div id="tabs"></div><span id="toast"></span><span id="edinfo"></span><button id="bsave" title="Ctrl+S">Save</button></div>
    <div id="edittools" role="toolbar" aria-label="Editor tools">
      <button id="bundo" title="Undo (Ctrl/Cmd+Z)">Undo</button><button id="bredo" title="Redo (Ctrl/Cmd+Shift+Z)">Redo</button>
      <button id="bfind" title="Find (Ctrl/Cmd+F)">Find</button><button id="breplace" title="Replace (Ctrl/Cmd+H)">Replace</button>
      <button id="bgoto" title="Go to line (Ctrl/Cmd+G)">Go to line</button><button id="bcomment" title="Toggle comments (Ctrl/Cmd+/)">Comment</button>
      <button id="bcomplete" title="Suggest words from this file (Ctrl+Space)">Suggest</button><button id="bsaveall" title="Save all modified files (Ctrl/Cmd+Shift+S)">Save all</button>
      <span class="hint">Tab to indent · Ctrl/Cmd+/ to comment</span>
    </div>
    <div id="findbar" hidden>
      <div class="findrow"><input id="findtext" type="text" aria-label="Find in current file" placeholder="Find in current file" spellcheck="false">
        <span id="findcount" role="status" aria-live="polite"></span><button id="findprev" title="Previous match (Shift+Enter)">↑</button><button id="findnext" title="Next match (Enter)">↓</button>
        <label><input id="findcase" type="checkbox">Match case</label><label><input id="findword" type="checkbox">Whole word</label><label><input id="findregex" type="checkbox">Regex</label>
        <button id="findclose" aria-label="Close find">×</button></div>
      <div id="replacerow" class="findrow" hidden><input id="replacetext" type="text" aria-label="Replace with" placeholder="Replace with" spellcheck="false"><button id="replaceone">Replace</button><button id="replaceall">Replace all</button></div>
    </div>
    <div id="completions" hidden role="group" aria-label="Local word suggestions"></div>
    <div id="code"><div class="msg"><h3>Your code, up close.</h3>Open a Python file from the explorer, set a breakpoint in the gutter, then press Run.<br><br>Choose a workspace and editor theme in ⚙ Settings. Everything runs on this computer.</div></div>
    <div id="editorstatus"><span id="filemode">Python editor</span><span id="fileformat"></span><span id="cursorpos">Ln 1, Col 1</span><button id="bgotofooter" title="Go to line">Go to…</button></div>
    </div>
    <div class="split h" data-v="--cons" data-d="-1"></div>
    <div id="cons"><div class="ph">Console / terminal <span style="font-weight:normal;text-transform:none"> — when paused, type Python to run in the selected frame (e.g. <b>flag = True</b>); while running, input goes to the script's stdin</span></div>
      <pre id="out"></pre>
      <div id="prompt"><span>&gt;&gt;&gt;</span><textarea id="in" rows="1" spellcheck="false" autocomplete="off" placeholder="expression or statement (Enter = run, Shift+Enter = newline)"></textarea></div>
    </div>
  </div>
  <div class="split" data-v="--right" data-d="-1"></div>
  <div id="rt">
    <div class="panel" id="stackp"><div class="ph">Call stack</div><div class="pb" id="stack"></div></div>
    <div class="panel" id="varp"><div class="ph">Variables</div><div class="pb" id="vars"></div></div>
    <div class="panel" id="watchp"><div class="ph">Watch</div><div class="pb" id="watch"></div>
      <div id="wadd"><input type="text" id="winp" placeholder="add expression, Enter"></div></div>
  </div>
</div>
<div id="modal"><div id="mbox"><div class="ph"><span id="mtitle"></span><span class="sp"></span><span id="mctl"></span><button id="mclose">Close</button></div><div id="mbody"></div></div></div>
<script nonce="__NONCE__">
'use strict';
const TOKEN = new URLSearchParams(location.search).get('t') || '';
const $ = (s, r) => (r || document).querySelector(s);
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
async function post(name, body) {
  const r = await fetch('/api/' + name, {method: 'POST', headers: {'X-Token': TOKEN, 'Content-Type': 'application/json'}, body: JSON.stringify(body || {})});
  return r.json();
}
async function get(name, params) {
  const u = new URLSearchParams(params || {}); u.set('t', TOKEN);
  return (await fetch('/api/' + name + '?' + u)).json();
}
const S = {cfg: {}, prefs: BOOT.prefs, settingsPath: '', state: 'idle', status: '', files: new Map(), alias: new Map(), tabs: [], active: null,
  breaks: new Map(), stop: null, sel: 0, expanded: new Set(), prevVals: new Map(), curVals: new Map(), pending: new Map(), rid: 1,
  hist: [], hpos: 0, watches: [], lastVars: null, tbl: null, lastPos: null, trail: null, raf: 0};

/* ---------------- syntax highlighting ---------------- */
const KW = new Set('False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield self'.split(' '));
const RX = /(#[^\n]*)|("{3}[\s\S]*?"{3}|'{3}[\s\S]*?'{3}|(?:[rRbBuUfF]{0,2})"(?:\\.|[^"\\\n])*"|(?:[rRbBuUfF]{0,2})'(?:\\.|[^'\\\n])*')|(\b\d[\d_]*\.?\d*(?:[eE][+-]?\d+)?\b)|(\b[A-Za-z_]\w*\b)/g;
function highlight(text, hits = [], selected = -1) {
  const lines = []; let cur = '', offset = 0, hitIndex = 0;
  const emit = (t, cls) => {
    const parts = t.split('\n');
    parts.forEach((p, i) => {
      if (i) { lines.push(cur); cur = ''; offset++; }
      let rendered = '', pos = 0;
      while (pos < p.length) {
        while (hitIndex < hits.length && hits[hitIndex].end <= offset + pos) hitIndex++;
        const h = hits[hitIndex], start = offset + pos;
        const end = h ? Math.min(offset + p.length, h.start > start ? h.start : h.end) : offset + p.length;
        const chunk = esc(p.slice(pos, end - offset));
        rendered += h && h.start <= start ? '<mark class="find-hit' + (hitIndex === selected ? ' current' : '') + '">' + chunk + '</mark>' : chunk;
        pos = end - offset;
      }
      if (p) cur += cls ? '<span class="' + cls + '">' + rendered + '</span>' : rendered;
      offset += p.length;
    });
  };
  let last = 0, m; RX.lastIndex = 0;
  while ((m = RX.exec(text))) {
    if (m.index > last) emit(text.slice(last, m.index), '');
    if (m[1]) emit(m[0], 'c'); else if (m[2]) emit(m[0], 's'); else if (m[3]) emit(m[0], 'n');
    else emit(m[0], KW.has(m[0]) ? 'k' : '');
    last = RX.lastIndex;
  }
  if (last < text.length) emit(text.slice(last), '');
  lines.push(cur);
  return lines;
}
const codeLike = l => { const t = (l || '').trim(); return t && !t.startsWith('#'); };

/* ---------------- files, tabs, editor ---------------- */
async function loadFile(path) {
  path = S.alias.get(path) || path;
  if (S.files.has(path)) return S.files.get(path);
  const r = await get('file', {path});
  const key = r.path || path;
  S.alias.set(path, key);
  let f = S.files.get(key);
  if (!f) {
    f = r.error ? {path: key, error: r.error}
      : {path: key, text: r.text, saved: r.text, crlf: !!r.crlf, readonly: !!r.readonly, dirty: false, lines: r.text.split('\n'), html: highlight(r.text), scroll: [0, 0], selection: [0,0], history: [{text:r.text, selection:[0,0]}], historyIndex:0};
    S.files.set(key, f);
  }
  return f;
}
function rememberScroll() { const f = S.files.get(S.active); if (f && !f.error) { const c = $('#code'), ta = $('#edta'); f.scroll = [c.scrollTop, c.scrollLeft]; if (ta) f.selection = [ta.selectionStart,ta.selectionEnd]; } }
async function openFile(path, line) {
  const f = await loadFile(path);
  rememberScroll();
  if (!S.tabs.includes(f.path)) S.tabs.push(f.path);
  S.active = f.path;
  renderTabs(); renderCode();
  if (line) scrollTo(line); else if (f.scroll) { $('#code').scrollTop = f.scroll[0]; $('#code').scrollLeft = f.scroll[1]; }
  return f;
}
function closeTab(p) {
  const i = S.tabs.indexOf(p); if (i < 0) return;
  const f = S.files.get(p);
  if (f && f.dirty && !confirm('Discard unsaved changes to ' + base(p) + '?')) return;
  S.tabs.splice(i, 1); S.files.delete(p);  // reopening re-reads the file from disk
  if (S.active === p) S.active = S.tabs[Math.min(i, S.tabs.length - 1)] || null;
  else rememberScroll();
  renderTabs(); renderCode();
}
const base = p => p.split(/[\\/]/).pop();
function renderTabs() {
  const t = $('#tabs'); t.textContent = '';
  for (const p of S.tabs) {
    const f = S.files.get(p);
    const d = el('div', 'tab' + (p === S.active ? ' on' : '')); d.title = p;
    if (f && f.dirty) d.appendChild(el('span', 'dot', '●'));
    d.appendChild(document.createTextNode(base(p)));
    d.onclick = () => { rememberScroll(); S.active = p; renderTabs(); renderCode(); const g = S.files.get(p); if (g && g.scroll) { $('#code').scrollTop = g.scroll[0]; $('#code').scrollLeft = g.scroll[1]; } };
    const x = el('span', 'x', '×'); x.onclick = e => { e.stopPropagation(); closeTab(p); }; d.appendChild(x);
    t.appendChild(d);
    if (p === S.active) requestAnimationFrame(() => d.scrollIntoView({block: 'nearest', inline: 'nearest'}));
  }
}
function updateEdInfo() {
  const f = S.files.get(S.active), i = $('#edinfo'), b = $('#bsave');
  i.className = ''; i.textContent = '';
  if (f && !f.error) {
    if (f.readonly) i.textContent = 'read-only';
    else if (f.dirty) { i.textContent = 'modified'; i.className = 'mod'; }
  }
  b.disabled = !(f && !f.error && f.dirty && !f.readonly);
  const writable = f && !f.error && !f.readonly;
  $('#bundo').disabled = !writable || !f.historyIndex;
  $('#bredo').disabled = !writable || f.historyIndex >= f.history.length - 1;
  $('#bcomment').disabled = !writable;
  $('#bcomplete').disabled = !writable;
  $('#bsaveall').disabled = ![...S.files.values()].some(g => g.dirty && !g.readonly && !g.error);
  $('#filemode').textContent = f && !f.error ? (f.readonly ? 'Read-only viewer' : 'Python editor') : 'No file open';
  $('#fileformat').textContent = f && !f.error ? 'UTF-8 · ' + (f.crlf ? 'CRLF' : 'LF') + ' · 4 spaces' : '';
}
let toastTimer = 0;
function toast(t) { const e = $('#toast'); e.textContent = t; clearTimeout(toastTimer); toastTimer = setTimeout(() => e.textContent = '', 5000); }
function makeRow(n, h) {
  const row = el('div', 'line'); row.id = 'L' + n; row.dataset.n = n;
  const g = el('span', 'gut'); g.appendChild(el('i')); g.appendChild(el('b', null, String(n)));
  g.onclick = () => toggleBp(n);
  const s = el('span', 'src'); s.innerHTML = h || ' '; s._h = h;
  row.appendChild(g); row.appendChild(s); return row;
}
function renderCode() {
  const c = $('#code'); c.textContent = '';
  hideCompletions();
  const f = S.files.get(S.active);
  refreshFind();
  if (!f) { c.appendChild(el('div', 'msg', 'Open a file from the explorer to edit it.')); updateEdInfo(); return; }
  if (f.error) { c.appendChild(el('div', 'msg', f.path + ': ' + f.error)); updateEdInfo(); return; }
  f.html = highlight(f.text, FIND.hits, FIND.index);
  const root = el('div', 'edroot'); root.id = 'edroot';
  const frag = document.createDocumentFragment();
  f.html.forEach((h, i) => frag.appendChild(makeRow(i + 1, h)));
  root.appendChild(frag);
  const ta = el('textarea', 'edta'); ta.id = 'edta'; ta.value = f.text; ta.spellcheck = false; ta.wrap = 'off'; ta.readOnly = f.readonly;
  ta.setAttribute('autocapitalize', 'off'); ta.setAttribute('autocomplete', 'off');
  ta.setAttribute('aria-label', 'Code editor: ' + base(f.path)); ta.setAttribute('autocorrect', 'off');
  ta.addEventListener('beforeinput', e => {
    if (e.inputType === 'historyUndo' || e.inputType === 'historyRedo') { e.preventDefault(); undoEdit(e.inputType === 'historyRedo'); return; }
    f.beforeSelection = [ta.selectionStart,ta.selectionEnd];
  });
  ta.addEventListener('input', onEdInput); ta.addEventListener('keydown', onEdKey);
  ta.addEventListener('select', () => updateCursor(ta)); ta.addEventListener('click', () => { hideCompletions(); updateCursor(ta); });
  ta.addEventListener('keyup', () => { updateCursor(ta); ensureCaret(ta); });
  root.appendChild(ta); c.appendChild(root);
  ta.setSelectionRange(...(f.selection || [0,0]));
  marks(); updateEdInfo(); updateCursor(ta);
}
function syncRows(f) {
  const root = $('#edroot'); if (!root) return;
  const rows = root.querySelectorAll('.line'), n = f.html.length;
  for (let i = 0; i < Math.min(rows.length, n); i++) {
    const s = rows[i].lastChild;
    if (s._h !== f.html[i]) { s.innerHTML = f.html[i] || ' '; s._h = f.html[i]; }
  }
  for (let i = rows.length - 1; i >= n; i--) rows[i].remove();
  const ta = $('#edta');
  for (let i = rows.length; i < n; i++) root.insertBefore(makeRow(i + 1, f.html[i]), ta);
  if (rows.length !== n) marks();
}
function onEdInput(e) {
  const f = S.files.get(S.active); if (!f) return;
  const ta = e.target;
  if (f.readonly) { ta.value = f.text; return; }
  const was = f.dirty;
  recordEdit(f, ta, e.inputType || 'command');
  f.text = ta.value; f.lines = f.text.split('\n'); f.dirty = f.text !== f.saved;
  hideCompletions(); refreshFind();
  if (!S.raf) S.raf = requestAnimationFrame(() => { S.raf = 0; const g = S.files.get(S.active); if (g && !g.error) { g.html = highlight(g.text, FIND.hits, FIND.index); syncRows(g); } });
  if (was !== f.dirty) renderTabs();
  updateEdInfo(); updateCursor(ta); ensureCaret(ta);
}
let charW = 0, charFont = '';
function ensureCaret(ta) {
  const c = $('#code'), cs = getComputedStyle(ta), lh = parseFloat(cs.lineHeight) || 20, v = ta.value, p = ta.selectionStart;
  let line = 0; for (let i = v.indexOf('\n'); i >= 0 && i < p; i = v.indexOf('\n', i + 1)) line++;
  const top = line * lh, bot = top + lh;
  if (top < c.scrollTop) c.scrollTop = top; else if (bot > c.scrollTop + c.clientHeight - 6) c.scrollTop = bot - c.clientHeight + 6;
  if (cs.font !== charFont) { const cv = document.createElement('canvas').getContext('2d'); cv.font = cs.font; charW = cv.measureText('M').width; charFont = cs.font; }
  const col = p - lineStartAt(v,p), x = col * charW + parseFloat(cs.paddingLeft) + ta.offsetLeft;
  if (x < c.scrollLeft + ta.offsetLeft + 10) c.scrollLeft = Math.max(0, x - ta.offsetLeft - 10);
  else if (x > c.scrollLeft + c.clientWidth - 30) c.scrollLeft = x - c.clientWidth + 60;
}
function lineStartAt(text, pos) { return pos > 0 ? text.lastIndexOf('\n',pos - 1) + 1 : 0; }
function updateCursor(ta = $('#edta')) {
  if (!ta) { $('#cursorpos').textContent = ''; return; }
  const f = S.files.get(S.active), p = ta.selectionStart, end = ta.selectionEnd;
  if (f) f.selection = [p,end];
  const line = ta.value.slice(0,p).split('\n').length, col = p - lineStartAt(ta.value,p) + 1;
  $('#cursorpos').textContent = 'Ln ' + line + ', Col ' + col + (end > p ? ' · ' + (end - p) + ' selected' : '');
}
function recordEdit(f, ta, kind) {
  if (ta.value === f.text) return;
  const before = f.beforeSelection || f.selection || [0,0], now = Date.now();
  const current = f.history[f.historyIndex];
  const group = /^(insertText|deleteContentBackward|deleteContentForward)$/.test(kind) && f.lastEditKind === kind &&
    now - (f.lastEditAt || 0) < 700 && f.historyIndex > 0 && f.historyIndex === f.history.length - 1 &&
    before[0] === current.selection[0] && before[1] === current.selection[1];
  const next = {text:ta.value,selection:[ta.selectionStart,ta.selectionEnd]};
  if (group) f.history[f.historyIndex] = next;
  else {
    current.selection = before.slice(); f.history.splice(f.historyIndex + 1); f.history.push(next); f.historyIndex++;
    let size = f.history.reduce((n,s) => n + s.text.length,0);
    while (f.history.length > 2 && (f.history.length > 100 || size > 4000000)) { size -= f.history.shift().text.length; f.historyIndex--; }
  }
  f.lastEditKind = kind; f.lastEditAt = now; f.beforeSelection = null;
}
function editRange(ta, start, end, text, selection) {
  if (!ta || ta.readOnly) return;
  const f = S.files.get(S.active); f.beforeSelection = [ta.selectionStart,ta.selectionEnd];
  ta.setRangeText(text,start,end,'end');
  if (selection) ta.setSelectionRange(...selection);
  ta.focus(); onEdInput({target:ta,inputType:'command'});
}
function undoEdit(redo = false) {
  const f = S.files.get(S.active), ta = $('#edta');
  if (!f || !ta || f.readonly) return;
  const index = f.historyIndex + (redo ? 1 : -1);
  if (index < 0 || index >= f.history.length) return;
  f.history[f.historyIndex].selection = [ta.selectionStart,ta.selectionEnd];
  f.historyIndex = index; const snap = f.history[index];
  f.text = ta.value = snap.text; f.lines = f.text.split('\n'); f.dirty = f.text !== f.saved; f.lastEditKind = ''; f.beforeSelection = null;
  ta.setSelectionRange(...snap.selection); hideCompletions(); refreshFind();
  f.html = highlight(f.text,FIND.hits,FIND.index); syncRows(f); renderTabs(); updateEdInfo(); updateCursor(ta); ta.focus(); ensureCaret(ta);
}
function lineRange(ta) {
  const v = ta.value, s = ta.selectionStart, e = ta.selectionEnd;
  const start = lineStartAt(v,s);
  let end = v.indexOf('\n',e > s && v[e - 1] === '\n' ? e - 1 : e);
  if (end < 0) end = v.length;
  return {start,end,text:v.slice(start,end)};
}
function indentLines(outdent = false) {
  const ta = $('#edta'); if (!ta || ta.readOnly) return;
  if (ta.selectionStart === ta.selectionEnd && !outdent) {
    const col = ta.selectionStart - lineStartAt(ta.value,ta.selectionStart);
    editRange(ta,ta.selectionStart,ta.selectionEnd,' '.repeat(4 - col % 4)); return;
  }
  const r = lineRange(ta), rows = r.text.split('\n'), changes = rows.map(l => outdent ? -(l.match(/^( {1,4}|\t)/) || [''])[0].length : 4);
  const text = rows.map((l,i) => outdent ? l.slice(-changes[i]) : '    ' + l).join('\n');
  const s = ta.selectionStart, e = ta.selectionEnd;
  const start = Math.max(r.start,s + changes[0]);
  const end = e === s ? start : Math.max(start,e + changes.reduce((a,b) => a + b,0));
  editRange(ta,r.start,r.end,text,[start,end]);
}
function toggleComments() {
  const ta = $('#edta'); if (!ta || ta.readOnly) return;
  const r = lineRange(ta), rows = r.text.split('\n'), nonblank = rows.filter(l => l.trim());
  const remove = nonblank.length && nonblank.every(l => /^\s*#/.test(l));
  const indent = nonblank.length ? Math.min(...nonblank.map(l => l.match(/^[ \t]*/)[0].length)) : 0;
  const text = rows.map(l => remove ? l.replace(/^(\s*)# ?/,'$1') : l.trim() || rows.length === 1 ? l.slice(0,indent) + '# ' + l.slice(indent) : l).join('\n');
  editRange(ta,r.start,r.end,text,[r.start,r.start + text.length]);
}
function duplicateLines() {
  const ta = $('#edta'); if (!ta || ta.readOnly) return;
  const r = lineRange(ta), s = ta.selectionStart, e = ta.selectionEnd, offset = r.text.length + 1;
  editRange(ta,r.end,r.end,'\n' + r.text,[s + offset,e + offset]);
}
function moveLines(down) {
  const ta = $('#edta'); if (!ta || ta.readOnly) return;
  const r = lineRange(ta), s = ta.selectionStart, e = ta.selectionEnd;
  if (down) {
    if (r.end === ta.value.length) return;
    let end = ta.value.indexOf('\n',r.end + 1); if (end < 0) end = ta.value.length;
    const next = ta.value.slice(r.end + 1,end), delta = next.length + 1;
    editRange(ta,r.start,end,next + '\n' + r.text,[s + delta,e + delta]);
  } else {
    if (!r.start) return;
    const start = lineStartAt(ta.value,r.start - 1), prev = ta.value.slice(start,r.start - 1), delta = prev.length + 1;
    editRange(ta,start,r.end,r.text + '\n' + prev,[s - delta,e - delta]);
  }
}
function pythonContext(text, end) {
  let quote = '', triple = false, comment = false;
  for (let i = 0; i < end; i++) {
    const c = text[i];
    if (comment) { if (c === '\n') comment = false; continue; }
    if (quote) {
      if (c === '\\') { i++; continue; }
      if (triple) { if (text.slice(i,i + 3) === quote.repeat(3) && i + 3 <= end) { quote = ''; triple = false; i += 2; } }
      else if (c === quote || c === '\n') quote = '';
    } else if (c === '#') comment = true;
    else if (c === '"' || c === "'") {
      quote = c; triple = text.slice(i,i + 3) === c.repeat(3) && i + 3 <= end; if (triple) i += 2;
    }
  }
  return {quote,comment};
}
function onEdKey(e) {
  const ta = e.target, mod = e.ctrlKey || e.metaKey;
  if (e.isComposing) return;
  if (COMPLETE.items.length && ['ArrowDown','ArrowUp','Enter','Tab','Escape'].includes(e.key)) {
    e.preventDefault(); e.stopPropagation();
    if (e.key === 'Escape') hideCompletions();
    else if (e.key === 'Enter' || e.key === 'Tab') acceptCompletion();
    else { COMPLETE.index = (COMPLETE.index + (e.key === 'ArrowDown' ? 1 : -1) + COMPLETE.items.length) % COMPLETE.items.length; renderCompletions(); }
    return;
  }
  if (COMPLETE.items.length) hideCompletions();
  if (mod && ['z','y'].includes(e.key.toLowerCase())) { e.preventDefault(); undoEdit(e.shiftKey || e.key.toLowerCase() === 'y'); return; }
  if (ta.readOnly) return;
  if (mod && e.code === 'Space') { e.preventDefault(); suggestWords(); return; }
  if (mod && e.key === '/') { e.preventDefault(); toggleComments(); return; }
  if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) { e.preventDefault(); e.shiftKey ? duplicateLines() : moveLines(e.key === 'ArrowDown'); return; }
  if (e.key === 'Tab') { e.preventDefault(); indentLines(e.shiftKey); return; }
  if (mod || e.altKey) return;
  const v = ta.value, s = ta.selectionStart, end = ta.selectionEnd;
  const pairs = {'(':')','[':']','{':'}','"':'"',"'":"'"};
  const context = pythonContext(v,s);
  if (e.key === 'Backspace' && s > 0 && s === end && pairs[v[s - 1]] === v[s] && !context.comment && (!context.quote || context.quote === v[s - 1])) {
    e.preventDefault(); editRange(ta,s - 1,s + 1,''); return;
  }
  if (!context.quote && !context.comment && s === end && ')]}'.includes(e.key) && v[s] === e.key) { e.preventDefault(); ta.setSelectionRange(s + 1,s + 1); updateCursor(ta); return; }
  if (Object.prototype.hasOwnProperty.call(pairs,e.key)) {
    // Pair only outside strings/comments; triple quotes remain ordinary input.
    const quote = e.key === '"' || e.key === "'";
    if (quote && context.quote === e.key && !context.comment && s === end && v[s] === e.key) { e.preventDefault(); ta.setSelectionRange(s + 1,s + 1); updateCursor(ta); return; }
    if (!context.quote && !context.comment && (!quote || !/[\w'"\\]/.test(v[s - 1] || '')) && (s !== end || !/[\w]/.test(v[end] || ''))) {
      e.preventDefault(); const text = e.key + v.slice(s,end) + pairs[e.key];
      editRange(ta,s,end,text,[s + 1,end + 1]); return;
    }
  }
  if (e.key === 'Enter') {
    e.preventDefault();
    const line = v.slice(lineStartAt(v,s),s), baseIndent = line.match(/^[ \t]*/)[0];
    let indent = baseIndent; if (!context.quote && (/^[^#]*:\s*(#.*)?$/.test(line) || (!context.comment && /[([{]\s*$/.test(line)))) indent += '    ';
    const splitPair = !context.quote && !context.comment && s === end && ['()', '[]', '{}'].includes(v.slice(s - 1,s + 1));
    const text = '\n' + indent + (splitPair ? '\n' + baseIndent : '');
    editRange(ta,s,end,text,[s + 1 + indent.length,s + 1 + indent.length]);
  }
}

/* ---------------- find / replace and local word suggestions ---------------- */
const FIND = {open:false,hits:[],index:-1,error:'',limit:false};
const COMPLETE = {items:[],index:0,start:0,end:0};
function findPattern() {
  let query = $('#findtext').value; if (!query) return null;
  if (!$('#findregex').checked) query = query.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
  if ($('#findword').checked) query = '\\b(?:' + query + ')\\b';
  return new RegExp(query,'gm' + ($('#findcase').checked ? '' : 'i'));
}
function refreshFind() {
  FIND.hits = []; FIND.error = ''; FIND.limit = false;
  const f = S.files.get(S.active), ta = $('#edta');
  if (FIND.open && f && !f.error) {
    try {
      const re = findPattern(); let m;
      if (re) while ((m = re.exec(f.text))) {
        if (!m[0].length) { re.lastIndex = m.index + 1; continue; }
        if (FIND.hits.length === 5000) { FIND.limit = true; break; }
        FIND.hits.push({start:m.index,end:m.index + m[0].length});
      }
    } catch (e) { FIND.error = 'Invalid regex'; }
  }
  const caret = ta && ta.value === (f || {}).text ? ta.selectionStart : f && f.selection ? f.selection[0] : 0;
  FIND.index = FIND.hits.findIndex(h => h.start >= caret); if (FIND.index < 0 && FIND.hits.length) FIND.index = 0;
  updateFindCount();
}
function updateFindCount() {
  const count = $('#findcount'); count.className = FIND.error ? 'error' : '';
  count.textContent = FIND.error || (FIND.hits.length ? (FIND.index + 1) + ' / ' + FIND.hits.length + (FIND.limit ? '+' : '') : 'No matches');
  const f = S.files.get(S.active), writable = f && !f.error && !f.readonly;
  $('#findprev').disabled = $('#findnext').disabled = !FIND.hits.length;
  $('#replaceone').disabled = $('#replaceall').disabled = !writable || !FIND.hits.length;
}
function paintSearch() {
  const f = S.files.get(S.active); if (f && !f.error) { f.html = highlight(f.text,FIND.hits,FIND.index); syncRows(f); }
}
function openFind(replace = false) {
  hideCompletions();
  FIND.open = true; $('#findbar').hidden = false; $('#replacerow').hidden = !replace;
  const ta = $('#edta'); if (ta && ta.selectionEnd > ta.selectionStart) {
    const selected = ta.value.slice(ta.selectionStart,ta.selectionEnd); if (!selected.includes('\n')) $('#findtext').value = selected;
  }
  refreshFind(); paintSearch(); $('#findtext').focus(); $('#findtext').select();
}
function closeFind() { FIND.open = false; $('#findbar').hidden = true; refreshFind(); paintSearch(); const ta = $('#edta'); if (ta) ta.focus(); }
function nextMatch(backward = false, fromInput = false) {
  if (!FIND.hits.length) return;
  const ta = $('#edta'), current = FIND.hits[FIND.index];
  const selected = ta && current && ta.selectionStart === current.start && ta.selectionEnd === current.end;
  if (selected) FIND.index = (FIND.index + (backward ? -1 : 1) + FIND.hits.length) % FIND.hits.length;
  else {
    FIND.index = FIND.hits.findIndex(h => h.start >= ta.selectionStart); if (FIND.index < 0) FIND.index = 0;
    if (backward) FIND.index = (FIND.index - 1 + FIND.hits.length) % FIND.hits.length;
  }
  const h = FIND.hits[FIND.index]; ta.setSelectionRange(h.start,h.end); if (!fromInput) ta.focus();
  updateCursor(ta); ensureCaret(ta); updateFindCount(); paintSearch();
}
function replaceMatches(all) {
  const ta = $('#edta'), f = S.files.get(S.active); if (!ta || !f || f.readonly || !FIND.hits.length || FIND.error) return;
  const re = findPattern(), replacement = $('#replacetext').value;
  if (all) {
    const text = replaceNonempty(f.text,re,replacement,!$('#findregex').checked);
    editRange(ta,0,f.text.length,text,[0,0]);
  } else {
    const h = FIND.hits[FIND.index];
    const one = new RegExp(re.source,re.flags.replace('g','') + 'y'); one.lastIndex = h.start;
    const result = f.text.replace(one,$('#findregex').checked ? replacement : () => replacement);
    const inserted = result.slice(h.start,result.length - (f.text.length - h.end));
    editRange(ta,h.start,h.end,inserted);
  }
  refreshFind(); paintSearch();
}
function replaceNonempty(text, re, replacement, literal) {
  const parts = []; let m, last = 0;
  while ((m = re.exec(text))) {
    if (!m[0].length) { re.lastIndex = m.index + 1; continue; }
    const inserted = literal ? replacement : replacement.replace(/\$(\$|&|`|'|<[^>]*>|\d{1,2})/g,(token,k) => {
      if (k === '$') return '$'; if (k === '&') return m[0];
      if (k === '`') return text.slice(0,m.index); if (k === "'") return text.slice(m.index + m[0].length);
      if (k[0] === '<') return m.groups ? (m.groups[k.slice(1,-1)] || '') : token;
      if (+k > 0 && +k < m.length) return m[+k] || '';
      if (k.length === 2 && +k[0] > 0 && +k[0] < m.length) return (m[+k[0]] || '') + k[1];
      return token;
    });
    parts.push(text.slice(last,m.index),inserted); last = m.index + m[0].length;
  }
  parts.push(text.slice(last)); return parts.join('');
}
function goToLine() {
  const ta = $('#edta'); if (!ta) return;
  hideCompletions();
  const answer = prompt('Go to line (or line:column)',String(ta.value.slice(0,ta.selectionStart).split('\n').length));
  if (answer === null) return;
  const m = /^\s*(\d+)(?::(\d+))?\s*$/.exec(answer);
  if (!m || +m[1] < 1 || (m[2] && +m[2] < 1)) { toast('Enter a line number, such as 12 or 12:4'); return; }
  const lines = ta.value.split('\n'), line = Math.min(+m[1],lines.length) - 1;
  const pos = lines.slice(0,line).reduce((n,l) => n + l.length + 1,0) + Math.min((+(m[2] || 1)) - 1,lines[line].length);
  ta.setSelectionRange(pos,pos); ta.focus(); updateCursor(ta); ensureCaret(ta);
}
function hideCompletions() { COMPLETE.items = []; $('#completions').hidden = true; }
function suggestWords() {
  const ta = $('#edta'); if (!ta || ta.readOnly) return;
  const match = /[A-Za-z_]\w*$/.exec(ta.value.slice(0,ta.selectionStart));
  if (!match) { toast('Type the start of a name, then press Ctrl+Space'); return; }
  const prefix = match[0], words = new Set([...KW,...(ta.value.match(/\b[A-Za-z_]\w*\b/g) || []),...'print len range enumerate zip sorted sum min max open str int float list dict set tuple isinstance super'.split(' ')]);
  COMPLETE.items = [...words].filter(w => w !== prefix && w.startsWith(prefix)).sort().slice(0,8);
  COMPLETE.start = ta.selectionStart - prefix.length; COMPLETE.end = ta.selectionStart; COMPLETE.index = 0;
  if (!COMPLETE.items.length) { hideCompletions(); toast('No local word suggestions'); return; }
  ta.focus(); renderCompletions();
}
function renderCompletions() {
  const host = $('#completions'); host.textContent = ''; host.hidden = false;
  host.appendChild(el('div','label','Words in this file + Python keywords · ↑↓ Enter · Esc'));
  COMPLETE.items.forEach((word,i) => { const b = el('button',i === COMPLETE.index ? 'on' : '',word); b.onmousedown = e => e.preventDefault(); b.onclick = () => { COMPLETE.index = i; acceptCompletion(); }; host.appendChild(b); });
}
function acceptCompletion() {
  const ta = $('#edta'), word = COMPLETE.items[COMPLETE.index]; if (!ta || !word) return;
  editRange(ta,COMPLETE.start,COMPLETE.end,word); hideCompletions();
}
$('#bundo').onclick = () => undoEdit(); $('#bredo').onclick = () => undoEdit(true);
$('#bfind').onclick = () => openFind(); $('#breplace').onclick = () => openFind(true);
$('#bgoto').onclick = $('#bgotofooter').onclick = goToLine; $('#bcomment').onclick = toggleComments; $('#bcomplete').onclick = suggestWords;
$('#findclose').onclick = closeFind; $('#findprev').onclick = () => nextMatch(true); $('#findnext').onclick = () => nextMatch();
$('#replaceone').onclick = () => replaceMatches(false); $('#replaceall').onclick = () => replaceMatches(true);
['findtext','findcase','findword','findregex'].forEach(id => $('#' + id).addEventListener('input',() => { refreshFind(); paintSearch(); }));
$('#findtext').addEventListener('keydown',e => { if (e.key === 'Enter') { e.preventDefault(); nextMatch(e.shiftKey,true); } });
function shiftBreaks(path, oldT, newT) {
  const s = S.breaks.get(path); if (!s || !s.size) return false;
  const a = oldT.split('\n'), b = newT.split('\n'); let p = 0;
  while (p < a.length && p < b.length && a[p] === b[p]) p++;
  let q = 0; while (q < a.length - p && q < b.length - p && a[a.length - 1 - q] === b[b.length - 1 - q]) q++;
  const delta = b.length - a.length, out = new Set();
  s.forEach(n => { if (n <= p) out.add(n); else if (n > a.length - q) out.add(n + delta); });
  const changed = out.size !== s.size || [...s].some(n => !out.has(n));
  S.breaks.set(path, out); return changed;
}
async function saveFile(f) {
  if (!f || f.error || f.readonly || !f.dirty) return;
  if (f.saving) { try { await f.saving; } catch (e) { return false; } return saveFile(f); }
  // An edit made while the HTTP request is in flight must stay marked dirty.
  const text = f.text, previous = f.saved;
  f.saving = post('save', {path: f.path, text, crlf: f.crlf});
  let r;
  try { r = await f.saving; } catch (e) { toast('Save failed: ' + e.message); return false; }
  finally { f.saving = null; }
  if (r.error) { toast('Save failed: ' + r.error); return; }
  if (shiftBreaks(f.path, previous, text)) syncBreaks();
  f.saved = text; f.dirty = f.text !== text; renderTabs(); updateEdInfo(); marks();
  toast(f.dirty ? 'Saved snapshot — newer edits are still unsaved' : S.state === 'idle' ? 'Saved' : 'Saved — Restart to run the new code');
  return true;
}
$('#bsave').onclick = () => saveFile(S.files.get(S.active));
async function saveAll() {
  for (const f of S.files.values()) if (f.dirty && !f.readonly && !f.error) await saveFile(f);
}
$('#bsaveall').onclick = saveAll;
function marks(flash) {
  const c = $('#code');
  c.querySelectorAll('.cur,.caller,.exc,.bp,.trail,.flash').forEach(e => e.classList.remove('cur', 'caller', 'exc', 'bp', 'trail', 'flash'));
  if (S.stop && S.trail && S.trail.file === S.active) { const t = document.getElementById('L' + S.trail.line); if (t) t.classList.add('trail'); }
  const bs = S.breaks.get(S.active);
  if (bs) bs.forEach(n => { const e = document.getElementById('L' + n); if (e) e.classList.add('bp'); });
  if (S.stop) S.stop.stack.forEach((fr, i) => {
    if (fr.file !== S.active) return;
    const e = document.getElementById('L' + fr.line); if (!e) return;
    if (i === S.sel) { e.classList.remove('trail'); e.classList.add(S.stop.reason === 'exception' && i === S.stop.idx ? 'exc' : 'cur'); if (flash) e.classList.add('flash'); } else e.classList.add('caller');
  });
}
function scrollTo(line) {
  const e = document.getElementById('L' + line), c = $('#code'); if (!e) return;
  const er = e.getBoundingClientRect(), cr = c.getBoundingClientRect();
  if (er.top < cr.top + 20 || er.bottom > cr.bottom - 20) c.scrollTop += (er.top - cr.top) - cr.height / 2;
  c.scrollLeft = 0;
}
function toggleBp(n) {
  const f = S.files.get(S.active); if (!f || f.error) return;
  if (!codeLike(f.lines[n - 1])) return;
  let s = S.breaks.get(f.path); if (!s) S.breaks.set(f.path, s = new Set());
  s.has(n) ? s.delete(n) : s.add(n);
  marks(); syncBreaks();   // takes effect immediately, even while paused or running
}
let breakSync = Promise.resolve();
function syncBreaks() {
  const files = {}; S.breaks.forEach((s, p) => { if (s.size) files[p] = [...s].sort((a, b) => a - b); });
  breakSync = breakSync.then(() => post('breaks', {files})).catch(() => {});   // delivered in order
}

/* ---------------- file tree & folder browser ---------------- */
function treeNode(entry, depth, onFile, container, onDbl) {
  const wrap = el('div'), row = el('div', 'ti' + (entry.dir ? ' dir' : ''));
  row.style.paddingLeft = (depth * 12 + 4) + 'px';
  const tg = el('span', 'tg', entry.dir ? '▸' : ''); row.appendChild(tg); row.appendChild(document.createTextNode(entry.name));
  row.title = entry.path; wrap.appendChild(row);
  const kids = el('div'); wrap.appendChild(kids);
  let open = false;
  row.onclick = async () => {
    if (!entry.dir) { onFile(entry, row); return; }
    open = !open; tg.textContent = open ? '▾' : '▸'; kids.textContent = '';
    if (open) { const r = await get('ls', {path: entry.path, files: 1}); (r.entries || []).forEach(e => kids.appendChild(treeNode(e, depth + 1, onFile, null, onDbl))); markScriptRow(); }
  };
  if (!entry.dir && onDbl) row.ondblclick = () => onDbl(entry, row);
  container && container.appendChild(wrap);
  return wrap;
}
async function loadTree() {
  const t = $('#tree'); t.textContent = '';
  const r = await get('ls', {path: S.cfg.root, files: 1});
  if (r.error) { t.appendChild(el('div', 'msg', r.error)); return; }
  const onFile = async en => { await openFile(en.path); if (!S.cfg.script && /\.py$/i.test(en.path)) setScript(en.path); };   // first file opened becomes the Script
  const onDbl = async en => { await openFile(en.path); if (/\.py$/i.test(en.path)) { setScript(en.path); toast('Script: ' + S.cfg.script); } };
  (r.entries || []).forEach(e => t.appendChild(treeNode(e, 0, onFile, null, onDbl)));
  markScriptRow();
}
function markScriptRow() {
  document.querySelectorAll('#tree .ti').forEach(r => r.classList.toggle('run', !r.classList.contains('dir') && !!S.cfg.script && (r.title === S.cfg.script || rel(r.title) === S.cfg.script)));
}
const rel = p => { const r = S.cfg.root || ''; return r && p.startsWith(r) ? p.slice(r.length).replace(/^[\\/]/, '') : p; };
function setScript(p) { S.cfg.script = rel(p); $('#script').value = S.cfg.script; pushCfg(); markScriptRow(); }
function showModal(title) { $('#mtitle').textContent = title; $('#mctl').textContent = ''; $('#modal').classList.add('on'); }
$('#mclose').onclick = () => { $('#modal').classList.remove('on'); S.tbl = null; };
async function browse(path) {
  showModal('Select folder');
  const body = $('#mbody'); body.textContent = '';
  const r = await get('ls', {path: path || S.cfg.root || ''});
  const top = el('div', 'msg', r.path || '(computer)'); body.appendChild(top);
  const pick = el('button', null, 'Use this folder'); pick.style.margin = '0 1em .5em'; pick.disabled = !r.path;
  pick.onclick = () => { $('#modal').classList.remove('on'); $('#root').value = r.path; applyRoot(); };
  body.appendChild(pick);
  if (r.parent !== null && r.path) { const up = el('div', 'ti dir', '↑ ..'); up.onclick = () => browse(r.parent); body.appendChild(up); }
  (r.entries || []).forEach(e => { const d = el('div', 'ti dir', e.name); d.onclick = () => browse(e.path); body.appendChild(d); });
}
function applyRoot() { S.cfg.root = $('#root').value.trim(); pushCfg(); loadTree(); }

/* ---------------- manual ---------------- */
const MANUAL = `<div class="man">
<h2>Quick start</h2>
<ol>
<li>Type a folder path in <b>Folder</b> and press Enter (or <b>Browse…</b>). The file tree appears on the left. The tool remembers your last folder, script and settings.</li>
<li>Click a <code>.py</code> file to open it in the editor. <b>Double-click</b> a file to make it the <b>Script</b> that Run/Restart launches (marked with ▶ in the tree; the first file you open is chosen automatically). Opening other files, e.g. to set breakpoints, never changes the Script.</li>
<li>Click in the gutter (left of a line number) to set a breakpoint <span class="sw"></span>. Click again to remove it.</li>
<li>Press <b>Run</b>. Execution stops at your first breakpoint and the line turns accent-colored: <b>PAUSED</b>.</li>
<li>Step with the toolbar or the keyboard, inspect variables on the right, type Python in the terminal at the bottom.</li>
</ol>

<h2>Toolbar &amp; keyboard</h2>
<table>
<tr><th>Control</th><th>Key</th><th>What it does</th></tr>
<tr><td><b>Run</b></td><td></td><td>Start the script under the debugger. Runs until a breakpoint, an uncaught exception, or the end.</td></tr>
<tr><td><b>Continue</b></td><td><kbd>F8</kbd></td><td>Run until the next breakpoint (or the end).</td></tr>
<tr><td><b>Step Over</b></td><td><kbd>F10</kbd></td><td>Run the current line completely, including any function it calls, and stop at the next line in this function.</td></tr>
<tr><td><b>Step Into</b></td><td><kbd>F11</kbd></td><td>If the current line calls a function, stop on its first line, <i>even if it is defined in another file</i> (that file opens in a new tab). Otherwise acts like Step Over.</td></tr>
<tr><td><b>Step Out</b></td><td><kbd>Shift</kbd>+<kbd>F11</kbd></td><td>Run until the current function returns, then stop in the caller.</td></tr>
<tr><td><b>Stop</b></td><td></td><td>Kill the program. Always works, paused or running.</td></tr>
<tr><td><b>Restart</b></td><td></td><td>Stop and run again with the current settings and the code on disk. Breakpoints and watches are kept.</td></tr>
<tr><td><b>Save</b></td><td><kbd>Ctrl</kbd>+<kbd>S</kbd></td><td>Save the current file (see Editing).</td></tr>
<tr><td><b>A− / A+</b></td><td><kbd>Ctrl</kbd>+<kbd>−</kbd> / <kbd>+</kbd></td><td>Make only the text smaller / larger.</td></tr>
<tr><td><b>Settings</b></td><td></td><td>Font size, theme, accent color, environment variables.</td></tr>
<tr><td><b>Help</b></td><td><kbd>F1</kbd></td><td>This manual. <kbd>Esc</kbd> closes any pop-up.</td></tr>
</table>
<p>On a Mac laptop the F-keys may need <kbd>fn</kbd>; the buttons always work. Step buttons are only enabled while paused.</p>

<h2>Editing code</h2>
<ul>
<li>The editor is always editable: click in the code and type. A <b>●</b> on the tab and the word <i>modified</i> show unsaved changes.</li>
<li><kbd>Ctrl</kbd>+<kbd>S</kbd> (or the Save button) writes the file to disk. Line endings (LF / CRLF) are preserved.</li>
<li><b>Save all</b> or <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>S</kbd> writes all modified, writable tabs. Typing while a save is in progress keeps the newer edits marked as unsaved.</li>
<li><kbd>Tab</kbd> advances to the next 4-space indent stop; with several lines selected it indents them; <kbd>Shift</kbd>+<kbd>Tab</kbd> un-indents. <kbd>Enter</kbd> keeps indentation and adds 4 spaces after a block colon or opening bracket. Between a bracket pair it creates an indented blank line.</li>
<li><b>Undo / Redo:</b> <kbd>Ctrl</kbd>+<kbd>Z</kbd>, <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd> or <kbd>Ctrl</kbd>+<kbd>Y</kbd>. Each tab retains its own in-memory history and cursor position. History survives saving and tab switches, but not closing the tab or reloading the page.</li>
<li><b>Find / Replace:</b> <kbd>Ctrl</kbd>+<kbd>F</kbd> / <kbd>Ctrl</kbd>+<kbd>H</kbd>. Search the current file with match-case, whole-word, or JavaScript regex options. <kbd>Enter</kbd> / <kbd>Shift</kbd>+<kbd>Enter</kbd> navigate matches while the find field is focused; <kbd>F3</kbd> / <kbd>Shift</kbd>+<kbd>F3</kbd> navigate from the editor. <kbd>Esc</kbd> closes find. Regex replacements support capture groups such as <code>$1</code>; literal replacements keep dollar signs unchanged. Zero-width matches are skipped. Highlighting is limited to 5,000 matches; Replace all processes every nonempty match in the file as one undoable edit.</li>
<li><b>Go to line:</b> <kbd>Ctrl</kbd>+<kbd>G</kbd>; enter <code>12</code> or <code>12:4</code> for a column. The status bar shows the current line, column, selection size, and line endings.</li>
<li><b>Line commands:</b> <kbd>Ctrl</kbd>+<kbd>/</kbd> toggles comments on the current or selected lines. <kbd>Alt</kbd>+<kbd>↑</kbd> / <kbd>↓</kbd> moves lines. <kbd>Alt</kbd>+<kbd>Shift</kbd>+<kbd>↓</kbd> duplicates them.</li>
<li><b>Pairs:</b> brackets and quotes close automatically outside strings/comments; selected text can be wrapped in a pair. Backspace between an empty pair removes both characters.</li>
<li><b>Suggest:</b> type the start of a name and press <kbd>Ctrl</kbd>+<kbd>Space</kbd>, or use the Suggest button. Candidates come from this file, Python keywords, and common built-ins. Choose with <kbd>↑</kbd> / <kbd>↓</kbd>, accept with <kbd>Enter</kbd> / <kbd>Tab</kbd>, dismiss with <kbd>Esc</kbd>. This is word completion, without type analysis or external packages.</li>
<li>On Mac, use <kbd>Cmd</kbd> for Ctrl-based commands except <kbd>Ctrl</kbd>+<kbd>Space</kbd>. Normal copy, cut, paste and select-all work in the editor.</li>
<li><b>A running program is not changed by edits.</b> Save, then press <b>Restart</b> to run the new code. While you are paused, the marker lines refer to the code as it was when the program started.</li>
<li>When you save, breakpoints below your edit move with the code (if you inserted or deleted lines above them); breakpoints on lines you deleted are dropped.</li>
<li>Files outside the project folder (libraries you stepped into) and files that are not valid UTF-8 open <b>read-only</b>.</li>
<li>Not included: semantic autocomplete, multi-cursor, code folding, or project-wide refactoring.</li>
</ul>

<h2>Settings row</h2>
<table>
<tr><td><b>Folder</b></td><td>The project root. It is also the working directory of your script, so relative paths such as <code>data/x.csv</code> resolve from here.</td></tr>
<tr><td><b>Script</b></td><td>File to run (relative to Folder). Set by double-clicking a file in the tree (or typing here). Run and Restart always launch this file, not the tab you are looking at.</td></tr>
<tr><td><b>Args</b></td><td>Command-line arguments, as you would type them after <code>python script.py</code>. Quotes work.</td></tr>
<tr><td><b>Python</b></td><td>Interpreter used to run the script (e.g. a venv's <code>python.exe</code>). Defaults to the one that started this tool.</td></tr>
<tr><td><b>stop on entry</b></td><td>Pause on the very first line instead of running to a breakpoint.</td></tr>
<tr><td><b>just my code</b></td><td>On: stepping never enters the standard library or installed packages (it steps over them). Off: you can step into any code, e.g. <code>json/__init__.py</code>. Can be toggled while running.</td></tr>
</table>

<h2>Settings menu (⚙) and the settings file</h2>
<ul>
<li><b>Text-only zoom</b>: the <b>A−</b> / <b>A+</b> buttons in the toolbar, <kbd>Ctrl</kbd>+<kbd>+</kbd> / <kbd>Ctrl</kbd>+<kbd>−</kbd> (<kbd>Cmd</kbd> on Mac), <kbd>Ctrl</kbd>+scroll wheel, and <kbd>Ctrl</kbd>+<kbd>0</kbd> to reset. They change <i>only the size of the text</i> (code, panels, tables, console); panel sizes stay as you set them, unlike the browser's own zoom (its menu still works as usual and scales everything).</li>
<li><b>Font size</b> (also settable here by number), <b>font family</b>, <b>line spacing</b>.</li>
<li><b>Workspace theme</b>: Daylight, Graphite, Midnight, Parchment, Forest, or High contrast. <b>Viewer / editor</b> can match the workspace or use a different preset. The live code preview shows your selection.</li>
<li><b>Custom colors</b>: adjust editor background, text, keywords, strings, comments, numbers, and gutter. <b>Reset editor colors</b> clears overrides; choosing an editor preset also clears them. <b>Accent color</b> controls buttons, breakpoints, and execution highlights.</li>
<li><b>Style files</b>: export appearance to a local JSON file, then import it on another machine. Styles contain only validated appearance settings, never code, environment variables, or project paths. No CSS, JavaScript, fonts, images, or stylesheets are downloaded.</li>
<li><b>Environment variables</b>: your script always inherits the environment of the terminal that started this tool. In addition you can add <code>KEY=VALUE</code> lines here (one per line, <code>#</code> for comments, <code>$OTHER</code>/<code>%OTHER%</code> are expanded), and tick <i>load .env from the project folder</i>. Order of precedence: this list overrides <code>.env</code>, which overrides the inherited environment.</li>
<li>Everything is saved automatically to <code>debugger_settings.json</code> next to <code>debugger.py</code> (or in your home folder if that folder is not writable) and loaded on the next start, so the page opens already themed. It also remembers the last folder, script, arguments, breakpoints and watches. <b>Do not put secrets in it</b>: it is a plain text file. Export secrets in your shell instead.</li>
<li><b>Reset to defaults</b> restores the look; delete the file to forget everything.</li>
</ul>

<h2>Breakpoints</h2>
<ul>
<li>Click the gutter. Blank lines and comment-only lines cannot hold breakpoints.</li>
<li>You can add or remove breakpoints at any time: <i>while the program runs, and also while it is paused at another breakpoint</i>. They take effect immediately, so Continue will stop at a breakpoint you just added further down the code, in the same function, in a caller, in another file, or later in a loop.</li>
<li>Breakpoints work in any file you open, including files you stepped into, and are remembered in the settings file.</li>
</ul>

<h2>Reading the editor</h2>
<ul>
<li><span class="sw"></span> dot: a breakpoint.</li>
<li><b>Tinted line with ▶ and a colored bar</b>: where execution is now (the selected stack frame). It flashes briefly each time you step so you can find it.</li>
<li><b>Small dot + faint tint</b>: the line you just stepped <i>from</i>, so you can see which way you moved.</li>
<li><b>Faint tint</b>: the line in each caller (other stack frames) that is waiting for the call to return.</li>
<li><b>Hatched line</b>: where an uncaught exception was raised.</li>
<li>Tabs: every file you open or step into gets a tab; <b>×</b> closes it (and re-reads it from disk next time).</li>
</ul>

<h2>Hover info (while paused)</h2>
<p>When paused, rest the mouse on a name in the code (about a quarter second) to see what it is, resolved in the live program:</p>
<ul>
<li><b>Functions and methods:</b> signature with defaults and annotations, docstring, and where they are defined (<code>file:line</code>, click to open it). For a method called on an object it also says <i>which class in the inheritance chain actually defines it</i>.</li>
<li><b>Classes:</b> constructor signature, direct bases, docstring and the full <b>MRO</b> (method resolution order). Every class in the MRO is listed with its file and line (clickable); built-ins show "no source".</li>
<li><b>Variables:</b> type, current value, the file where the type is defined, and the type's MRO. For members like <code>first.greet</code> the defining class is marked with ●.</li>
<li><b>Go to definition:</b> <kbd>Ctrl</kbd>+click (<kbd>Cmd</kbd> on Mac) a name to jump to where its function, class or type is defined.</li>
<li>Hover never runs your code: properties and dynamic attributes (<code>__getattr__</code>, DataFrame columns as <code>df.col</code>) show nothing rather than being evaluated. Calls and subscripts (<code>f().x</code>, <code>a[0].x</code>) are not resolved either. Strings and comments are ignored.</li>
<li>It works for names defined in the frame you are looking at: if you browse a file that is not in the current call stack, there is no hover.</li>
</ul>

<h2>Call stack (top right)</h2>
<p>Innermost call on top. <b>Click any frame</b> to jump the editor to that call site and to show that frame's variables; the terminal and watches then run in that frame too. With <i>just my code</i> on, library frames are hidden.</p>

<h2>Variables</h2>
<ul>
<li><b>Locals</b> (inside a function) and <b>Globals</b> (module level; modules, functions and classes are hidden to reduce noise).</li>
<li>Click a row with ▸ to expand: lists, tuples, dicts, sets, enums, objects (their attributes), numpy arrays, DataFrame columns, Series. Long containers load 100 items at a time ("… more").</li>
<li>Rows stay expanded while you keep stepping.</li>
<li>A value with an <span style="background:var(--ac-l);outline:1px solid var(--ac-m);color:var(--ac-d);padding:0 3px">accent tint</span> changed since the previous stop.</li>
<li><b>view</b> button (DataFrame, Series, 1-D/2-D numpy array) opens a paged table with dtypes; use the row/column arrows for big data.</li>
<li>Long values are shortened in the row; print them in the terminal (<code>p name</code>) to see everything.</li>
</ul>

<h2>Watch</h2>
<p>Type any expression (e.g. <code>len(items)</code>, <code>df.shape</code>, <code>total &gt; 100</code>) and press Enter. It is re-evaluated at every stop in the selected frame. Errors are shown instead of a value. <b>×</b> removes a watch. Watches must not have side effects.</p>

<h2>Console &amp; terminal (bottom)</h2>
<p>The area shows your program's output (stderr in accent italics). The prompt <code>&gt;&gt;&gt;</code> works in two modes:</p>
<ul>
<li><b>Paused:</b> a Python prompt that runs <i>inside the selected frame</i>, with that frame's variables.
<ul>
<li>Inspect: <code>x</code>, <code>df.head()</code>, <code>len(items)</code>. Pdb style also works: <code>p x</code>, <code>pp mydict</code>.</li>
<li><b>Change state:</b> <code>enabled = True</code>, <code>count += 1</code>, <code>items.append(3)</code>. The change is real and the program continues with it; the variables panel updates immediately.</li>
<li>Statements, imports and one-liners such as <code>for i in range(3): print(i)</code> work. <kbd>Shift</kbd>+<kbd>Enter</kbd> adds a new line, <kbd>Enter</kbd> runs, <kbd>↑</kbd>/<kbd>↓</kbd> browse history.</li>
<li>Errors print as a normal Python traceback and never break the debugging session.</li>
<li>Terminal code runs untraced: breakpoints are not hit inside it.</li>
</ul></li>
<li><b>Running:</b> what you type is sent to the program's standard input (for <code>input()</code>).</li>
<li><b>Not running:</b> nothing to talk to; press Run.</li>
</ul>
<div class="nt">Assigning to a <i>new</i> name inside a function frame (not an existing variable) creates it in the terminal's scope only; the running function will not see it. Existing variables, globals, and mutations of lists/dicts/objects always take effect.</div>

<h2>Exceptions</h2>
<p>If the script ends with an uncaught exception, the program pauses at the failing line (hatched) with the full stack intact, as in a post-mortem debugger. Inspect variables, walk the call stack, evaluate in the terminal. <b>Continue</b> (or Stop) then ends the program with exit code 1. Exceptions that your code catches do not pause.</p>

<h2>The status line</h2>
<p>The thin line at the very top: <b>gray</b> = idle, <b>dark</b> = running, <b>accent</b> = paused. The text on the right says why you are paused (<i>breakpoint</i>, <i>step</i>, <i>entry</i>, <i>exception</i>) and where.</p>

<h2>Layout</h2>
<p>Drag the thin bars between panels to resize the file tree, the right-hand column and the console. Sizes are remembered.</p>

<h2>Limits &amp; good to know</h2>
<ul>
<li>Only the <b>main thread</b> is debugged; code in other threads or processes is not stopped by breakpoints.</li>
<li>Debugging is slower than normal execution (about 0.7 µs per Python function call). Code with no breakpoints in a file runs nearly full speed.</li>
<li>Big objects: only short previews are computed; expand rows to see more, so the tool stays fast on large DataFrames.</li>
<li>The page works only through the URL printed in the terminal (it contains a private token, localhost only). If you see "forbidden", open the exact URL again. Close the tool with <kbd>Ctrl</kbd>+<kbd>C</kbd> in the terminal that started it.</li>
</ul>

<h2>Troubleshooting</h2>
<table>
<tr><td>Nothing happens on Run</td><td>Check the Script field and the console for <code>[script not found]</code>.</td></tr>
<tr><td>Breakpoint never hits</td><td>The line may not execute (e.g. inside an unused branch), or the file differs from the one that actually runs (a copy elsewhere, or an installed package). Step into the call to see which file is used. If you edited the file, Save and Restart.</td></tr>
<tr><td>Wrong packages / import errors</td><td>Point <b>Python</b> at your project's interpreter.</td></tr>
<tr><td>Step Into doesn't enter a library call</td><td>That is <i>just my code</i>. Untick it to step into library code.</td></tr>
<tr><td>Program waits forever</td><td>It may be waiting for <code>input()</code>: type the answer in the terminal prompt.</td></tr>
<tr><td>Save fails</td><td>The file may be read-only on disk or locked by another program (common on Windows).</td></tr>
</table>
</div>`;

/* ---------------- settings menu ---------------- */
let prefsTimer = 0;
function savePrefsSoon() { clearTimeout(prefsTimer); prefsTimer = setTimeout(() => post('prefs', {prefs: S.prefs}), 250); }
function setPref(k, v) { S.prefs[k] = v; applyPrefs(S.prefs); savePrefsSoon(); if ($('#modal').classList.contains('on') && $('#mtitle').textContent === 'Settings') showSettings(); }
let cfgTimer = 0;
function pushCfgSoon() { clearTimeout(cfgTimer); cfgTimer = setTimeout(pushCfg, 300); }
const ACCENTS = [['Red', '#d71e28'], ['Blue', '#1f6feb'], ['Green', '#1a7f37'], ['Orange', '#c8610a'], ['Purple', '#8250df'], ['Gray', '#555555']];
const STYLE_KEYS = ['font_size','font','line','theme','accent','editor_theme','editor_colors'];
function readStyle(data) {
  if (!data || data.format !== 'pythondebugger-style' || data.version !== 1 || !data.prefs || typeof data.prefs !== 'object' || Array.isArray(data.prefs))
    throw new Error('Choose a PythonDebugger style JSON file (version 1).');
  const p = data.prefs, out = {};
  for (const k of Object.keys(p)) {
    if (!STYLE_KEYS.includes(k)) throw new Error('Unknown style setting: ' + k);
    const v = p[k];
    if ((k === 'font_size' && (!Number.isInteger(v) || v < 9 || v > 32)) ||
        (k === 'font' && !Object.prototype.hasOwnProperty.call(FONTS,v)) ||
        (k === 'line' && !['compact','normal','relaxed'].includes(v)) ||
        (k === 'theme' && !Object.prototype.hasOwnProperty.call(THEMES,v)) ||
        (k === 'editor_theme' && v !== 'match' && !Object.prototype.hasOwnProperty.call(THEMES,v)) ||
        (k === 'accent' && !validColor(v))) throw new Error('Invalid style setting: ' + k);
    if (k === 'editor_colors') {
      if (!v || typeof v !== 'object' || Array.isArray(v)) throw new Error('Editor colors must be an object.');
      for (const [name,color] of Object.entries(v)) if (!EDITOR_FIELDS.some(([f]) => f === name) || !validColor(color))
        throw new Error('Invalid editor color: ' + name);
    }
    out[k] = v;
  }
  if (!Object.keys(out).length) throw new Error('The style has no appearance settings.');
  return out;
}
function exportStyle() {
  const prefs = {}; STYLE_KEYS.forEach(k => prefs[k] = S.prefs[k]);
  const blob = new Blob([JSON.stringify({format:'pythondebugger-style',version:1,prefs}, null, 2)], {type:'application/json'});
  const url = URL.createObjectURL(blob), a = el('a'); a.href = url; a.download = 'pythondebugger-style.json';
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function showSettings() {
  showModal('Settings');
  const b = $('#mbody'), keep = b.scrollTop; b.textContent = '';
  const w = el('div', 'man'); b.appendChild(w);
  const P = S.prefs;
  let rowId = 0;
  const row = (label, ...ctl) => { const r = el('div', 'srow'), l = el('label', null, label); r.appendChild(l); const c = el('div', 'sctl'); ctl.forEach(x => c.appendChild(x)); r.appendChild(c); w.appendChild(r);
    const field = c.querySelector('select,input:not([type=color]),textarea'); if (field) { field.id = 'setting-' + rowId++; l.htmlFor = field.id; }
    else { c.setAttribute('role','group'); c.setAttribute('aria-label',label); } return c; };
  w.appendChild(el('h2', null, 'Appearance'));
  w.appendChild(el('p', 'style-note', 'Built-in styles, local fonts, and a live preview. No downloads or internet connection.'));
  const cards = el('div', 'theme-grid');
  Object.entries(THEMES).forEach(([key,t]) => {
    const card = el('button','theme-card'); card.setAttribute('aria-pressed', String(P.theme === key));
    const dots = el('span','theme-dots'); dots.setAttribute('aria-hidden','true');
    [t.bg,t.text,t.tokens[0]].forEach(color => { const dot = el('i'); dot.style.background = color; dots.appendChild(dot); });
    card.appendChild(dots); card.appendChild(el('span',null,t.label)); card.onclick = () => setPref('theme',key); cards.appendChild(card);
  });
  row('Workspace theme',cards);
  const editorTheme = el('select');
  [['match','Match workspace'], ...Object.entries(THEMES).map(([k,t]) => [k,t.label])].forEach(([key,label]) => {
    const o = el('option',null,label); o.value = key; o.selected = (P.editor_theme || 'match') === key; editorTheme.appendChild(o);
  });
  editorTheme.onchange = () => { S.prefs.editor_colors = {}; setPref('editor_theme',editorTheme.value); };
  row('Viewer / editor',editorTheme);
  const preview = el('pre','theme-preview'); preview.setAttribute('aria-label','Editor theme preview');
  preview.innerHTML = '<span class="c"># A preview of your Python style</span>\n<span class="k">def</span> greet(name):\n    message = <span class="s">"Hello, "</span> + name\n    <span class="k">return</span> message, <span class="n">42</span>';
  w.appendChild(preview);
  const colors = el('div','color-grid'), current = editorColors(P);
  EDITOR_FIELDS.forEach(([key,label]) => {
    const item = el('label','color-item'), input = el('input'), hex = el('code',null,current[key]);
    input.type = 'color'; input.setAttribute('aria-label','Editor ' + label.toLowerCase());
    input.value = mix(hex2rgb(current[key]),hex2rgb(current[key]),0);
    input.oninput = () => { S.prefs.editor_colors = Object.assign({}, S.prefs.editor_colors, {[key]:input.value}); hex.textContent = input.value; applyPrefs(S.prefs); savePrefsSoon(); };
    item.appendChild(input); item.appendChild(el('span',null,label)); item.appendChild(hex); colors.appendChild(item);
  });
  row('Custom colors',colors);
  const clearColors = el('button',null,'Reset editor colors'); clearColors.onclick = () => setPref('editor_colors',{});
  row('Color overrides',clearColors);
  w.appendChild(el('p','style-note','Color overrides apply to the viewer and editor. Choosing an editor preset clears overrides. Workspace and editor themes can be different.'));
  const fs = el('input'); fs.type = 'number'; fs.min = 9; fs.max = 32; fs.value = P.font_size;
  const setFs = v => setPref('font_size', Math.max(9, Math.min(32, Math.round(+v) || 14)));
  const dec = el('button', null, 'A−'), inc = el('button', null, 'A+');
  dec.onclick = () => setFs(P.font_size - 1); inc.onclick = () => setFs(P.font_size + 1); fs.onchange = () => setFs(fs.value);
  row('Font size', dec, fs, el('span', null, 'px'), inc);
  const ff = el('select'); [['default', 'Consolas / Menlo (default)'], ['courier', 'Courier New'], ['lucida', 'Lucida Console / Monaco'], ['system', 'System monospace'], ['sans', 'Sans-serif']]
    .forEach(([k, n]) => { const o = el('option', null, n); o.value = k; if (P.font === k) o.selected = true; ff.appendChild(o); });
  ff.onchange = () => setPref('font', ff.value); row('Font', ff);
  const ls = el('select'); [['compact', 'Compact'], ['normal', 'Normal'], ['relaxed', 'Relaxed']]
    .forEach(([k, n]) => { const o = el('option', null, n); o.value = k; if (P.line === k) o.selected = true; ls.appendChild(o); });
  ls.onchange = () => setPref('line', ls.value); row('Line spacing', ls);
  const sw = ACCENTS.map(([n, h]) => { const x = el('button', 'sw2' + (P.accent.toLowerCase() === h ? ' on' : '')); x.style.background = h; x.title = n; x.onclick = () => setPref('accent', h); return x; });
  const col = el('input'); col.type = 'color'; col.value = P.accent.length === 7 ? P.accent : '#d71e28'; col.onchange = () => setPref('accent', col.value);
  const hx = el('input'); hx.type = 'text'; hx.size = 8; hx.value = P.accent; hx.onchange = () => { if (/^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(hx.value.trim())) setPref('accent', hx.value.trim()); else hx.value = P.accent; };
  row('Accent color', ...sw, col, hx);
  const saveStyle = el('button',null,'Export style…'); saveStyle.onclick = exportStyle;
  const loadStyle = el('button',null,'Import style…'), file = el('input'); file.type = 'file'; file.accept = '.json,application/json'; file.hidden = true;
  loadStyle.onclick = () => file.click();
  const error = el('div','style-error'); error.setAttribute('role','status');
  file.onchange = async () => {
    const chosen = file.files[0]; if (!chosen) return;
    try {
      if (chosen.size > 65536) throw new Error('Style files must be smaller than 64 KB.');
      const prefs = readStyle(JSON.parse(await chosen.text())); clearTimeout(prefsTimer);
      const r = await post('prefs',{prefs:Object.assign({},S.prefs,prefs)});
      if (!r.prefs) throw new Error(r.error || 'Could not save the style.');
      S.prefs = r.prefs; applyPrefs(S.prefs); showSettings(); toast('Style imported');
    } catch (e) { error.textContent = e.message; } finally { file.value = ''; }
  };
  row('Style files',saveStyle,loadStyle,file); w.appendChild(error);
  w.appendChild(el('p','style-note','Save a style as a local JSON file to reuse or share. Only appearance is exported; project paths, environment variables, and code are excluded.'));
  w.appendChild(el('h2', null, 'Environment for the program'));
  const env = el('textarea', 'fld'); env.spellcheck = false; env.placeholder = 'API_URL=http://localhost:8000\nDEBUG=1\n# one KEY=VALUE per line'; env.value = S.cfg.env || '';
  env.oninput = () => { S.cfg.env = env.value; pushCfgSoon(); };
  row('Variables', env);
  const de = el('input'); de.type = 'checkbox'; de.checked = !!S.cfg.dotenv; de.onchange = () => { S.cfg.dotenv = de.checked; pushCfg(); };
  const dl = el('label'); dl.appendChild(de); dl.appendChild(document.createTextNode(' load .env from the project folder')); row('.env file', dl);
  w.appendChild(el('p', 'msg', 'The program also inherits every variable of the terminal that started this tool. This list overrides .env, which overrides the inherited environment. Applied at the next Run.'));
  w.appendChild(el('h2', null, 'Settings file'));
  w.appendChild(el('p', null, S.settingsPath || '(not available)'));
  if (S.settingsError) w.appendChild(el('p', 'nt', S.settingsError));
  const rs = el('button', null, 'Reset appearance to defaults');
  rs.onclick = async () => { clearTimeout(prefsTimer); const r = await post('prefs', {reset: true}); S.prefs = r.prefs; applyPrefs(S.prefs); showSettings(); };
  w.appendChild(rs);
  b.scrollTop = keep;
}
function showHelp() { showModal('Help — manual'); const b = $('#mbody'); b.innerHTML = MANUAL; b.scrollTop = 0; }
$('#bhelp').onclick = showHelp; $('#bset').onclick = showSettings;
/* text-only zoom: changes the font size, never the layout */
function zoomText(delta) { setPref('font_size', Math.max(9, Math.min(32, delta === 0 ? 14 : S.prefs.font_size + delta))); }
$('#bfm').onclick = () => zoomText(-1); $('#bfp').onclick = () => zoomText(1);
let wheelAt = 0;
document.addEventListener('wheel', e => { if (!(e.ctrlKey || e.metaKey)) return; e.preventDefault(); const t = Date.now(); if (t - wheelAt < 60) return; wheelAt = t; zoomText(e.deltaY < 0 ? 1 : -1); }, {passive: false});

/* ---------------- config / controls ---------------- */
function readCfg() {
  S.cfg.root = $('#root').value.trim(); S.cfg.script = $('#script').value.trim(); S.cfg.args = $('#args').value;
  S.cfg.python = $('#python').value.trim(); S.cfg.stop_on_entry = $('#soe').checked; S.cfg.jmc = $('#jmc').checked;
  return S.cfg;
}
function pushCfg() { post('config', readCfg()); }
function writeCfg() {
  $('#root').value = S.cfg.root || ''; $('#script').value = S.cfg.script || ''; $('#args').value = S.cfg.args || '';
  $('#python').value = S.cfg.python || ''; $('#soe').checked = !!S.cfg.stop_on_entry; $('#jmc').checked = S.cfg.jmc !== false;
  markScriptRow();
}
['script', 'args', 'python'].forEach(id => $('#' + id).addEventListener('change', () => { pushCfg(); markScriptRow(); }));
['soe', 'jmc'].forEach(id => $('#' + id).addEventListener('change', pushCfg));
$('#root').addEventListener('keydown', e => { if (e.key === 'Enter') applyRoot(); });
$('#bopen').onclick = applyRoot; $('#bbrowse').onclick = () => browse(S.cfg.root);
const run = () => { out('sys', ''); post('run', readCfg()); };
$('#brun').onclick = run; $('#brestart').onclick = run;
$('#bstop').onclick = () => post('stop');
const cmd = n => async () => { if (S.state === 'paused') { await breakSync; post(n); } };   // breakpoint edits always arrive before Continue/Step
$('#bcont').onclick = cmd('continue'); $('#bnext').onclick = cmd('next'); $('#bstep').onclick = cmd('step'); $('#bout').onclick = cmd('out');
document.addEventListener('keydown', e => {
  if (e.defaultPrevented || e.isComposing) return;
  const mod = e.ctrlKey || e.metaKey, target = e.target;
  const editorContext = !$('#modal').classList.contains('on') && (target === document.body || target.closest('#editor'));
  if (mod && !e.altKey && e.key.toLowerCase() === 's') { e.preventDefault(); e.shiftKey ? saveAll() : saveFile(S.files.get(S.active)); }
  else if (editorContext && mod && !e.altKey && ['f','h','g'].includes(e.key.toLowerCase())) {
    e.preventDefault(); if (e.key.toLowerCase() === 'g') goToLine(); else openFind(e.key.toLowerCase() === 'h');
  }
  else if (editorContext && e.key === 'F3') { e.preventDefault(); if (!FIND.open) openFind(); else nextMatch(e.shiftKey); }
  else if ((e.ctrlKey || e.metaKey) && !e.altKey && ['=', '+', '-', '_', '0'].includes(e.key)) { e.preventDefault(); zoomText(e.key === '0' ? 0 : (e.key === '-' || e.key === '_') ? -1 : 1); }
  else if (e.key === 'Escape') { if (COMPLETE.items.length) hideCompletions(); else if ($('#modal').classList.contains('on')) $('#mclose').click(); else if (FIND.open) closeFind(); }
  else if (e.key === 'F1') { e.preventDefault(); showHelp(); }
  else if (e.key === 'F8') { e.preventDefault(); cmd('continue')(); }
  else if (e.key === 'F10') { e.preventDefault(); cmd('next')(); }
  else if (e.key === 'F11') { e.preventDefault(); e.shiftKey ? cmd('out')() : cmd('step')(); }
});
function setState(state, status) {
  S.state = state; S.status = status; document.body.dataset.state = state;
  const paused = state === 'paused', running = state === 'running';
  ['bcont', 'bnext', 'bstep', 'bout'].forEach(i => $('#' + i).disabled = !paused);
  $('#bstop').disabled = !(paused || running); $('#brun').disabled = paused || running; $('#brestart').disabled = state === 'idle' && !S.cfg.script;
  let t = state;
  if (paused) { const f = S.stop && S.stop.stack[S.stop.idx]; t = 'PAUSED (' + status + ')' + (f ? ' ' + base(f.file) + ':' + f.line : ''); }
  else if (running) t = 'RUNNING'; else if (status) t = 'idle — ' + status;
  $('#status').textContent = t;
}

/* ---------------- console ---------------- */
const OUT = $('#out');
function out(kind, text) {
  if (!text) return;
  const atEnd = OUT.scrollTop + OUT.clientHeight >= OUT.scrollHeight - 8;
  const s = el('span', kind, text); OUT.appendChild(s);
  while (OUT.childNodes.length > 3000) OUT.removeChild(OUT.firstChild);
  if (atEnd) OUT.scrollTop = OUT.scrollHeight;
}
const INP = $('#in');
function fit() { INP.style.height = 'auto'; INP.style.height = Math.min(parseFloat(getComputedStyle(INP).maxHeight) || 110, INP.scrollHeight) + 'px'; }
INP.addEventListener('input', fit);
INP.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); }
  else if (e.key === 'ArrowUp' && !INP.value.includes('\n') && S.hist.length) { e.preventDefault(); S.hpos = Math.max(0, S.hpos - 1); INP.value = S.hist[S.hpos]; }
  else if (e.key === 'ArrowDown' && !INP.value.includes('\n')) { e.preventDefault(); S.hpos = Math.min(S.hist.length, S.hpos + 1); INP.value = S.hist[S.hpos] || ''; }
});
function submit() {
  const src = INP.value; if (!src.trim()) return;
  S.hist.push(src); S.hpos = S.hist.length; INP.value = ''; fit();
  if (S.state === 'paused') {
    out('in', '>>> ' + src.split('\n').join('\n... ') + '\n');
    const id = S.rid++; S.pending.set(id, {type: 'eval'});
    post('eval', {id, src, frame: S.sel});
  } else if (S.state === 'running') post('stdin', {text: src + '\n'});
  else out('sys', '(no active process — press Run, or pause at a breakpoint to evaluate code)\n');
}

/* ---------------- call stack / variables / watch ---------------- */
function renderStack() {
  const c = $('#stack'); c.textContent = '';
  if (!S.stop) return;
  const st = S.stop.stack;
  for (let i = st.length - 1; i >= 0; i--) {
    const fr = st[i]; if (!fr.user && S.cfg.jmc !== false && i !== S.stop.idx) continue;
    const d = el('div', 'frm' + (i === S.sel ? ' on' : '') + (fr.user ? '' : ' lib'), fr.func);
    const l = el('span', 'fl', '  ' + base(fr.file) + ':' + fr.line); d.appendChild(l); d.title = fr.file + ':' + fr.line;
    d.onclick = () => selectFrame(i); c.appendChild(d);
  }
}
async function selectFrame(i) {
  S.sel = i; renderStack(); post('frame', {idx: i});
  const fr = S.stop.stack[i];
  if (fr.exists !== false) { await openFile(fr.file, fr.line); } else { out('sys', '[source not available for ' + fr.file + ']\n'); }
  marks(); scrollTo(fr.line);
}
function valKey(p) { return (S.stop ? S.stop.stack[S.sel].func : '') + '|' + p; }
function nodeRow(n, ppath, depth, host) {
  if (n.more) {
    const r = el('div', 'vrow more', '… more'); r.style.paddingLeft = (depth * 14 + 4) + 'px';
    r.onclick = () => { requestExpand(n.ref, n.offset, host, ppath, depth, r); }; return r;
  }
  const path = ppath + '/' + n.name, wrap = el('div');
  const row = el('div', 'vrow' + (n.ref ? ' ex' : '') + (n.error ? ' er' : '')); row.style.paddingLeft = (depth * 14 + 4) + 'px';
  const tg = el('span', 'tg', n.ref ? '▸' : ''); row.appendChild(tg);
  row.appendChild(el('span', 'nm', n.name));
  if (n.error) row.appendChild(el('span', 'vl', n.error));
  else {
    row.appendChild(el('span', 'ty', n.type));
    const v = el('span', 'vl', n.value); v.title = n.value; row.appendChild(v);
    const k = valKey(path); S.curVals.set(k, n.value);
    if (S.prevVals.has(k) && S.prevVals.get(k) !== n.value) row.classList.add('chg');
  }
  if (n.table) { const b = el('button', 'mini', 'view'); b.onclick = e => { e.stopPropagation(); openTable(n); }; row.appendChild(b); }
  wrap.appendChild(row);
  const kids = el('div'); wrap.appendChild(kids);
  if (n.ref) {
    let open = false;
    const toggle = () => { open = !open; tg.textContent = open ? '▾' : '▸'; kids.textContent = '';
      if (open) { S.expanded.add(path); requestExpand(n.ref, 0, kids, path, depth + 1); } else S.expanded.delete(path); };
    row.onclick = toggle;
    if (S.expanded.has(path)) { open = true; tg.textContent = '▾'; requestExpand(n.ref, 0, kids, path, depth + 1); }
  }
  return wrap;
}
function requestExpand(ref, offset, host, path, depth, moreRow) {
  const id = S.rid++; S.pending.set(id, {type: 'expand', host, path, depth, moreRow});
  post('expand', {id, ref, offset});
}
function section(host, title, nodes, empty) {
  host.appendChild(el('div', 'sub', title));
  if (!nodes.length) { const e = el('div', 'msg', empty); e.style.padding = '2px 8px'; host.appendChild(e); }
  nodes.forEach(n => host.appendChild(nodeRow(n, title, 0, host)));
}
function renderVars(v) {
  S.lastVars = v;
  S.curVals = new Map();
  const host = $('#vars'), top = host.scrollTop; host.textContent = '';
  if (!v) return;
  if (v.scope === 'function') section(host, 'Locals', v.locals, '(none)');
  section(host, 'Globals', v.globals, '(none)');
  host.scrollTop = top;
  const w = $('#watch'); w.textContent = '';
  v.watch.forEach((n, i) => {
    const r = nodeRow(n, 'watch', 0, w); w.appendChild(r);
    const x = el('span', 'wx', '×'); x.onclick = () => { S.watches.splice(i, 1); post('watches', {list: S.watches}); if (!S.stop) renderWatchOnly(); };
    r.firstChild.appendChild(x);
  });
}
function renderWatchOnly() {
  const w = $('#watch'); w.textContent = '';
  S.watches.forEach((e, i) => { const r = el('div', 'vrow', e); const x = el('span', 'wx', '×'); x.onclick = () => { S.watches.splice(i, 1); post('watches', {list: S.watches}); renderWatchOnly(); }; r.appendChild(x); w.appendChild(r); });
}
$('#winp').addEventListener('keydown', e => {
  if (e.key !== 'Enter' || !e.target.value.trim()) return;
  S.watches.push(e.target.value.trim()); e.target.value = ''; post('watches', {list: S.watches}); if (S.state !== 'paused') renderWatchOnly();
});

/* ---------------- table viewer (DataFrame / Series / ndarray) ---------------- */
function openTable(n) {
  S.tbl = {ref: n.ref, name: n.name, r0: 0, c0: 0};
  showModal(n.name + ' — ' + n.type + ' ' + n.value); $('#mbody').textContent = 'loading…'; reqTable();
}
function reqTable() { const id = S.rid++; S.pending.set(id, {type: 'table'}); post('table', {id, ref: S.tbl.ref, r0: S.tbl.r0, c0: S.tbl.c0}); }
function renderTable(d) {
  const body = $('#mbody'), ctl = $('#mctl'); body.textContent = ''; ctl.textContent = '';
  if (!d) { body.appendChild(el('div', 'msg', 'Value is no longer available (the program has moved on).')); return; }
  const [R, C] = d.shape;
  const mk = (txt, fn, dis) => { const b = el('button', 'mini', txt); b.disabled = dis; b.onclick = fn; ctl.appendChild(b); };
  const info = el('span', null, 'rows ' + d.r0 + '–' + (d.r0 + d.rows.length) + ' of ' + R + (C > 1 ? ', cols ' + d.c0 + '–' + (d.c0 + d.cols.length) + ' of ' + C : '') + ' ');
  ctl.appendChild(info);
  mk('◀ rows', () => { S.tbl.r0 = Math.max(0, S.tbl.r0 - 50); reqTable(); }, d.r0 === 0);
  mk('rows ▶', () => { S.tbl.r0 += 50; reqTable(); }, d.r0 + 50 >= R);
  if (C > d.cols.length || d.c0 > 0) {
    mk('◀ cols', () => { S.tbl.c0 = Math.max(0, S.tbl.c0 - 20); reqTable(); }, d.c0 === 0);
    mk('cols ▶', () => { S.tbl.c0 += 20; reqTable(); }, d.c0 + 20 >= C);
  }
  const t = el('table', 't'), thead = el('thead'), hr = el('tr');
  hr.appendChild(el('th', 'i', ''));
  d.cols.forEach((c, j) => { const th = el('th', null, c); th.appendChild(el('span', 'dt', d.dtypes[j] || '')); hr.appendChild(th); });
  thead.appendChild(hr); t.appendChild(thead);
  const tb = el('tbody');
  d.rows.forEach((row, i) => { const tr = el('tr'); tr.appendChild(el('th', 'i', d.idx[i])); row.forEach(v => tr.appendChild(el('td', null, v))); tb.appendChild(tr); });
  t.appendChild(tb); body.appendChild(t);
}

/* ---------------- events from server ---------------- */
async function onStopped(m) {
  S.stop = {reason: m.reason, idx: m.idx, exc: m.exc, stack: m.stack};
  S.trail = m.reason === 'step' ? S.lastPos : null;
  S.sel = m.idx;
  S.prevVals = S.curVals;
  renderStack(); renderVars(m.vars);
  setState('paused', m.reason);
  const fr = m.stack[m.idx];
  if (m.reason === 'exception') out('bad', '[uncaught exception] ' + m.exc + '\n');
  if (fr.exists !== false) await openFile(fr.file, fr.line); else out('sys', '[source not available: ' + fr.file + ']\n');
  marks(true); scrollTo(fr.line); setState('paused', m.reason);
}
function onEvent(m) {
  switch (m.t) {
    case 'snapshot':
      S.cfg = m.cfg; writeCfg(); S.watches = m.watches || []; S.settingsPath = m.settings_path; S.settingsError = m.settings_error;
      if (m.prefs) { S.prefs = m.prefs; applyPrefs(S.prefs); }
      S.breaks = new Map(Object.entries(m.breaks).map(([p, l]) => [p, new Set(l)]));
      OUT.textContent = ''; m.output.forEach(([k, t]) => out(k, t));
      if (!$('#tree').firstChild) loadTree();
      if (m.stop) { S.stop = m.stop; onStopped(Object.assign({vars: m.vars}, m.stop)); } else { S.stop = null; renderStack(); renderVars(null); renderWatchOnly(); marks(); }
      setState(m.state, m.status); break;
    case 'state':
      if (S.stop && m.state === 'running') { const t = S.stop.stack[S.stop.idx]; S.lastPos = {file: t.file, line: t.line}; }
      if (m.state === 'idle') S.lastPos = S.trail = null;
      if (m.state !== 'paused') { hideTip(); S.stop = null; renderStack(); marks(); if (m.state === 'idle') { renderVars(null); renderWatchOnly(); } }
      setState(m.state, m.status); break;
    case 'output': out(m.stream, m.text); break;
    case 'stopped': onStopped(m); break;
    case 'vars': renderVars(m); break;
    case 'evalres': S.pending.delete(m.id); out(m.err ? 'bad' : 'sys', m.out ? m.out + '\n' : ''); break;
    case 'expanded': {
      const p = S.pending.get(m.id); S.pending.delete(m.id); if (!p) break;
      if (p.moreRow) p.moreRow.remove();
      if (m.error) { p.host.appendChild(el('div', 'msg', '(value no longer available)')); break; }
      m.children.forEach(c => p.host.appendChild(nodeRow(c, p.path, p.depth, p.host)));
      break;
    }
    case 'tabled': S.pending.delete(m.id); if (S.tbl) renderTable(m.data); break;
    case 'hovered': {
      const p = S.pending.get(m.id); S.pending.delete(m.id); if (!p || !m.info) break;
      if (p.goto) { const l = m.info.loc; if (l && l.exists) jumpTo(l); else toast('No source to jump to'); break; }
      if (p.key === hoverKey && S.state === 'paused') showTip(m.info, p.px, p.py);
      break;
    }
  }
}
new EventSource('/events?t=' + encodeURIComponent(TOKEN)).onmessage = e => onEvent(JSON.parse(e.data));
setState('idle', '');

/* ---------------- hover info (paused only): signature, file, MRO ---------------- */
const tip = el('div'); tip.id = 'tip'; document.body.appendChild(tip);
let hoverTimer = 0, hideTimer = 0, hoverKey = '';
function hideTip() { clearTimeout(hoverTimer); clearTimeout(hideTimer); tip.style.display = 'none'; hoverKey = ''; }   // full reset
const fadeTip = () => { clearTimeout(hideTimer); hideTimer = setTimeout(() => { tip.style.display = 'none'; }, 160); };   // only hides what is shown, keeps a pending request alive
const cancelHover = () => { clearTimeout(hoverTimer); hoverKey = ''; };
tip.addEventListener('mouseenter', () => clearTimeout(hideTimer));
tip.addEventListener('mouseleave', hideTip);
function frameForActive() {
  if (!S.stop) return -1;
  const st = S.stop.stack;
  if (st[S.sel] && st[S.sel].file === S.active) return S.sel;
  for (let i = st.length - 1; i >= 0; i--) if (st[i].file === S.active) return i;
  return -1;
}
function charIndexAt(src, x) {
  const w = document.createTreeWalker(src, NodeFilter.SHOW_TEXT); let base = 0, n;
  const r = document.createRange();
  while ((n = w.nextNode())) {
    for (let i = 0; i < n.length; i++) {
      r.setStart(n, i); r.setEnd(n, i + 1);
      const b = r.getBoundingClientRect();
      if (b.width && x >= b.left && x < b.right) return base + i;
    }
    base += n.length;
  }
  return -1;
}
function exprAt(line, idx) {
  if (!/[A-Za-z0-9_]/.test(line[idx] || '')) return null;
  RX.lastIndex = 0; let m;
  while ((m = RX.exec(line))) { if ((m[1] || m[2]) && idx >= m.index && idx < m.index + m[0].length) return null; }   // inside a comment or string
  let s = idx, e = idx + 1;
  while (s > 0 && /[A-Za-z0-9_]/.test(line[s - 1])) s--;
  while (e < line.length && /[A-Za-z0-9_]/.test(line[e])) e++;
  const word = line.slice(s, e);
  if (/^\d/.test(word) || (KW.has(word) && word !== 'self')) return null;
  let cs = s;
  while (cs > 1 && line[cs - 1] === '.' && /[A-Za-z0-9_]/.test(line[cs - 2])) { cs--; while (cs > 0 && /[A-Za-z0-9_]/.test(line[cs - 1])) cs--; }
  if (cs > 0 && line[cs - 1] === '.') return null;      // base is a call/subscript result, not a plain name
  const chain = line.slice(cs, e);
  if (!/^[A-Za-z_]\w*(\.[A-Za-z_]\w*)*$/.test(chain)) return null;
  return {expr: chain, hs: s};
}
function tokenUnder(ev) {
  const row = document.elementsFromPoint(ev.clientX, ev.clientY).find(n => n.classList && n.classList.contains('line'));
  if (!row) return null;
  const src = row.lastChild, idx = charIndexAt(src, ev.clientX);
  if (idx < 0) return null;
  const x = exprAt(src.textContent, idx);
  return x && Object.assign(x, {line: +row.dataset.n});
}
function requestHover(x, fi, key, px, py, goto) {
  const id = S.rid++; S.pending.set(id, {type: 'hover', key, px, py, goto});
  post('hover', {id, expr: x.expr, frame: fi});
}
$('#code').addEventListener('mousemove', e => {
  if (S.state !== 'paused') { if (tip.style.display === 'block') hideTip(); return; }
  const fi = frameForActive();
  if (fi < 0 || e.target.closest('.gut')) { cancelHover(); fadeTip(); return; }
  const x = tokenUnder(e);
  if (!x) { cancelHover(); fadeTip(); return; }
  const key = S.active + ':' + x.line + ':' + x.hs + ':' + x.expr + ':' + fi;
  if (key === hoverKey) { clearTimeout(hideTimer); return; }       // still on the same token
  clearTimeout(hoverTimer); hoverKey = key;
  if (tip.style.display === 'block') fadeTip();                     // moving to another token: old tip goes away shortly
  hoverTimer = setTimeout(() => requestHover(x, fi, key, e.clientX, e.clientY, false), 280);
});
$('#code').addEventListener('mouseleave', e => { if (!tip.contains(e.relatedTarget)) { cancelHover(); fadeTip(); } });
$('#code').addEventListener('scroll', hideTip);
$('#code').addEventListener('mousedown', e => {       // Ctrl/Cmd+click = go to definition
  if (!(e.ctrlKey || e.metaKey) || S.state !== 'paused' || e.target.closest('.gut')) return;
  const fi = frameForActive(), x = fi < 0 ? null : tokenUnder(e);
  if (!x) return;
  e.preventDefault(); requestHover(x, fi, '', e.clientX, e.clientY, true);
}, true);
function jumpTo(loc) { if (loc && loc.exists) { hideTip(); openFile(loc.file, loc.line); } }
function locLink(loc, label) {
  if (!loc) return el('span', 'lbl', 'no source (built-in)');
  const a = el('a', null, (label || base(loc.file)) + ':' + loc.line); a.title = loc.file; if (loc.exists) a.onclick = () => jumpTo(loc); else a.style.textDecoration = 'none';
  return a;
}
function showTip(i, px, py) {
  clearTimeout(hideTimer); tip.textContent = '';
  const h = el('div', 'h', i.name); h.appendChild(el('span', 'kind', i.kind + (i.owner ? ' of ' + i.owner : ''))); tip.appendChild(h);
  if (i.sig != null) tip.appendChild(el('div', 'sig', (i.kind === 'class' ? 'class ' : 'def ') + i.name + i.sig));
  if (i.kind === 'variable') tip.appendChild(el('div', 'sig', i.type + ' = ' + i.value));
  if (i.kind === 'class' && i.bases) tip.appendChild(el('div', null, 'bases: ' + (i.bases.join(', ') || '—')));
  if (i.definer && i.kind !== 'class') tip.appendChild(el('div', null, 'defined in ' + i.definer));
  else if (i.owner && i.kind === 'variable') tip.appendChild(el('div', null, 'instance attribute of ' + i.owner));
  if (i.loc) { const d = el('div'); d.appendChild(el('span', 'lbl', (i.kind === 'variable' ? 'type defined at ' : 'defined at '))); d.appendChild(locLink(i.loc)); tip.appendChild(d); }
  if (i.doc) tip.appendChild(el('div', 'doc', i.doc));
  if (i.mro && i.mro.length) {
    const m = el('div', 'mro'); m.appendChild(el('div', 'lbl', 'MRO (method resolution order)'));
    i.mro.forEach((c, k) => { const d = el('div', c.mark ? 'def' : ''); d.appendChild(document.createTextNode((k ? '↳ ' : '') + c.name + '  ')); d.appendChild(locLink(c.loc)); m.appendChild(d); });
    tip.appendChild(m);
  }
  tip.style.display = 'block';
  const w = tip.offsetWidth, hgt = tip.offsetHeight;
  tip.style.left = Math.max(4, Math.min(px + 8, innerWidth - w - 8)) + 'px';
  tip.style.top = (py + 18 + hgt > innerHeight ? Math.max(4, py - hgt - 10) : py + 18) + 'px';
}

/* ---------------- splitters (sizes are remembered) ---------------- */
document.querySelectorAll('.split').forEach(s => s.addEventListener('mousedown', e => {
  e.preventDefault();
  const v = s.dataset.v, d = +s.dataset.d, horiz = s.classList.contains('h'), st = horiz ? e.clientY : e.clientX;
  const root = document.documentElement;
  const start = v === '--left' ? $('#files').offsetWidth : v === '--right' ? $('#rt').offsetWidth : $('#cons').offsetHeight;
  const mv = ev => { const cur = horiz ? ev.clientY : ev.clientX; root.style.setProperty(v, Math.max(80, Math.round(start + d * (cur - st))) + 'px'); };
  const up = () => {
    document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up);
    S.prefs.layout = Object.assign({}, S.prefs.layout, {[v.slice(2)]: parseInt(root.style.getPropertyValue(v))}); savePrefsSoon();
  };
  document.addEventListener('mousemove', mv); document.addEventListener('mouseup', up);
}));
window.addEventListener('beforeunload', e => { if ([...S.files.values()].some(f => f.dirty)) { e.preventDefault(); e.returnValue = ''; } });
</script></body></html>
"""
