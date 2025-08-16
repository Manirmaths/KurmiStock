// --- Toast helpers ---
function showToast(title, msg='', type='ok'){
  const wrap = document.getElementById('toasts');
  if(!wrap) return;
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<h5>${title}</h5>${msg?`<p>${msg}</p>`:''}`;
  wrap.appendChild(el);
  setTimeout(()=>{ el.style.opacity='0'; el.style.transform='translateY(10px)'; }, 2800);
  setTimeout(()=>wrap.removeChild(el), 3400);
}

const offlineBadge = document.getElementById('offlineBadge');
function updateOnlineStatus(){
  const o = navigator.onLine;
  offlineBadge.hidden = o;
}
window.addEventListener('online', updateOnlineStatus);
window.addEventListener('offline', updateOnlineStatus);
updateOnlineStatus();

// Simple IndexedDB wrapper for queued ops
const DB_NAME = 'stockwise';
const STORE = 'queue';
let dbPromise = new Promise((resolve, reject)=>{
  const req = indexedDB.open(DB_NAME, 1);
  req.onupgradeneeded = (e)=>{
    const db = e.target.result;
    if(!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, {keyPath:'id', autoIncrement:true});
  };
  req.onsuccess = ()=>resolve(req.result);
  req.onerror = ()=>reject(req.error);
});

async function queueOperation(kind, payload){
  const db = await dbPromise;
  const tx = db.transaction(STORE, 'readwrite');
  tx.objectStore(STORE).add({kind, payload, createdAt: Date.now()});
  return tx.complete;
}

async function readAll(){
  const db = await dbPromise;
  return new Promise((res)=>{
    const tx = db.transaction(STORE, 'readonly');
    const store = tx.objectStore(STORE);
    const items = [];
    store.openCursor().onsuccess = (e)=>{
      const cur = e.target.result;
      if(cur){ items.push({...cur.value, _key:cur.key}); cur.continue(); } else res(items);
    };
  });
}
async function clearAll(){
  const db = await dbPromise;
  const tx = db.transaction(STORE, 'readwrite');
  tx.objectStore(STORE).clear();
  return tx.complete;
}

async function syncNow(){
  const items = await readAll();
  if(!items.length) return;
  // naive grouping: send as-is
  const payload = {products:[], sales:[], purchases:[]};
  for(const it of items){
    payload[it.kind+'s']?.push(it.payload);
  }
  const res = await fetch('/api/sync',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  if(res.ok) await clearAll();
}

document.getElementById('syncBtn')?.addEventListener('click', syncNow);
window.addEventListener('online', syncNow);
