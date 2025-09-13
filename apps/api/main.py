from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from alfred_app.api.v1.health import router as health_router
from alfred_app.api.v1.stream import router as stream_router
from alfred_app.api.v1.crewai import router as crewai_router
from alfred_app.api.v1.gmail_status import router as gmail_status_router
from alfred_app.api.v1.notion import router as notion_router
from alfred_app.core.config import settings

app = FastAPI(title="Alfred API")

# CORS (dev-friendly defaults; configure via CORS_ALLOW_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# v1 routes
app.include_router(health_router)
app.include_router(stream_router)
app.include_router(crewai_router)
app.include_router(gmail_status_router)
app.include_router(notion_router)
if settings.enable_gmail:
    from alfred_app.api.v1.gmail import router as gmail_router
    app.include_router(gmail_router)


@app.get("/connect/gmail", response_class=HTMLResponse, tags=["ui"])
def connect_gmail_ui():
    # Simple HTML helper to kick off OAuth from a browser
    return """
    <!doctype html>
    <html>
      <head>
        <meta charset='utf-8'>
        <title>Connect Gmail · Alfred</title>
        <style>
          body{font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem;}
          label,input,button{font-size: 1rem}
          input{padding: .4rem .6rem;}
          button{padding: .5rem .8rem;}
          .row{margin: .5rem 0}
          code{background: #f5f5f5; padding: 2px 4px; border-radius: 3px}
        </style>
      </head>
      <body>
        <h1>Connect Gmail</h1>
        <p>Set a profile label (e.g., <code>personal</code> or <code>work</code>) then click Connect.</p>
        <div class="row">
          <label for="profile">Profile ID:</label>
          <input id="profile" value="personal" />
          <button onclick="connect()">Connect</button>
        </div>
        <p id="status"></p>
        <script>
          async function connect(){
            const pid = document.getElementById('profile').value || 'personal';
            const r = await fetch(`/api/v1/gmail/login_url?profile_id=${encodeURIComponent(pid)}`);
            if(!r.ok){
              const e = await r.json().catch(()=>({detail:r.statusText}))
              document.getElementById('status').textContent = 'Error: ' + (e.detail || r.statusText);
              return;
            }
            const data = await r.json();
            window.location.href = data.auth_url;
          }
        </script>
      </body>
    </html>
    """


@app.get("/admin/gmail", response_class=HTMLResponse, tags=["ui"])
def admin_gmail_ui():
    return """
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>Alfred · Gmail Admin</title>
      <script src="https://cdn.tailwindcss.com"></script>
      <style>
        .badge{display:inline-flex;align-items:center;gap:.35rem;border-radius:9999px;padding:.15rem .55rem;font-size:.75rem}
      </style>
    </head>
    <body class="bg-slate-50 text-slate-900">
      <header class="border-b bg-white/80 backdrop-blur sticky top-0 z-10">
        <div class="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <h1 class="text-xl font-semibold">Alfred Admin</h1>
          <nav class="text-sm text-slate-600">Gmail</nav>
        </div>
      </header>

      <main class="max-w-6xl mx-auto px-4 py-6 space-y-6">
        <section class="bg-white shadow rounded-xl p-5">
          <div class="flex flex-wrap items-end gap-3">
            <div>
              <label class="block text-sm text-slate-600 mb-1">Profile ID</label>
              <input id="profile" class="border rounded-lg px-3 py-2 w-48" value="personal"/>
            </div>
            <div>
              <label class="block text-sm text-slate-600 mb-1">Email</label>
              <input id="email" class="border rounded-lg px-3 py-2 w-72" placeholder="you@gmail.com"/>
            </div>
            <div>
              <label class="block text-sm text-slate-600 mb-1">Max Results</label>
              <select id="max" class="border rounded-lg px-3 py-2 w-28">
                <option>10</option><option>25</option><option>50</option>
              </select>
            </div>
            <div class="ml-auto flex items-center gap-2">
              <a href="/connect/gmail" target="_blank" class="px-3 py-2 rounded-lg bg-sky-600 text-white hover:bg-sky-700">Connect Gmail</a>
              <button onclick="loadAccounts()" class="px-3 py-2 rounded-lg bg-slate-100 hover:bg-slate-200">Load Accounts</button>
            </div>
          </div>
          <div class="mt-4 flex items-center gap-2">
            <input id="q" class="border rounded-lg px-3 py-3 w-full" placeholder="Search (e.g., subject:invoice newer_than:30d from:alice@acme.com)"/>
            <button onclick="doSearch()" class="px-4 py-3 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700">Search</button>
          </div>
          <div id="status" class="mt-3 text-sm text-slate-600"></div>
        </section>

        <section id="results" class="grid gap-3"></section>
      </main>

      <div id="modal" class="hidden fixed inset-0 bg-black/50 z-20">
        <div class="absolute inset-0 flex items-start md:items-center justify-center p-4">
          <div class="bg-white rounded-xl shadow-xl w-full max-w-3xl overflow-hidden">
            <div class="flex items-center justify-between px-4 py-3 border-b">
              <div class="font-semibold" id="modalTitle">Message</div>
              <button onclick="closeModal()" class="text-slate-500 hover:text-slate-700">✕</button>
            </div>
            <div id="modalBody" class="p-4 prose max-w-none"></div>
          </div>
        </div>
      </div>

      <script>
        async function fetchJSON(url){
          const r = await fetch(url);
          if(!r.ok){
            const t = await r.text();
            throw new Error(t || r.statusText);
          }
          return r.json();
        }

        function badge(text, kind){
          const colors = {
            ok: 'bg-emerald-100 text-emerald-700',
            warn: 'bg-amber-100 text-amber-800',
            err: 'bg-rose-100 text-rose-700'
          };
          return `<span class="badge ${colors[kind]||colors.ok}">${text}</span>`;
        }

        async function updateStatus(){
          try{
            const s = await fetchJSON('/api/v1/gmail/status');
            const el = document.getElementById('status');
            el.innerHTML = `Status: ${badge(s.enabled?'enabled':'disabled', s.enabled?'ok':'warn')} ${badge(s.ready?'ready':'not ready', s.ready?'ok':'warn')}` +
              (s.missing && s.missing.length ? ` · Missing: <code>${s.missing.join(', ')}</code>` : '');
          }catch(e){
            document.getElementById('status').textContent = 'Status error: ' + e.message;
          }
        }

        async function loadAccounts(){
          const pid = document.getElementById('profile').value.trim();
          try{
            const data = await fetchJSON(`/api/v1/gmail/accounts?profile_id=${encodeURIComponent(pid)}`);
            const list = data.emails || [];
            if(list.length){
              document.getElementById('email').value = list[0];
            }
            document.getElementById('status').innerHTML += ' · ' + badge(`${list.length} account(s)`, 'ok');
          }catch(e){
            document.getElementById('status').innerHTML += ' · ' + badge('accounts error', 'err');
          }
        }

        function resultCard(item){
          const date = item.date || '';
          const from = item.from || '';
          const subject = item.subject || '(no subject)';
          const snippet = item.snippet || '';
          const id = item.id;
          return `
            <article class="bg-white shadow-sm hover:shadow rounded-xl p-4 border transition">
              <div class="flex items-center justify-between gap-3">
                <div class="min-w-0">
                  <div class="text-sm text-slate-500 truncate">${from}</div>
                  <h3 class="font-medium truncate">${subject}</h3>
                </div>
                <div class="text-xs text-slate-500">${date}</div>
              </div>
              <p class="mt-2 text-slate-600 line-clamp-2">${snippet}</p>
              <div class="mt-3 flex items-center gap-2">
                <button class="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200" onclick="openMessage('${id}')">Open</button>
                <a class="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200" href="#" onclick="copyId('${id}');return false;">Copy ID</a>
              </div>
            </article>`;
        }

        async function doSearch(){
          const pid = document.getElementById('profile').value.trim();
          const email = document.getElementById('email').value.trim();
          const q = document.getElementById('q').value.trim();
          const max = document.getElementById('max').value;
          const container = document.getElementById('results');
          container.innerHTML = '<div class="text-sm text-slate-500">Searching…</div>';
          try{
            const data = await fetchJSON(`/api/v1/gmail/search?profile_id=${encodeURIComponent(pid)}&email=${encodeURIComponent(email)}&q=${encodeURIComponent(q)}&max_results=${max}`);
            const items = data.results || [];
            container.innerHTML = items.length ? items.map(resultCard).join('') : '<div class="text-sm text-slate-500">No results</div>';
          }catch(e){
            container.innerHTML = '<div class="text-sm text-rose-600">' + e.message + '</div>';
          }
        }

        async function openMessage(id){
          const pid = document.getElementById('profile').value.trim();
          const email = document.getElementById('email').value.trim();
          document.getElementById('modal').classList.remove('hidden');
          document.getElementById('modalTitle').textContent = 'Message ' + id;
          document.getElementById('modalBody').innerHTML = '<div class="text-slate-500">Loading…</div>';
          try{
            let data = await fetchJSON(`/api/v1/gmail/message/html?profile_id=${encodeURIComponent(pid)}&email=${encodeURIComponent(email)}&id=${encodeURIComponent(id)}`);
            let html = (data && data.html) || '';
            if(!html){
              const t = await fetchJSON(`/api/v1/gmail/message/text?profile_id=${encodeURIComponent(pid)}&email=${encodeURIComponent(email)}&id=${encodeURIComponent(id)}`);
              html = '<pre class="whitespace-pre-wrap">' + (t.text||'') + '</pre>';
            }
            document.getElementById('modalBody').innerHTML = html || '<div class="text-slate-500">(no content)</div>';
          }catch(e){
            document.getElementById('modalBody').innerHTML = '<div class="text-rose-600">' + e.message + '</div>';
          }
        }

        function closeModal(){ document.getElementById('modal').classList.add('hidden'); }
        function copyId(id){ navigator.clipboard.writeText(id); }

        updateStatus();
      </script>
    </body>
    </html>
    """
