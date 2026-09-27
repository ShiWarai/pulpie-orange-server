// Tab switching (paste / url / file)
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    document.querySelectorAll('.tab-body').forEach(b => b.classList.remove('active'));
    document.getElementById('body-' + tab.dataset.mode).classList.add('active');
  });
});

// View toggle (rendered / source)
function switchView(view) {
  document.querySelectorAll('.vtab').forEach(t => t.classList.remove('active'));
  const target = document.querySelector('.vtab[data-view="' + view + '"]');
  if (target) target.classList.add('active');
  if (view === 'preview') {
    document.getElementById('output').style.display = '';
    document.getElementById('output-source').style.display = 'none';
  } else {
    document.getElementById('output').style.display = 'none';
    document.getElementById('output-source').style.display = '';
  }
}
document.querySelectorAll('.vtab').forEach(tab => {
  tab.addEventListener('click', () => switchView(tab.dataset.view));
});

// Simple markdown -> HTML renderer
function mdToHtml(md) {
  if (!md) return '<p style="color:#8b92a1">Результат появится здесь</p>';
  const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  return esc(md)
    .replace(/\`\`\`([\s\S]*?)\`\`\`/g, '<pre><code>$1</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%;height:auto">')
    .replace(/^#{1} (.+)$/gm, '<h1>$1</h1>')
    .replace(/^#{2} (.+)$/gm, '<h2>$1</h2>')
    .replace(/^#{3} (.+)$/gm, '<h3>$1</h3>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
}

function setStatus(el, msg, ok) {
  el.innerHTML = ok
    ? '<span class="ok">' + msg + '</span>'
    : '<span class="err">' + msg + '</span>';
}

function setProgress(show, frac, text) {
  const wrap = document.getElementById('progress-wrap');
  const fill = document.getElementById('progress-fill');
  const label = document.getElementById('progress-text');
  if (!show) {
    wrap.style.display = 'none';
    return;
  }
  wrap.style.display = '';
  const processed = Math.max(0, frac[0] || 0);
  const total = Math.max(0, frac[1] || 0);
  const pct = total > 0 ? Math.max(0, Math.min(100, Math.round((processed / total) * 100))) : 0;
  fill.style.width = pct + '%';
  label.textContent = text || (total > 0 ? `Обработка… ${processed}/${total} чанков` : 'Обработка…');
}

function processingState(on) {
  const btn = document.getElementById('process-btn');
  const cancel = document.getElementById('cancel-btn');
  btn.disabled = on;
  cancel.style.display = on ? '' : 'none';
  if (on) {
    btn.textContent = '⏳ Обработка...';
    cancel.disabled = false;
  } else {
    btn.textContent = '▶ Обработать';
    cancel.textContent = '■ Отменить';
  }
}

let pollTimer = null;
let currentJobId = null;

async function process() {
  const stats = document.getElementById('stats');
  const out = document.getElementById('output');
  const outSrc = document.getElementById('output-source');

  const active = document.querySelector('.tab.active');
  const data = {
    device: document.getElementById('device-select').value,
    max_tokens: parseInt(document.getElementById('chunk-select').value, 10),
    as_html: document.getElementById('as-html').checked,
  };

  let source;
  if (active.dataset.mode === 'url') {
    source = document.getElementById('url-input').value.trim();
    if (!source) { setStatus(stats, 'Введите URL', false); return; }
    data.url = source;
  } else if (active.dataset.mode === 'file') {
    const f = document.getElementById('file-input').files[0];
    if (!f) { setStatus(stats, 'Выберите файл', false); return; }
    data.html = await f.text();
  } else {
    source = document.getElementById('html-input').value;
    if (!source.trim()) { setStatus(stats, 'Вставьте HTML', false); return; }
    data.html = source;
  }

  processingState(true);
  setProgress(true, [0, 0], 'Задача запущена...');
  clearTimeout(pollTimer);
  out.innerHTML = '';
  outSrc.value = '';

  try {
    const res = await fetch('/api/extract', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    const json = await res.json();
    if (!json.job_id) {
      setStatus(stats, json.error || 'Ошибка запуска задачи', false);
      processingState(false);
      setProgress(false);
      return;
    }
    currentJobId = json.job_id;
    pollStatus(json.job_id);
  } catch (e) {
    setStatus(stats, 'Ошибка сети: ' + e, false);
    processingState(false);
    setProgress(false);
    clearTimeout(pollTimer);
  }
}

async function pollStatus(jobId) {
  const stats = document.getElementById('stats');
  const out = document.getElementById('output');
  const outSrc = document.getElementById('output-source');

  const tick = async () => {
    try {
      const res = await fetch('/api/status/' + jobId);
      const job = await res.json();

      if (currentJobId && currentJobId !== jobId) return;

      if (job.status === 'running') {
        const prog = job.progress || [0, 0];
        setProgress(true, prog);
        pollTimer = setTimeout(tick, 400);
        return;
      }

      if (job.status === 'done') {
        clearTimeout(pollTimer);
        currentJobId = null;
        processingState(false);
        setProgress(false);
        if (job.aborted) {
          out.innerHTML = '';
          outSrc.value = '';
          setStatus(stats, '⚠ Обработано частично (отменено). kept=' + job.kept + ' | dropped=' + job.dropped, false);
        } else {
          outSrc.value = job.output;
          if ((job.format || 'markdown') === 'html') {
            out.innerHTML = job.output;
          } else {
            out.innerHTML = mdToHtml(job.output);
          }
          const fmt = (job.format || 'markdown') === 'html' ? 'HTML' : 'Markdown';
          document.getElementById('result-label').textContent = 'Результат (' + fmt + ')';
          setStatus(stats, 'kept=' + job.kept + ' | dropped=' + job.dropped + ' | proc=' + job.proc_ms + 'ms | ' + job.device, true);
        }
        switchView('preview');
        return;
      }

      if (job.status === 'error') {
        clearTimeout(pollTimer);
        processingState(false);
        setProgress(false);
        out.innerHTML = '';
        outSrc.value = '';
        setStatus(stats, 'Ошибка: ' + (job.error || 'unknown'), false);
        return;
      }

      pollTimer = setTimeout(tick, 400);
    } catch (e) {
      pollTimer = setTimeout(tick, 600);
    }
  };

  tick();
}

async function cancelJob() {
  if (!currentJobId) return;
  clearTimeout(pollTimer);
  setProgress(true, [1, 0], 'Отмена...');
  try {
    await fetch('/api/abort/' + currentJobId, { method: 'POST' });
  } catch (e) {}
  pollStatus(currentJobId);
}

document.getElementById('process-btn').addEventListener('click', process);
document.getElementById('cancel-btn').addEventListener('click', cancelJob);
document.getElementById('html-input').addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') process();
});
