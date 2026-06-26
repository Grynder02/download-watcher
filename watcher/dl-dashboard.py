#!/usr/bin/env python3
"""
Download Watcher Dashboard — serves HTML widget + JSON API on a local port.
Warns via audio + massive browser flash on failure.
Config-driven: reads from ~/.config/download-watcher/config
"""
import json, os, subprocess, sys, time, http.server, urllib.parse, threading, signal, operator

# ─── Load config ───────────────────────────────────────────
CONFIG_FILE = os.path.expanduser("~/.config/download-watcher/config")
_conf = {}
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE) as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, _, v = line.partition('=')
                _conf[k.strip()] = v.strip().strip('"')

DIR = _conf.get('DIR', '/tmp/downloads')
TOTAL_FILES = int(_conf.get('TOTAL_FILES', '0'))
SERVICE = _conf.get('SERVICE', '')
PORT = int(_conf.get('PORT', '18999'))
STALL_SECONDS = int(_conf.get('STALL_SECONDS', '300'))
MONITOR_SCRIPT = os.path.expanduser(_conf.get('MONITOR_SCRIPT', '~/.local/share/download-watcher/watcher/dl-monitor.sh'))
ALARM_WAV = os.path.expanduser(_conf.get('ALARM_WAV', '~/.local/share/download-watcher/watcher/dl-alarm.wav'))
HEARTBEAT_WAV = os.path.expanduser(_conf.get('HEARTBEAT_WAV', '~/.local/share/download-watcher/watcher/dl-heartbeat.wav'))
TITLE = _conf.get('TITLE', os.path.basename(DIR.rstrip('/')))

STATE_FILE = "/dev/shm/dl-watcher-state.json"

# ─── Audio ────────────────────────────────────────────────
def play_sound(wav_path, repeat=1):
    for _ in range(repeat):
        subprocess.Popen(["paplay", wav_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if repeat > 1:
            time.sleep(0.3)

def play_alarm():
    t = threading.Thread(target=lambda: play_sound(ALARM_WAV, repeat=5), daemon=True)
    t.start()

def play_heartbeat():
    global _heartbeat_counter, _muted
    if _muted:
        return
    _heartbeat_counter += 1
    if _heartbeat_counter % 14 == 0:
        t = threading.Thread(target=lambda: play_sound(HEARTBEAT_WAV), daemon=True)
        t.start()

# Track previous state for edge detection
_prev_failed = False
_prev_files = 0
_prev_file_time = time.time()
_heartbeat_counter = 0
_muted = True
AUDIO_ENABLED = _conf.get('AUDIO_ENABLED', '0').lower() in ('1','true','yes','on')

# ─── Translations ──────────────────────────────────────────
TRANSLATIONS = {
    "en": {
        "title": "Download Watcher",
        "connecting": "Connecting...",
        "healthy": "Healthy",
        "running": "Running",
        "failed": "DOWNLOAD FAILED",
        "disconnected": "Disconnected",
        "stalled": "Stalled",
        "downloaded": "Downloaded",
        "speed": "Speed",
        "eta": "ETA",
        "files": "files",
        "updated": "Updated",
        "chirps_on": "Sounds on",
        "chirps_off": "Sounds off",
        "conn_lost": "Connection lost",
        "dl_failed": "Download failed - check the service log",
        "yes": "Yes",
        "no": "No",
    },
    "es": {
        "title": "Monitor de Descarga",
        "connecting": "Conectando...",
        "healthy": "Activo",
        "running": "Descargando",
        "failed": "DESCARGA FALLIDA",
        "disconnected": "Desconectado",
        "stalled": "Detenido",
        "downloaded": "Descargado",
        "speed": "Velocidad",
        "eta": "Tiempo restante",
        "files": "archivos",
        "updated": "Actualizado",
        "chirps_on": "Sonido activo",
        "chirps_off": "Sonido silenciado",
        "conn_lost": "Conexion perdida",
        "dl_failed": "Descarga fallida - revisa el registro",
        "yes": "Si",
        "no": "No",
    },
    "de": {
        "title": "Download-Überwachung",
        "connecting": "Verbinde...",
        "healthy": "Aktiv",
        "running": "Läuft",
        "failed": "DOWNLOAD FEHLGESCHLAGEN",
        "disconnected": "Getrennt",
        "stalled": "Stockt",
        "downloaded": "Heruntergeladen",
        "speed": "Geschwindigkeit",
        "eta": "Verbleibend",
        "files": "Dateien",
        "updated": "Aktualisiert",
        "chirps_on": "Ton an",
        "chirps_off": "Ton aus",
        "conn_lost": "Verbindung getrennt",
        "dl_failed": "Download fehlgeschlagen - Log prüfen",
        "yes": "Ja",
        "no": "Nein",
    },
    "fr": {
        "title": "Surveillance de Téléchargement",
        "connecting": "Connexion...",
        "healthy": "Actif",
        "running": "En cours",
        "failed": "ECHEC DU TÉLÉCHARGEMENT",
        "disconnected": "Déconnecté",
        "stalled": "Bloqué",
        "downloaded": "Téléchargé",
        "speed": "Vitesse",
        "eta": "Temps restant",
        "files": "fichiers",
        "updated": "Mis à jour",
        "chirps_on": "Son activé",
        "chirps_off": "Son désactivé",
        "conn_lost": "Connexion perdue",
        "dl_failed": "Échec du téléchargement - vérifier les logs",
        "yes": "Oui",
        "no": "Non",
    },
    "pt-BR": {
        "title": "Monitor de Download",
        "connecting": "Conectando...",
        "healthy": "Ativo",
        "running": "Baixando",
        "failed": "DOWNLOAD FALHOU",
        "disconnected": "Desconectado",
        "stalled": "Parado",
        "downloaded": "Baixado",
        "speed": "Velocidade",
        "eta": "Tempo restante",
        "files": "arquivos",
        "updated": "Atualizado",
        "chirps_on": "Som ligado",
        "chirps_off": "Som desligado",
        "conn_lost": "Conexão perdida",
        "dl_failed": "Download falhou - verifique o log",
        "yes": "Sim",
        "no": "Não",
    },
    "ja": {
        "title": "ダウンロード監視",
        "connecting": "接続中...",
        "healthy": "正常",
        "running": "ダウンロード中",
        "failed": "ダウンロード失敗",
        "disconnected": "切断されました",
        "stalled": "停止中",
        "downloaded": "ダウンロード済",
        "speed": "速度",
        "eta": "残り時間",
        "files": "ファイル",
        "updated": "更新",
        "chirps_on": "音声オン",
        "chirps_off": "音声オフ",
        "conn_lost": "接続が切れました",
        "dl_failed": "ダウンロード失敗 - ログを確認",
        "yes": "はい",
        "no": "いいえ",
    },
    "zh": {
        "title": "下载监视器",
        "connecting": "连接中...",
        "healthy": "正常",
        "running": "下载中",
        "failed": "下载失败",
        "disconnected": "已断开",
        "stalled": "已停止",
        "downloaded": "已下载",
        "speed": "速度",
        "eta": "预计剩余",
        "files": "文件",
        "updated": "更新于",
        "chirps_on": "声音开",
        "chirps_off": "声音关",
        "conn_lost": "连接丢失",
        "dl_failed": "下载失败 - 请检查日志",
        "yes": "是",
        "no": "否",
    },
}

DEFAULT_LANG = "en"
SUPPORTED_LANGS = list(TRANSLATIONS.keys())

def get_lang(accept):
    """Parse Accept-Language header and return best match."""
    if not accept:
        return DEFAULT_LANG
    # Parse quality values
    entries = []
    for part in accept.split(','):
        part = part.strip()
        if ';' in part:
            lang, _, q = part.partition(';')
            q = q.replace('q=', '').strip() if q else '1'
        else:
            lang = part
            q = '1'
        try:
            entries.append((lang.strip(), float(q)))
        except ValueError:
            entries.append((lang.strip(), 1.0))
    entries.sort(key=operator.itemgetter(1), reverse=True)
    for lang, _ in entries:
        lang = lang.split('-')[0]
        # Check exact
        if lang in SUPPORTED_LANGS:
            return lang
        # Check root (e.g., "zh" matches zh)
        for supported in SUPPORTED_LANGS:
            if supported.startswith(lang):
                return supported
    return DEFAULT_LANG

def render_html(lang, title, total_files):
    """Render HTML with localized strings."""
    t = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANG])

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{t['title']}</title>
<style>
  :root {{ --bg: #0d1117; --card: #161b22; --accent: #58a6ff; --green: #3fb950; --red: #f85149; --text: #c9d1d9; --muted: #8b949e; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; }}
  .card {{ background: var(--card); border: 1px solid #30363d; border-radius: 16px; padding: 32px; width: 100%; max-width: 680px; box-shadow: 0 8px 32px rgba(0,0,0,0.4); }}
  h1 {{ font-size: 1.5rem; margin-bottom: 4px; }}
  .subtitle {{ color: var(--muted); font-size: 0.85rem; margin-bottom: 20px; }}
  .status-bar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }}
  .status-indicator {{ display: flex; align-items: center; gap: 8px; font-weight: 600; }}
  .dot {{ width: 12px; height: 12px; border-radius: 50%; display: inline-block; }}
  .dot.ok {{ background: var(--green); box-shadow: 0 0 8px var(--green); animation: pulse-dot 2s infinite; }}
  .dot.fail {{ background: var(--red); box-shadow: 0 0 12px var(--red); animation: flash-dot 0.5s infinite; }}
  @keyframes pulse-dot {{ 0%,100%{{opacity:1}} 50%{{opacity:0.5}} }}
  @keyframes flash-dot {{ 0%,100%{{opacity:1}} 50%{{opacity:0.2}} }}
  .progress-container {{ background: #21262d; border-radius: 10px; height: 24px; overflow: hidden; margin: 16px 0; position: relative; }}
  .progress-fill {{ height: 100%; border-radius: 10px; transition: width 0.5s ease, background 1s; background: linear-gradient(90deg, #58a6ff, #1f6feb); width: 0%; }}
  .progress-fill.stalled {{ background: linear-gradient(90deg, #f85149, #da3633); animation: shake 0.3s infinite; }}
  .progress-text {{ position: absolute; top: 0; left: 0; right: 0; bottom: 0; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 700; color: #fff; text-shadow: 0 1px 2px rgba(0,0,0,0.5); }}
  .stats {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin: 16px 0; }}
  .stat {{ background: #0d1117; border-radius: 10px; padding: 12px; text-align: center; }}
  .stat .label {{ font-size: 0.7rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }}
  .stat .value {{ font-size: 1.3rem; font-weight: 700; margin-top: 4px; }}
  .stat .value.green {{ color: var(--green); }}
  .stat .value.blue {{ color: var(--accent); }}
  .stat .value.orange {{ color: #d29922; }}
  .stat .value.red {{ color: var(--red); }}
  .alert-bar {{ display: none; margin-top: 16px; padding: 12px; border-radius: 10px; font-weight: 600; text-align: center; animation: flash-bg 1s infinite; }}
  .alert-bar.active {{ display: block; }}
  .alert-bar.fail {{ background: var(--red); color: #fff; }}
  .alert-bar.warn {{ background: #d29922; color: #000; }}
  @keyframes flash-bg {{ 0%,100%{{opacity:1}} 50%{{opacity:0.6}} }}
  @keyframes shake {{ 0%,100%{{transform:translateX(0)}} 25%{{transform:translateX(-4px)}} 75%{{transform:translateX(4px)}} }}
  .top-bar {{ display: flex; justify-content: flex-end; gap: 8px; position: fixed; top: 20px; right: 20px; z-index: 100; }}
  .mute-btn, .lang-btn {{ background: var(--card); border: 1px solid #30363d; border-radius: 30px; padding: 8px 16px; cursor: pointer; font-size: 0.8rem; color: var(--text); transition: all 0.3s; }}
  .mute-btn:hover, .lang-btn:hover {{ border-color: var(--accent); }}
  .mute-btn.muted {{ border-color: var(--red); color: var(--red); }}
  .mute-btn.unmuted {{ border-color: var(--green); color: var(--green); }}
  .lang-dropdown {{ display: none; position: fixed; top: 60px; right: 20px; background: var(--card); border: 1px solid #30363d; border-radius: 10px; padding: 4px; z-index: 101; }}
  .lang-dropdown.open {{ display: block; }}
  .lang-dropdown a {{ display: block; padding: 6px 16px; color: var(--text); text-decoration: none; font-size: 0.8rem; border-radius: 6px; cursor: pointer; }}
  .lang-dropdown a:hover {{ background: #21262d; }}
  .lang-dropdown a.active {{ color: var(--accent); font-weight: 600; }}
</style>
</head>
<body>
<div class="top-bar">
  <div class="lang-btn" id="langBtn" onclick="toggleLang()">🌐</div>
  <div class="mute-btn unmuted" id="muteBtn" onclick="toggleMute()">{t['chirps_on']}</div>
</div>
<div class="lang-dropdown" id="langDropdown">
  <a onclick="setLang('en')" data-lang="en">English</a>
  <a onclick="setLang('es')" data-lang="es">Español</a>
  <a onclick="setLang('de')" data-lang="de">Deutsch</a>
  <a onclick="setLang('fr')" data-lang="fr">Français</a>
  <a onclick="setLang('pt-BR')" data-lang="pt-BR">Português (BR)</a>
  <a onclick="setLang('ja')" data-lang="ja">日本語</a>
  <a onclick="setLang('zh')" data-lang="zh">中文</a>
</div>
<div class="card">
  <h1>{t['title']}</h1>
  <div class="subtitle">{title}</div>
  <div class="subtitle" id="lastUpdate">{t['connecting']}</div>
  <div class="status-bar">
    <div class="status-indicator"><span class="dot ok" id="dot"></span><span id="statusText">{t['healthy']}</span></div>
    <span id="pctText" style="font-weight:700;font-size:1.1rem">0%</span>
  </div>
  <div class="progress-container">
    <div class="progress-fill" id="progressFill" style="width:0%"></div>
    <div class="progress-text" id="progressLabel">0 / {total_files} {t['files']}</div>
  </div>
  <div class="stats">
    <div class="stat"><div class="label">{t['downloaded']}</div><div class="value blue" id="totalSize">--</div></div>
    <div class="stat"><div class="label">{t['speed']}</div><div class="value green" id="speed">--</div></div>
    <div class="stat"><div class="label">{t['eta']}</div><div class="value orange" id="eta">--</div></div>
  </div>
  <div class="progress-bar" id="fileStatus" style="margin-top:8px;text-align:center;font-size:0.6rem;letter-spacing:0.1em;color:#58a6ff;"></div>
  <div class="alert-bar" id="alertBar"></div>
</div>

<script>
const LANG_STRINGS = """ + json.dumps(TRANSLATIONS) + r""";
const API = '/api/status';
const POLL_MS = 2000;
const MAX_FILES = """ + str(total_files) + r""";
let currentLang = '""" + lang + r"""';
let lastFiles = 0;
let failCount = 0;
let alarmPlaying = false;
const AUDIO_ENABLED = false;
let audioCtx = null;

function t(key) {
  const lang = currentLang;
  if (LANG_STRINGS[lang] && LANG_STRINGS[lang][key]) return LANG_STRINGS[lang][key];
  if (LANG_STRINGS['en'] && LANG_STRINGS['en'][key]) return LANG_STRINGS['en'][key];
  return key;
}

function initAudio() {
  if (audioCtx) return;
  try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch(e) {}
}

function playBrowserSiren() {
  if (!audioCtx) return;
  const now = audioCtx.currentTime;
  for (let i = 0; i < 20; i++) {
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = 'sawtooth';
    osc.frequency.value = (i % 2 === 0) ? 880 : 440;
    gain.gain.setValueAtTime(0.3, now + i * 0.15);
    gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.15 + 0.12);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start(now + i * 0.15);
    osc.stop(now + i * 0.15 + 0.12);
  }
}

function $(id) { return document.getElementById(id); }

function fetchStatus() {
  fetch(API+'?lang='+currentLang).then(r=>r.json()).then(d=>update(d)).catch(() => {
    failCount++;
    if (failCount > 3) {
      $('dot').className = 'dot fail';
      $('statusText').textContent = t('disconnected');
      showAlert(t('conn_lost'), 'warn');
      initAudio(); playBrowserSiren();
    }
  });
}

function update(d) {
  failCount = 0;
  const files = parseInt(d.files) || 0;
  const maxF = parseInt(d.max_files) || MAX_FILES;
  const pct = parseInt(d.pct) || 0;
  const total = d.total || '--';
  const rate = d.rate ? d.rate + ' MB/s' : '--';
  const remaining = d.remaining || '--';

  $('lastUpdate').textContent = t('updated') + ' ' + new Date().toLocaleTimeString();

  if (d.status === 'failed') {
    $('dot').className = 'dot fail';
    $('statusText').textContent = t('failed');
    $('progressFill').classList.add('stalled');
    showAlert(t('dl_failed'), 'fail');
    if (!alarmPlaying) {
      alarmPlaying = true; if (AUDIO_ENABLED) { initAudio(); playBrowserSiren(); }
      // repeating siren disabled by default; user must opt into audio explicitly
    }
  } else {
    $('dot').className = 'dot ok';
    $('statusText').textContent = t('running');
    $('progressFill').classList.remove('stalled');
    alarmPlaying = false;
    if (window._alarmInterval) { clearInterval(window._alarmInterval); window._alarmInterval = null; }
    if (d.stalled && files > 0 && files < maxF) {
      $('statusText').textContent = t('stalled') + ' ' + (d.stalled_sec || '') + 's';
    }
  }

  lastFiles = files;
  $('pctText').textContent = pct + '%';
  $('progressFill').style.width = pct + '%';
  $('progressLabel').textContent = files + ' / ' + maxF + ' ' + t('files');
  $('totalSize').textContent = total;
  $('speed').textContent = rate;
  $('eta').textContent = remaining;
  renderFiles(files, maxF);

  if (d.report) { showAlert(d.report, 'warn'); setTimeout(hideAlert, 6000); }
}

function toggleMute() {
  fetch('/api/mute').then(r=>r.json()).then(d => {
    const btn = $('muteBtn');
    if (d.muted) { btn.className = 'mute-btn muted'; btn.innerHTML = t('chirps_off'); }
    else { btn.className = 'mute-btn unmuted'; btn.innerHTML = t('chirps_on'); }
  });
}

function toggleLang() {
  $('langDropdown').classList.toggle('open');
}

function setLang(lang) {
  currentLang = lang;
  document.documentElement.lang = lang;
  $('langDropdown').classList.remove('open');
  // Reload status with new lang
  fetchStatus();
  // Update static labels
  $('muteBtn').innerHTML = $('muteBtn').classList.contains('muted') ? t('chirps_off') : t('chirps_on');
  // Update active state in dropdown
  document.querySelectorAll('.lang-dropdown a').forEach(a => {
    a.classList.toggle('active', a.dataset.lang === lang);
  });
}

function renderFiles(done, total) {
  const el = $('fileStatus');
  if (total <= 0) { el.textContent = ''; return; }
  const cols = 47;
  let visual = '';
  const block = Math.max(1, Math.round(cols / total));
  for (let i = 0; i < total; i += block) visual += (i < done) ? '█' : '░';
  el.textContent = visual;
}

function showAlert(msg, t) { const b=$('alertBar'); b.textContent=msg; b.className='alert-bar active '+t; }
function hideAlert() { $('alertBar').className='alert-bar'; }

// Close lang dropdown on outside click
document.addEventListener('click', function(e) {
  if (!$('langDropdown').contains(e.target) && e.target !== $('langBtn')) {
    $('langDropdown').classList.remove('open');
  }
});

initAudio();
fetchStatus();
setInterval(fetchStatus, POLL_MS);
</script>
</body>
</html>"""


# ─── HTTP Handler ────────────────────────────────────────────────
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == '/':
            accept = self.headers.get('Accept-Language', '')
            lang = get_lang(accept)
            # Check if ?lang= override in URL
            qs = urllib.parse.parse_qs(parsed.query)
            if 'lang' in qs and qs['lang'][0] in SUPPORTED_LANGS:
                lang = qs['lang'][0]

            page = render_html(lang, TITLE, TOTAL_FILES)
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.end_headers()
            self.wfile.write(page.encode('utf-8'))
            return

        if parsed.path == '/api/status':
            self.handle_status()
            return

        if parsed.path == '/api/mute':
            global _muted
            qs = urllib.parse.parse_qs(parsed.query)
            _muted = qs.get('state', [''])[0].lower() == 'true' if 'state' in qs else not _muted
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"muted": _muted}).encode())
            return

        if parsed.path == '/api/ping':
            play_alarm()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())
            return

        self.send_response(404)
        self.end_headers()
        self.wfile.write(b'404')

    def handle_status(self):
        global _prev_failed, _prev_files, _prev_file_time
        try:
            result = subprocess.run([MONITOR_SCRIPT], capture_output=True, text=True, timeout=15)
            data = json.loads(result.stdout.strip()) if result.returncode == 0 else {"status":"error","error":result.stderr.strip()}
        except Exception as e:
            data = {"status":"error","error":str(e)}

        data["max_files"] = TOTAL_FILES
        data["muted"] = _muted

        if data.get("status") == "failed" and not _prev_failed:
            _prev_failed = True; play_alarm()
        elif data.get("status") != "failed":
            _prev_failed = False

        files = int(data.get("files", 0))
        if files > _prev_files:
            _prev_file_time = time.time()
        elif files == _prev_files and files > 0 and files < TOTAL_FILES:
            if time.time() - _prev_file_time > STALL_SECONDS:
                data["stalled"] = True
        else:
            _prev_file_time = time.time()
        _prev_files = files
        data["stalled_sec"] = int(time.time() - _prev_file_time) if (files == _prev_files and files > 0 and files < TOTAL_FILES) else 0

        play_heartbeat()

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, fmt, *args):
        pass

# ─── Startup ─────────────────────────────────────────────────────
if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *a: exit(0))
    server = http.server.HTTPServer(('0.0.0.0', PORT), Handler)
    print(f"Download Watcher running at http://localhost:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()