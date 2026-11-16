"""Fixed in-container terminal programs. No browser-supplied command strings."""
START = r'''
const fs = require('fs');
const {spawn} = require('child_process');
const [id, mode] = process.argv.slice(1);
if (!/^[a-f0-9]{32}$/.test(id) || !['login','attach'].includes(mode)) process.exit(64);
const file = '/tmp/.poc-terminal-' + id + '.json';
const cancel = '/tmp/.poc-terminal-' + id + '.closed';
if (fs.existsSync(cancel)) process.exit(0);
function startTime(pid) {
  const stat = fs.readFileSync('/proc/' + pid + '/stat','utf8');
  return stat.slice(stat.lastIndexOf(')') + 2).split(' ')[19];
}
fs.writeFileSync(file, JSON.stringify({pid:process.pid,start:startTime(process.pid)}), {flag:'wx',mode:0o600});
if (fs.existsSync(cancel)) { try { fs.unlinkSync(file); } catch {} process.exit(0); }
let child, closing=false;
function remove() { try { fs.unlinkSync(file); } catch {} }
function stop() {
  if (closing) return;
  closing=true;
  if (child) { child.kill('SIGCONT'); child.kill('SIGTERM'); }
  setTimeout(() => { if (child) child.kill('SIGKILL'); remove(); process.exit(0); },1000).unref();
}
process.on('SIGTERM',stop); process.on('SIGHUP',stop); process.on('SIGINT',()=>{});
const args = ['--no-daemon', ...(mode==='login' ? ['login','--device-auth'] : ['--sandbox','workspace-write','--ask-for-approval','on-request'])];
child=spawn('codex',args,{stdio:'inherit'});
child.on('error',()=>{remove();process.exit(70);});
child.on('exit',code=>{remove();process.exit(code===null?0:code);});
process.on('exit',remove);
'''
CLOSE = r'''
const fs=require('fs'); const id=process.argv[1];
if (!/^[a-f0-9]{32}$/.test(id)) process.exit(64);
const file='/tmp/.poc-terminal-'+id+'.json';
fs.writeFileSync('/tmp/.poc-terminal-'+id+'.closed','',{mode:0o600});
function done() { process.stdout.write(JSON.stringify({closed:true})); }
if (!fs.existsSync(file)) { done(); process.exit(0); }
try {
  const record=JSON.parse(fs.readFileSync(file,'utf8'));
  if (!Number.isInteger(record.pid) || record.pid<=1 || typeof record.start!=='string') process.exit(65);
  const stat=fs.readFileSync('/proc/'+record.pid+'/stat','utf8');
  const start=stat.slice(stat.lastIndexOf(')')+2).split(' ')[19];
  const args=fs.readFileSync('/proc/'+record.pid+'/cmdline','utf8').split('\0').filter(Boolean);
  if (start!==record.start || args[args.length-2]!==id || !['login','attach'].includes(args[args.length-1])) process.exit(65);
  process.kill(record.pid,'SIGCONT'); process.kill(record.pid,'SIGTERM');
  const until=Date.now()+2500;
  const timer=setInterval(()=>{
    if (!fs.existsSync(file)) {clearInterval(timer);done();}
    else if (Date.now()>until) {clearInterval(timer);process.exit(66);}
  },50);
} catch(e) {
  if (e.code==='ENOENT' || e.code==='ESRCH') {try{fs.unlinkSync(file);}catch{}done();}
  else process.exit(65);
}
'''
