import json
import logging
import os
import re
import signal
import socket
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cctv-dashboard")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CONFIG_FILE = Path(__file__).parent / "cameras.json"
DEFAULT_CAMERA_IDS = [
    "1013", "261", "301", "100", "36", "192", "531", "234", "243",
]
TOPIS_INFO_URL = "https://topis.seoul.go.kr/map/selectCctvInfo.do"
ALLOWED_PROXY_DOMAINS = [
    "topis.seoul.go.kr",
    "cctvsec.seoul.go.kr",
    "210.179.218.",
]

# ---------------------------------------------------------------------------
# Camera list management (thread-safe)
# ---------------------------------------------------------------------------
_camera_lock = threading.Lock()


def _load_camera_ids():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
            ids = data.get("camera_ids", DEFAULT_CAMERA_IDS)
            logger.info("Loaded %d cameras from config", len(ids))
            return list(ids)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load config, using defaults: %s", e)
    return list(DEFAULT_CAMERA_IDS)


def _save_camera_ids(ids):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"camera_ids": ids}, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error("Failed to save config: %s", e)


CURRENT_CAMERA_IDS = _load_camera_ids()

# ---------------------------------------------------------------------------
# HTTP session (thread-local for thread safety)
# ---------------------------------------------------------------------------
_thread_local = threading.local()


def _get_session():
    if not hasattr(_thread_local, "session"):
        s = requests.Session()
        s.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Referer": "https://topis.seoul.go.kr/map/openCctv.do",
        })
        _thread_local.session = s
    return _thread_local.session


# ---------------------------------------------------------------------------
# Proxy domain validation (SSRF prevention)
# ---------------------------------------------------------------------------
def _is_allowed_url(url):
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or ""
        return any(domain in host for domain in ALLOWED_PROXY_DOMAINS)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# M3U8 rewrite
# ---------------------------------------------------------------------------
def rewrite_m3u8(content, base_url):
    lines = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            if "URI=" in line:
                line = re.sub(
                    r'URI="([^"]+)"',
                    lambda m: (
                        'URI="/proxy?url='
                        + urllib.parse.quote(
                            urllib.parse.urljoin(base_url, m.group(1))
                        )
                        + '"'
                    ),
                    line,
                )
            lines.append(line)
        else:
            full_url = urllib.parse.urljoin(base_url, line)
            lines.append("/proxy?url=" + urllib.parse.quote(full_url))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Camera info fetch (parallel)
# ---------------------------------------------------------------------------
def _fetch_camera_info(cam_id):
    try:
        session = _get_session()
        r = session.post(
            TOPIS_INFO_URL,
            data={"camId": cam_id, "cctvSourceCd": "HP"},
            timeout=5,
        )
        r.raise_for_status()
        data = r.json()
        row = data["rows"][0]
        row["proxyUrl"] = "/proxy?url=" + urllib.parse.quote(row["hlsUrl"])
        return row
    except requests.RequestException as e:
        logger.warning("Camera %s fetch failed: %s", cam_id, e)
    except (KeyError, IndexError) as e:
        logger.warning("Camera %s parse failed: %s", cam_id, e)
    return None


def fetch_all_cameras():
    with _camera_lock:
        ids = list(CURRENT_CAMERA_IDS)

    if not ids:
        return []
    results = []
    with ThreadPoolExecutor(max_workers=min(len(ids), 10)) as pool:
        futures = {pool.submit(_fetch_camera_info, cid): cid for cid in ids}
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                results.append(result)
    return results


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
class ProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        logger.debug("HTTP %s", fmt % args)

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/api/add_camera":
            body = self._read_json_body()
            new_id = str(body.get("id", "")).strip()
            if not new_id:
                self._send_json({"error": "Camera ID is required."}, 400)
                return
            with _camera_lock:
                if new_id in CURRENT_CAMERA_IDS:
                    self._send_json(
                        {"error": "Camera already registered.",
                         "cameras": list(CURRENT_CAMERA_IDS)},
                    )
                    return
                CURRENT_CAMERA_IDS.append(new_id)
                _save_camera_ids(CURRENT_CAMERA_IDS)
            logger.info("Camera added: %s", new_id)
            self._send_json({"status": "ok", "cameras": list(CURRENT_CAMERA_IDS)})

        elif parsed.path == "/api/delete_camera":
            body = self._read_json_body()
            del_id = str(body.get("id", "")).strip()
            with _camera_lock:
                if del_id in CURRENT_CAMERA_IDS:
                    CURRENT_CAMERA_IDS.remove(del_id)
                    _save_camera_ids(CURRENT_CAMERA_IDS)
                    logger.info("Camera deleted: %s", del_id)
            self._send_json({"status": "ok", "cameras": list(CURRENT_CAMERA_IDS)})

        else:
            self._send_json({"error": "Not Found"}, 404)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/":
            body = HTML_TEMPLATE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif parsed.path == "/api/cameras":
            cams = fetch_all_cameras()
            self._send_json(cams)

        elif parsed.path == "/api/health":
            self._send_json({"status": "ok", "cameras": len(CURRENT_CAMERA_IDS)})

        elif parsed.path == "/api/exit":
            self._send_json({"status": "shutting_down"})
            logger.info("Shutdown requested")
            threading.Thread(
                target=lambda: (time.sleep(0.5), os._exit(0)),
                daemon=True,
            ).start()

        elif parsed.path == "/proxy":
            self._handle_proxy(parsed)

        else:
            self._send_json({"error": "Not Found"}, 404)

    def _handle_proxy(self, parsed):
        query = urllib.parse.parse_qs(parsed.query)
        target_url = query.get("url", [None])[0]

        if not target_url:
            self._send_json({"error": "url parameter required."}, 400)
            return

        if not _is_allowed_url(target_url):
            logger.warning("Blocked proxy request: %s", target_url)
            self._send_json({"error": "Domain not allowed."}, 403)
            return

        try:
            session = _get_session()
            resp = session.get(target_url, timeout=10, verify=False)
            content = resp.content

            if ".m3u8" in target_url.lower() or b"#EXTM3U" in content:
                content = rewrite_m3u8(
                    content.decode(errors="ignore"), target_url
                ).encode()

            self.send_response(200)
            self.send_header(
                "Content-Type",
                resp.headers.get("Content-Type", "application/octet-stream"),
            )
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        except requests.RequestException as e:
            logger.error("Proxy request failed (%s): %s", target_url, e)
            self._send_json({"error": "Stream load failed"}, 502)


# ---------------------------------------------------------------------------
# HTML Template (v2.0)
# ---------------------------------------------------------------------------
HTML_TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CCTV Dashboard v2.0</title>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <style>
        * { box-sizing: border-box; }
        body { margin: 0; background: #0f172a; color: white; font-family: 'Segoe UI', sans-serif; }

        header {
            padding: 15px 25px; background: #1e293b;
            display: flex; justify-content: space-between; align-items: center;
            border-bottom: 2px solid #3b82f6;
            position: sticky; top: 0; z-index: 100;
        }
        header h2 { margin: 0; font-size: 1.2rem; }

        .control-panel {
            padding: 16px 20px; background: #1e293b;
            margin: 16px; border-radius: 12px;
            display: flex; gap: 10px; align-items: center;
            flex-wrap: wrap;
        }
        .control-panel input {
            padding: 10px 14px; border-radius: 8px;
            border: 1px solid #334155; background: #0f172a;
            color: white; flex: 1; min-width: 200px;
            font-size: 14px; outline: none; transition: border-color 0.2s;
        }
        .control-panel input:focus { border-color: #3b82f6; }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
            gap: 16px; padding: 0 16px 16px;
        }

        .card {
            background: #1e293b; border-radius: 12px; overflow: hidden;
            border: 1px solid #334155;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            transition: border-color 0.2s;
        }
        .card:hover { border-color: #3b82f6; }

        video {
            width: 100%; aspect-ratio: 16/9;
            background: #000; display: block;
        }

        .title-bar {
            padding: 10px 14px; font-weight: 600; font-size: 13px;
            background: #334155;
            display: flex; justify-content: space-between; align-items: center;
        }
        .title-bar .cam-name {
            overflow: hidden; text-overflow: ellipsis;
            white-space: nowrap; flex: 1;
        }

        .status-badge {
            display: inline-block; width: 8px; height: 8px;
            border-radius: 50%; margin-right: 8px;
            background: #22c55e; animation: pulse 2s infinite;
        }
        .status-badge.error { background: #ef4444; animation: none; }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .btn {
            padding: 8px 16px; border-radius: 8px; border: none;
            cursor: pointer; font-weight: 600; font-size: 13px;
            transition: all 0.2s;
        }
        .btn-primary { background: #3b82f6; color: white; }
        .btn-primary:hover { background: #2563eb; }
        .btn-danger { background: #ef4444; color: white; }
        .btn-danger:hover { background: #dc2626; }
        .btn-sm { padding: 4px 10px; font-size: 12px; }

        .btn-group { display: flex; gap: 8px; }

        .loading-overlay {
            display: flex; align-items: center; justify-content: center;
            aspect-ratio: 16/9; background: #000; color: #94a3b8;
            font-size: 14px;
        }
        .spinner {
            width: 28px; height: 28px; border: 3px solid #334155;
            border-top-color: #3b82f6; border-radius: 50%;
            animation: spin 0.8s linear infinite; margin-right: 10px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        .toast-container {
            position: fixed; bottom: 20px; right: 20px; z-index: 1000;
            display: flex; flex-direction: column; gap: 8px;
        }
        .toast {
            padding: 12px 20px; border-radius: 8px; font-size: 13px;
            color: white; animation: slideIn 0.3s ease;
            box-shadow: 0 4px 12px rgba(0,0,0,0.4);
        }
        .toast.success { background: #16a34a; }
        .toast.error { background: #dc2626; }
        .toast.info { background: #2563eb; }
        @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } }

        .cam-count {
            background: #3b82f6; padding: 2px 10px; border-radius: 12px;
            font-size: 12px; margin-left: 10px;
        }

        @media (max-width: 500px) {
            .grid { grid-template-columns: 1fr; }
            header h2 { font-size: 1rem; }
            .control-panel { flex-direction: column; }
            .control-panel input { min-width: unset; width: 100%; }
        }
    </style>
</head>
<body>
    <header>
        <h2>
            실시간 CCTV 대시보드
            <span class="cam-count" id="camCount">0</span>
        </h2>
        <div class="btn-group">
            <button class="btn btn-primary" onclick="loadCameras()">새로고침</button>
            <button class="btn btn-danger" onclick="exitServer()">서버 종료</button>
        </div>
    </header>

    <div class="control-panel">
        <input type="text" id="camIdInput"
               placeholder="추가할 CCTV ID 입력 (예: 101, 261 등)"
               onkeydown="if(event.key==='Enter') addCamera()">
        <button class="btn btn-primary" onclick="addCamera()">카메라 추가</button>
    </div>

    <div class="grid" id="grid">
        <div class="card">
            <div class="loading-overlay">
                <div class="spinner"></div> 카메라 목록을 불러오는 중...
            </div>
        </div>
    </div>

    <div class="toast-container" id="toasts"></div>

    <script>
        var hlsInstances = {};

        function showToast(message, type) {
            type = type || 'info';
            var container = document.getElementById('toasts');
            var toast = document.createElement('div');
            toast.className = 'toast ' + type;
            toast.textContent = message;
            container.appendChild(toast);
            setTimeout(function() { toast.remove(); }, 3000);
        }

        function escapeHtml(str) {
            var div = document.createElement('div');
            div.textContent = str;
            return div.innerHTML;
        }

        function destroyAllStreams() {
            Object.keys(hlsInstances).forEach(function(key) {
                try { hlsInstances[key].destroy(); } catch(e) {}
                delete hlsInstances[key];
            });
        }

        function setupHls(videoEl, url, camId) {
            if (!Hls.isSupported()) return;
            var hls = new Hls({
                lowLatencyMode: true,
                maxBufferLength: 10,
                maxMaxBufferLength: 30
            });
            hls.loadSource(url);
            hls.attachMedia(videoEl);
            hls.on(Hls.Events.ERROR, function(event, data) {
                if (data.fatal) {
                    var badge = document.getElementById('badge-' + camId);
                    if (badge) badge.classList.add('error');
                    if (data.type === Hls.ErrorTypes.NETWORK_ERROR) {
                        setTimeout(function() { hls.startLoad(); }, 3000);
                    } else if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
                        hls.recoverMediaError();
                    }
                }
            });
            hls.on(Hls.Events.MANIFEST_PARSED, function() {
                var badge = document.getElementById('badge-' + camId);
                if (badge) badge.classList.remove('error');
            });
            hlsInstances[camId] = hls;
        }

        async function loadCameras() {
            var grid = document.getElementById('grid');
            grid.innerHTML = '<div class="card"><div class="loading-overlay"><div class="spinner"></div> 카메라 목록을 불러오는 중...</div></div>';
            destroyAllStreams();

            try {
                var res = await fetch('/api/cameras');
                if (!res.ok) throw new Error('Server error');
                var cams = await res.json();

                document.getElementById('camCount').textContent = cams.length;
                grid.innerHTML = '';

                if (cams.length === 0) {
                    grid.innerHTML = '<div class="card"><div class="loading-overlay">등록된 카메라가 없습니다. 위에서 카메라 ID를 추가해주세요.</div></div>';
                    return;
                }

                cams.forEach(function(cam) {
                    var safeId = escapeHtml(String(cam.cctvId));
                    var safeName = escapeHtml(String(cam.cctvName || ''));
                    var div = document.createElement('div');
                    div.className = 'card';
                    div.id = 'card-' + safeId;

                    var titleBar = document.createElement('div');
                    titleBar.className = 'title-bar';

                    var nameSpan = document.createElement('span');
                    nameSpan.className = 'cam-name';

                    var badge = document.createElement('span');
                    badge.className = 'status-badge';
                    badge.id = 'badge-' + safeId;
                    nameSpan.appendChild(badge);
                    nameSpan.appendChild(document.createTextNode(safeName + ' (ID: ' + safeId + ')'));

                    var delBtn = document.createElement('button');
                    delBtn.className = 'btn btn-danger btn-sm';
                    delBtn.textContent = '삭제';
                    delBtn.setAttribute('data-cam-id', safeId);
                    delBtn.onclick = function() { deleteCamera(this.getAttribute('data-cam-id')); };

                    titleBar.appendChild(nameSpan);
                    titleBar.appendChild(delBtn);

                    var video = document.createElement('video');
                    video.id = 'v-' + safeId;
                    video.controls = true;
                    video.autoplay = true;
                    video.muted = true;
                    video.playsInline = true;

                    div.appendChild(titleBar);
                    div.appendChild(video);
                    grid.appendChild(div);
                    setupHls(video, cam.proxyUrl, safeId);
                });
            } catch(e) {
                grid.innerHTML = '<div class="card"><div class="loading-overlay" style="color:#ef4444">카메라 로드 실패. 새로고침 해주세요.</div></div>';
                showToast('Load failed: ' + e.message, 'error');
            }
        }

        async function addCamera() {
            var input = document.getElementById('camIdInput');
            var id = input.value.trim();
            if (!id) { showToast('카메라 ID를 입력해주세요.', 'error'); return; }

            try {
                var res = await fetch('/api/add_camera', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id: id})
                });
                var data = await res.json();
                if (data.error) { showToast(data.error, 'error'); return; }
                input.value = '';
                showToast('Camera ' + id + ' added', 'success');
                loadCameras();
            } catch(e) {
                showToast('Add failed: ' + e.message, 'error');
            }
        }

        async function deleteCamera(id) {
            if (!confirm('카메라 ' + id + ' 을(를) 삭제하시겠습니까?')) return;
            try {
                await fetch('/api/delete_camera', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id: id})
                });
                showToast('Camera ' + id + ' deleted', 'success');
                loadCameras();
            } catch(e) {
                showToast('Delete failed: ' + e.message, 'error');
            }
        }

        async function exitServer() {
            if (!confirm('서버를 종료하시겠습니까?')) return;
            try {
                await fetch('/api/exit');
                showToast('Server shutting down...', 'info');
            } catch(e) {}
        }

        loadCameras();
    </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Server startup
# ---------------------------------------------------------------------------
_server = None


def _graceful_shutdown(signum, frame):
    logger.info("Signal %d received, shutting down...", signum)
    if _server:
        _server.shutdown()
    raise SystemExit(0)


def main():
    global _server

    signal.signal(signal.SIGINT, _graceful_shutdown)
    signal.signal(signal.SIGTERM, _graceful_shutdown)

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    _server = ThreadingHTTPServer(("127.0.0.1", port), ProxyHandler)
    threading.Thread(target=_server.serve_forever, daemon=True).start()

    url = "http://127.0.0.1:{}".format(port)
    logger.info("Server running: %s", url)

    import webbrowser
    webbrowser.open(url)

    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Server shutting down.")
        _server.shutdown()


if __name__ == "__main__":
    main()
