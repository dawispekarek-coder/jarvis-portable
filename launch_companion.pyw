#!/usr/bin/env python3
"""launch_companion.pyw — portable Jarvis launcher (mirrors the
original V2Autonomy launcher 1:1, adapted to repo layout).

- ensures local deps (Ollama) like the original
- spawns uvicorn companion_api:app from companion/ with venv pythonw
- opens an Edge --app window with its own BrowserProfile
- errors surface via MessageBox, never a silent exit
- first run on a new PC: auto-creates the venv + installs deps in a
  visible console window (no flashing-away cmd)
"""
from pathlib import Path
import sys, os, time, json, subprocess, urllib.request, ctypes

ROOT = Path(__file__).resolve().parent
BASE = ROOT / 'companion'                      # == BrainCore on the origin PC
sys.path.insert(0, str(BASE))
try:
    import companion_settings as settings
    PORT = int(settings.PORT)
    EXPECTED_BUILD = settings.build_id()
except Exception:
    PORT = 7430
    EXPECTED_BUILD = None

URL = f'http://127.0.0.1:{PORT}'
PY = BASE / '.venv' / 'Scripts' / 'pythonw.exe'
FLAGS = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
LOG = BASE / 'companion_launch.log'


def request(url, body=None, headers=None):
    req = urllib.request.Request(url, data=body, headers=headers or {},
                                 method='POST' if body is not None else 'GET')
    with urllib.request.urlopen(req, timeout=2) as r:
        return json.load(r)


def spawn(command, cwd):
    with LOG.open('ab') as log:
        return subprocess.Popen(command, cwd=cwd, creationflags=FLAGS,
                                stdin=subprocess.DEVNULL, stdout=log,
                                stderr=log, close_fds=True)


def dependencies():
    """Same as the original: Ollama backend only (legacy jarvis.main
    is an H:\\-path service that does not exist on a portable PC)."""
    for port in (11434, 11435):
        try:
            request(f'http://127.0.0.1:{port}/api/tags')
            return                                    # one is alive — done
        except Exception:
            pass
    candidates = [
        Path(os.environ.get('LOCALAPPDATA', '')) /
            'Programs' / 'Ollama' / 'ollama.exe',
        Path(r'C:\Program Files\Ollama\ollama.exe'),
    ]
    exe = next((p for p in candidates if p.is_file()), None)
    if exe:
        spawn([str(exe), 'serve'], ROOT)


def healthy(expected):
    try:
        d = request(URL + '/health')
        if d.get('service') != 'RealJarvis V2 companion':
            return False
        return expected is None or d.get('build') == expected
    except Exception:
        return False


def ensure_env():
    """First run on a new PC: build companion/.venv + install deps in
    a VISIBLE console (stays open on error) — no silent cmd flash."""
    if PY.is_file():
        return
    req = BASE / 'companion_requirements.txt'
    if not req.is_file():
        raise RuntimeError('Chybí companion_requirements.txt — repozitář není kompletní.')
    pyexe = Path(sys.executable)
    py = pyexe.with_name('python.exe')
    py = py if py.is_file() else pyexe
    script = BASE / '_first_run_setup.cmd'
    venv_py = BASE / '.venv' / 'Scripts' / 'python.exe'
    script.write_text(
        "@echo off\r\necho == Jarvis first-run setup ==\r\n"
        f'"{py}" -m venv "{BASE}\\.venv"\r\n'
        "if errorlevel 1 goto fail\r\n"
        f'"{venv_py}" -m pip install --upgrade pip\r\n'
        f'"{venv_py}" -m pip install -r "{req}" '
        "pillow numpy httpx opencv-python-headless\r\n"
        "if errorlevel 1 goto fail\r\n"
        "echo.\r\necho DONE - you can close this window.\r\n"
        "goto end\r\n:fail\r\n"
        "echo.\r\necho SETUP FAILED - read the errors above.\r\n"
        "pause\r\n:end\r\n",
        encoding="ascii", errors="replace")
    subprocess.Popen(["cmd", "/c", "start", '"Jarvis first-run setup"',
                      str(script)], shell=False)
    for _ in range(600):
        if PY.is_file():
            time.sleep(2)
            return
        time.sleep(1)
    raise RuntimeError('Venv se nevytvořil — podrobnosti v okně setupu.')


def main():
    ensure_env()
    if not PY.is_file():
        raise RuntimeError('Chybí prostředí JARVIS (companion/.venv). '
                           'Spusť nejdřív setup.ps1.')
    dependencies()
    expected = EXPECTED_BUILD
    if not healthy(expected):
        try:
            existing = request(URL + '/health')
            if existing.get('service') != 'RealJarvis V2 companion':
                raise RuntimeError('Port používá jiná aplikace.')
            key = BASE / 'companion_control.key'
            if key.is_file():
                request(URL + '/companion/reload', b'',
                        {'X-Jarvis-Control':
                         key.read_text(encoding='ascii').strip()})
                time.sleep(.7)
        except RuntimeError:
            raise
        except Exception:
            pass
        spawn([str(PY), '-m', 'uvicorn', 'companion_api:app',
               '--host', '127.0.0.1', '--port', str(PORT),
               '--no-access-log', '--log-level', 'warning'], BASE)
        for _ in range(70):
            if healthy(expected):
                break
            time.sleep(.2)
    if not healthy(expected):
        tail = ''
        try:
            tail = '\n\n' + '\n'.join(
                LOG.read_text(encoding='utf-8', errors='replace')
                   .splitlines()[-15:])
        except Exception:
            pass
        raise RuntimeError('JARVIS se nepřipojil k aktuální verzi. '
                           'Podrobnosti jsou v companion_launch.log.' + tail)
    if '--background' in sys.argv:
        return
    edge = Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
    if not edge.exists():
        edge = Path(r'C:\Program Files\Microsoft\Edge\Application\msedge.exe')
    if edge.exists():
        spawn([str(edge), '--app=' + URL + '/',
               '--user-data-dir=' + str(ROOT / 'BrowserProfile'),
               '--no-first-run', '--no-default-browser-check',
               '--window-size=1366,900'], ROOT)
    else:
        import webbrowser
        webbrowser.open(URL + '/')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        ctypes.windll.user32.MessageBoxW(
            None, str(exc), 'JARVIS — spuštění', 0x10)
