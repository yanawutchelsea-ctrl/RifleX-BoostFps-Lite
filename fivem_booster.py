"""
FiveM Booster v2  -  pywebview, ธีมขาว, ฟอนต์สวย, มี ToS, ปรับแต่งได้
ติดตั้ง:  pip install pywebview psutil
รัน:      python fivem_booster_v2.py   (แนะนำ Run as Administrator)
ฟอนต์โหลดจาก Google Fonts (ต้องต่ออินเทอร์เน็ตครั้งแรก ถ้าไม่มีจะใช้ Leelawadee UI / Segoe UI แทน)
"""
import ctypes, json, os, re, shutil, subprocess, tempfile, threading, time
from datetime import datetime
import webview
try:
    import psutil
except ImportError:
    psutil = None
try:
    import winreg
except ImportError:
    winreg = None

IS_WIN = os.name == "nt"
NOWIN = 0x08000000 if IS_WIN else 0
TOS_VERSION = "2.0"
HIGH_PERF = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
CFG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "FiveMBooster")
CFG_FILE = os.path.join(CFG_DIR, "config.json")
FIVEM_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "FiveM")

DEFAULT = {
    "tos": None, "accent": "#34c38f", "mode": "low", "anim": True,
    "presets": {
        "low": ["temp", "dns", "gamemode"],
        "medium": ["temp", "dns", "gamemode", "power", "priority", "ram", "dvr"],
        "high": ["temp", "dns", "gamemode", "power", "priority", "ram", "dvr", "bg", "cache", "gpu"],
    },
    "bg_apps": ["chrome.exe", "msedge.exe", "firefox.exe", "onedrive.exe", "spotify.exe", "teams.exe", "steamwebhelper.exe"],
    "kill_bg": False, "auto": False, "auto_mode": "medium",
    "stats": {"runs": 0, "freed_mb": 0}, "restore": {},
}


def load_cfg():
    cfg = json.loads(json.dumps(DEFAULT))
    try:
        with open(CFG_FILE, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_cfg(cfg):
    os.makedirs(CFG_DIR, exist_ok=True)
    with open(CFG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, creationflags=NOWIN)


def fivem_procs():
    if not psutil:
        return []
    return [p for p in psutil.process_iter(["name"])
            if (p.info["name"] or "").lower().startswith(("fivem", "gta5"))]


def dir_size(path):
    t = 0
    for r, _, fs in os.walk(path):
        for f in fs:
            try: t += os.path.getsize(os.path.join(r, f))
            except OSError: pass
    return t


def wipe(path):
    freed = 0
    if not os.path.isdir(path):
        return 0
    for n in os.listdir(path):
        full = os.path.join(path, n)
        try:
            if os.path.isdir(full) and not os.path.islink(full):
                s = dir_size(full); shutil.rmtree(full, ignore_errors=True)
                if not os.path.exists(full): freed += s
            else:
                s = os.path.getsize(full); os.remove(full); freed += s
        except OSError:
            pass
    return freed


def reg_set(cfg, path, name, value):
    """ตั้งค่า registry (HKCU) พร้อมจำค่าเดิมไว้ให้ restore"""
    key_id = f"{path}|{name}"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as k:
        if key_id not in cfg["restore"]:
            try: cfg["restore"][key_id] = winreg.QueryValueEx(k, name)[0]
            except FileNotFoundError: cfg["restore"][key_id] = None
        if isinstance(value, int):
            winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, value)
        else:
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)


# ------------------------------------------------------------------ tasks
def t_temp(c, ctx):
    f = wipe(tempfile.gettempdir()); ctx["freed"] += f
    return f"ล้างไฟล์ชั่วคราว {f/1048576:.0f} MB"

def t_dns(c, ctx):
    if IS_WIN: run(["ipconfig", "/flushdns"])
    return "ล้าง DNS cache แล้ว"

def t_gamemode(c, ctx):
    if not IS_WIN: return "ข้าม (Windows เท่านั้น)"
    reg_set(c, r"Software\Microsoft\GameBar", "AutoGameModeEnabled", 1)
    return "เปิด Windows Game Mode"

def t_power(c, ctx):
    if not IS_WIN: return "ข้าม (Windows เท่านั้น)"
    m = re.search(r"([0-9a-fA-F\-]{36})", run(["powercfg", "/getactivescheme"]).stdout)
    if m and "plan" not in c["restore"] and m.group(1).lower() != HIGH_PERF:
        c["restore"]["plan"] = m.group(1)
    run(["powercfg", "/setactive", HIGH_PERF])
    return "เปิดแผนไฟ High performance"

def t_priority(c, ctx):
    ps = fivem_procs()
    if not ps: return "ยังไม่พบ FiveM (เปิดเกมแล้วบูสต์อีกครั้ง)"
    n = 0
    for p in ps:
        try: p.nice(psutil.HIGH_PRIORITY_CLASS if IS_WIN else -5); n += 1
        except Exception: pass
    return f"ตั้ง FiveM เป็น High priority ({n} โปรเซส)"

def t_ram(c, ctx):
    if not (IS_WIN and psutil): return "ข้าม (Windows เท่านั้น)"
    before = psutil.virtual_memory().available
    skip = {p.pid for p in fivem_procs()} | {os.getpid()}
    k32, psa = ctypes.windll.kernel32, ctypes.windll.psapi
    for p in psutil.process_iter(["pid"]):
        if p.info["pid"] in skip: continue
        h = k32.OpenProcess(0x0500, False, p.info["pid"])
        if h: psa.EmptyWorkingSet(h); k32.CloseHandle(h)
    time.sleep(.4)
    g = max(0, psutil.virtual_memory().available - before); ctx["freed"] += g
    return f"คืนแรมให้เกม {g/1048576:.0f} MB"

def t_dvr(c, ctx):
    if not IS_WIN: return "ข้าม (Windows เท่านั้น)"
    reg_set(c, r"System\GameConfigStore", "GameDVR_Enabled", 0)
    reg_set(c, r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", 0)
    return "ปิดการอัดคลิปเบื้องหลัง (Game DVR)"

def t_bg(c, ctx):
    if not psutil: return "ข้าม"
    names = {a.lower() for a in c["bg_apps"]}; n = 0
    for p in psutil.process_iter(["name"]):
        if (p.info["name"] or "").lower() in names:
            try:
                p.kill() if c["kill_bg"] else p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if IS_WIN else 10)
                n += 1
            except Exception: pass
    return f"{'ปิด' if c['kill_bg'] else 'ลด priority'}แอปเบื้องหลัง {n} โปรเซส"

def t_cache(c, ctx):
    base = os.path.join(FIVEM_DIR, "FiveM.app", "data")
    f = sum(wipe(os.path.join(base, s)) for s in ("server-cache", "server-cache-priv", "cache/browser"))
    ctx["freed"] += f
    return f"ล้างแคช FiveM {f/1048576:.0f} MB"

def t_gpu(c, ctx):
    exe = os.path.join(FIVEM_DIR, "FiveM.exe")
    if not (IS_WIN and os.path.exists(exe)): return "ไม่พบ FiveM.exe"
    reg_set(c, r"Software\Microsoft\DirectX\UserGpuPreferences", exe, "GpuPreference=2;")
    return "ตั้งให้ FiveM ใช้การ์ดจอแรงสุด"

TASKS = [
    ("temp", "ล้างไฟล์ชั่วคราว", "ลบไฟล์ใน Temp ที่ไม่ได้ใช้งาน", t_temp),
    ("dns", "ล้าง DNS cache", "ช่วยเรื่องเชื่อมต่อเซิร์ฟเวอร์ผิดปกติ", t_dns),
    ("gamemode", "เปิด Game Mode", "ให้ Windows ให้ทรัพยากรกับเกมก่อน", t_gamemode),
    ("power", "แผนไฟประสิทธิภาพสูง", "ปลดล็อกความเร็ว CPU เต็มที่ (กินไฟขึ้น)", t_power),
    ("priority", "FiveM เป็น High priority", "ให้ CPU เลือกประมวลผลเกมก่อน", t_priority),
    ("ram", "คืนแรมจากโปรเซสอื่น", "บีบแรมของแอปที่ไม่ได้ใช้ให้ว่างขึ้น", t_ram),
    ("dvr", "ปิด Game DVR", "หยุดอัดคลิปเบื้องหลัง ลดอาการกระตุก", t_dvr),
    ("bg", "จัดการแอปเบื้องหลัง", "ลด priority (หรือปิด) ตามรายชื่อที่ตั้งไว้", t_bg),
    ("cache", "ล้างแคช FiveM", "แก้บั๊กแคชเสีย เข้าเซิร์ฟครั้งแรกอาจโหลดนานขึ้น", t_cache),
    ("gpu", "บังคับใช้การ์ดจอแรง", "เหมาะกับโน้ตบุ๊กที่มีการ์ดจอ 2 ตัว", t_gpu),
]
TASK_FN = {t[0]: t[3] for t in TASKS}


# ------------------------------------------------------------------ api
class Api:
    def __init__(self):
        self.cfg = load_cfg()
        self._window = None
        self._busy = False

    def _js(self, fn, *a):
        if self._window:
            self._window.evaluate_js(f"{fn}({','.join(json.dumps(x, ensure_ascii=False) for x in a)})")

    def get_state(self):
        ram = round(psutil.virtual_memory().total / 2**30) if psutil else 0
        rec = "high" if 0 < ram < 8 else "medium" if ram < 16 else "low"
        return {"cfg": self.cfg, "tos_ok": (self.cfg["tos"] or {}).get("v") == TOS_VERSION,
                "tasks": [t[:3] for t in TASKS], "defaults": DEFAULT["presets"],
                "ram_gb": ram, "cores": os.cpu_count(), "rec": rec, "admin": self._is_admin()}

    def _is_admin(self):
        try: return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception: return False

    def tos_accept(self):
        self.cfg["tos"] = {"v": TOS_VERSION, "at": datetime.now().isoformat(timespec="seconds")}
        save_cfg(self.cfg); return True

    def quit(self):
        self._window.destroy()

    def save(self, key, value):
        self.cfg[key] = value; save_cfg(self.cfg); return True

    def save_preset(self, mode, ids):
        self.cfg["presets"][mode] = [i for i in ids if i in TASK_FN]; save_cfg(self.cfg); return True

    def stats(self):
        if not psutil: return {"cpu": 0, "ram": 0, "fivem": False}
        return {"cpu": psutil.cpu_percent(), "ram": psutil.virtual_memory().percent, "fivem": bool(fivem_procs())}

    def boost(self, mode):
        if self._busy or mode not in self.cfg["presets"]: return False
        self._busy = True
        threading.Thread(target=self._plan, args=(mode,), daemon=True).start(); return True

    def restore(self):
        r = self.cfg["restore"]; n = 0
        if IS_WIN:
            if r.get("plan"): run(["powercfg", "/setactive", r["plan"]]); n += 1
            for k, v in list(r.items()):
                if "|" not in k: continue
                path, name = k.split("|", 1)
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as h:
                        if v is None: winreg.DeleteValue(h, name)
                        else: winreg.SetValueEx(h, name, 0, winreg.REG_DWORD if isinstance(v, int) else winreg.REG_SZ, v)
                    n += 1
                except OSError: pass
        self.cfg["restore"] = {}; save_cfg(self.cfg)
        return f"คืนค่าเดิมแล้ว {n} รายการ" if n else "ไม่มีค่าที่ต้องคืน"

    def _plan(self, mode):
        ids = [i for i in self.cfg["presets"][mode] if i in TASK_FN]
        names = {t[0]: t[1] for t in TASKS}
        ctx = {"freed": 0}
        self._js("onPlan", [names[i] for i in ids]); time.sleep(.5)
        for n, i in enumerate(ids):
            self._js("onStep", n, "run", ""); time.sleep(.4)
            try: self._js("onStep", n, "ok", TASK_FN[i](self.cfg, ctx))
            except Exception as e: self._js("onStep", n, "fail", str(e)[:90])
        mb = round(ctx["freed"] / 1048576)
        self.cfg["stats"]["runs"] += 1; self.cfg["stats"]["freed_mb"] += mb; save_cfg(self.cfg)
        self._js("onDone", mb, self.cfg["stats"]); self._busy = False

    def watcher(self):
        was = False
        while True:
            time.sleep(3)
            now = bool(fivem_procs())
            if now and not was and self.cfg["auto"] and not self._busy:
                time.sleep(20)  # รอให้เกมเปิดครบ
                self._js("onAuto", self.cfg["auto_mode"]); self.boost(self.cfg["auto_mode"])
            was = now


API = Api()

HTML = r"""
<!doctype html><html lang="th"><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Kanit:wght@400;500;600;700&family=IBM+Plex+Sans+Thai:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{--accent:#34c38f;--a2:color-mix(in srgb,var(--accent) 45%,#fff);--soft:color-mix(in srgb,var(--accent) 11%,#fff);
 --ink:#151a27;--mut:#7a8296;--line:#eceff5;--bg2:#f6f8fc;
 --head:"Kanit","Leelawadee UI","Segoe UI",sans-serif;--body:"IBM Plex Sans Thai","Leelawadee UI","Segoe UI",sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;background:#fff;color:var(--ink);font:14px/1.5 var(--body);overflow:hidden;user-select:none}
h1,h2,.big,.tabs button,.go,.modes b{font-family:var(--head)}
.blob{position:fixed;border-radius:50%;filter:blur(80px);opacity:.5;background:var(--a2);z-index:0;transition:background .6s}
.b1{width:380px;height:380px;top:-120px;left:-100px;animation:d1 16s ease-in-out infinite alternate}
.b2{width:340px;height:340px;bottom:-110px;right:-80px;animation:d2 19s ease-in-out infinite alternate}
@keyframes d1{to{transform:translate(90px,110px) scale(1.2)}}@keyframes d2{to{transform:translate(-100px,-70px) scale(1.2)}}
body.noanim *{animation:none!important;transition:none!important}
.app{position:relative;z-index:1;height:100%;display:grid;grid-template-columns:400px 1fr;gap:26px;padding:26px 30px}
.col{display:flex;flex-direction:column;gap:16px;min-height:0}
header{display:flex;justify-content:space-between;align-items:center}
h1{font-size:24px;font-weight:600;letter-spacing:-.4px}
.badge{display:flex;gap:8px;align-items:center;font-size:12.5px;color:var(--mut);padding:6px 12px;border-radius:99px;background:#fffc;border:1px solid var(--line)}
.dot{width:8px;height:8px;border-radius:50%;background:#c9ceda}.badge.on .dot{background:var(--accent);animation:ping 1.8s infinite}
@keyframes ping{to{box-shadow:0 0 0 9px #0000}}.badge.on .dot{box-shadow:0 0 0 0 var(--a2)}
.orb{position:relative;width:230px;height:230px;margin:0 auto;display:grid;place-items:center}
.orb:before{content:"";position:absolute;inset:14px;border-radius:50%;background:radial-gradient(circle at 35% 30%,#fff,var(--soft) 70%);
 box-shadow:0 20px 50px -14px color-mix(in srgb,var(--accent) 50%,#0000);animation:br 4.2s ease-in-out infinite}
@keyframes br{50%{transform:scale(1.04)}}
.orb svg{position:absolute;inset:0;transform:rotate(-90deg)}
.bar{stroke:url(#g);stroke-linecap:round;stroke-dasharray:628;stroke-dashoffset:628;transition:stroke-dashoffset .7s cubic-bezier(.3,.8,.3,1)}
.orb.run svg{animation:sp 2.2s linear infinite}.orb.run .bar{stroke-dasharray:170 628;stroke-dashoffset:0;transition:none}
@keyframes sp{to{transform:rotate(270deg)}}
.ctr{position:relative;text-align:center}.big{font-size:56px;font-weight:600;line-height:1;letter-spacing:-2px}
.big small{font-size:22px;color:var(--mut);margin-left:2px}.sub{font-size:13px;color:var(--mut);margin-top:6px;padding:0 24px}
.modes{position:relative;display:grid;grid-template-columns:repeat(3,1fr);padding:5px;border-radius:16px;background:var(--bg2);border:1px solid var(--line)}
.pill{position:absolute;top:5px;bottom:5px;left:5px;width:calc((100% - 10px)/3);border-radius:12px;background:#fff;box-shadow:0 6px 18px -6px #1e285038,0 0 0 1px var(--line);transition:transform .45s cubic-bezier(.5,1.4,.5,1)}
button{font:inherit;color:inherit;border:0;background:none;cursor:pointer}
.modes button{position:relative;z-index:1;padding:10px 0;color:var(--mut);transition:color .3s}.modes button.sel{color:var(--ink)}
.modes b{display:block;font-size:16px;font-weight:500}.modes span{font-size:11.5px}
.rec{font-size:12px;color:var(--accent);text-align:center;margin-top:-6px;min-height:18px}
.go{position:relative;overflow:hidden;padding:15px;border-radius:16px;color:#fff;font-size:17px;font-weight:500;
 background:linear-gradient(135deg,var(--accent),color-mix(in srgb,var(--accent) 65%,#fff));box-shadow:0 14px 30px -10px var(--accent);transition:transform .2s,filter .3s}
.go:hover{transform:translateY(-2px)}.go:disabled{filter:saturate(.4);transform:none;cursor:default}
.go:after{content:"";position:absolute;top:0;left:-60%;width:40%;height:100%;background:linear-gradient(100deg,#0000,#fff8,#0000);transform:skewX(-20deg);animation:sh 3.6s ease-in-out infinite}
@keyframes sh{0%,55%{left:-60%}100%{left:130%}}
.meters{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.meter{padding:11px 14px;border-radius:14px;background:#fff;border:1px solid var(--line)}
.meter div{display:flex;justify-content:space-between;font-size:12.5px;color:var(--mut);margin-bottom:7px}.meter b{color:var(--ink)}
.meter i{display:block;height:6px;border-radius:9px;background:var(--bg2);overflow:hidden}
.meter i:before{content:"";display:block;height:100%;width:var(--v,0%);border-radius:9px;background:linear-gradient(90deg,var(--a2),var(--accent));transition:width 1s}
.panel{background:#fffd;border:1px solid var(--line);border-radius:22px;display:flex;flex-direction:column;min-height:0;box-shadow:0 20px 50px -30px #1e285040}
.tabs{display:flex;gap:4px;padding:10px 12px 0;border-bottom:1px solid var(--line)}
.tabs button{padding:10px 16px;font-size:15px;color:var(--mut);position:relative}.tabs button.on{color:var(--ink)}
.tabs button.on:after{content:"";position:absolute;left:12px;right:12px;bottom:-1px;height:3px;border-radius:3px;background:var(--accent)}
.pg{display:none;flex:1;min-height:0;overflow:auto;padding:18px 20px;flex-direction:column;gap:9px}.pg.on{display:flex}
.pg::-webkit-scrollbar{width:0}
.empty{margin:auto;text-align:center;color:var(--mut);max-width:260px}.empty h2{color:var(--ink);font-weight:500;font-size:18px;margin-bottom:4px}
.row{display:grid;grid-template-columns:24px 1fr;gap:11px;padding:10px 13px;border-radius:13px;background:var(--bg2);animation:pop .4s cubic-bezier(.3,1.4,.5,1) both}
@keyframes pop{from{opacity:0;transform:translateY(8px) scale(.97)}}
.ico{width:22px;height:22px;border-radius:50%;border:2px solid #d6dbe6;margin-top:1px;display:grid;place-items:center}
.row.run .ico{border-color:var(--accent);border-top-color:#0000;animation:sp2 .8s linear infinite}@keyframes sp2{to{transform:rotate(360deg)}}
.row.ok .ico{background:var(--accent);border-color:var(--accent);animation:tk .4s}.row.ok .ico:after{content:"";width:5px;height:9px;border:solid #fff;border-width:0 2px 2px 0;transform:rotate(45deg) translate(-1px,-1px)}
.row.fail .ico{background:#ff6b6b;border-color:#ff6b6b}@keyframes tk{50%{transform:scale(1.3)}}
.row p{font-weight:600}.row small{display:block;font-size:12.5px;color:var(--mut)}
.opt{display:flex;align-items:center;gap:14px;padding:11px 14px;border-radius:13px;border:1px solid var(--line);background:#fff}
.opt div{flex:1}.opt p{font-weight:600}.opt small{color:var(--mut);font-size:12.5px;display:block}
.sw{position:relative;width:44px;height:26px;border-radius:99px;background:#dfe3ec;transition:background .3s;flex:none}
.sw:after{content:"";position:absolute;top:3px;left:3px;width:20px;height:20px;border-radius:50%;background:#fff;box-shadow:0 2px 6px #0003;transition:transform .35s cubic-bezier(.5,1.6,.5,1)}
.sw.on{background:var(--accent)}.sw.on:after{transform:translateX(18px)}
.sw2{display:flex;gap:10px;flex-wrap:wrap}.col-sw{width:34px;height:34px;border-radius:50%;border:3px solid #fff;box-shadow:0 0 0 1px var(--line);transition:transform .25s}
.col-sw.on{box-shadow:0 0 0 2px var(--ink)}.col-sw:hover{transform:scale(1.12)}
input[type=text],select{font:inherit;padding:9px 12px;border-radius:10px;border:1px solid var(--line);background:#fff;width:100%;outline:none}
input:focus,select:focus{border-color:var(--accent)}
.btn{padding:9px 16px;border-radius:11px;background:var(--bg2);border:1px solid var(--line);font-weight:500;transition:background .2s}.btn:hover{background:var(--soft)}
.sec{font-family:var(--head);font-weight:500;margin-top:8px}.note{font-size:12.5px;color:var(--mut)}
.modal{position:fixed;inset:0;z-index:9;background:#ffffffd9;backdrop-filter:blur(14px);display:none;place-items:center}.modal.on{display:grid}
.card{width:560px;max-height:88vh;display:flex;flex-direction:column;gap:14px;padding:28px;border-radius:26px;background:#fff;border:1px solid var(--line);box-shadow:0 40px 80px -30px #1e285060;animation:pop .5s cubic-bezier(.3,1.3,.5,1)}
.card h2{font-size:22px;font-weight:600}.tos{overflow:auto;padding:16px 18px;border-radius:14px;background:var(--bg2);border:1px solid var(--line);font-size:13.5px;line-height:1.65;max-height:300px;user-select:text}
.tos h3{font-family:var(--head);font-weight:500;font-size:14.5px;margin:10px 0 2px}.tos h3:first-child{margin-top:0}
.chk{display:flex;gap:10px;align-items:center;opacity:.45;transition:opacity .3s;pointer-events:none}.chk.ok{opacity:1;pointer-events:auto}
.chk .sw{width:40px;height:24px}.chk .sw:after{width:18px;height:18px}.chk .sw.on:after{transform:translateX(16px)}
.acts{display:flex;gap:10px;justify-content:flex-end}.acts .go{padding:12px 26px;font-size:15px}.acts .go:after{display:none}
</style></head><body>
<div class="blob b1"></div><div class="blob b2"></div>

<div class="app">
 <div class="col">
  <header><h1>FiveM Booster</h1><div class="badge" id="badge"><span class="dot"></span><span id="btxt">ยังไม่พบ FiveM</span></div></header>
  <div class="orb" id="orb">
   <svg width="230" height="230" viewBox="0 0 236 236"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="var(--a2)"/><stop offset="1" stop-color="var(--accent)"/></linearGradient></defs>
   <circle cx="118" cy="118" r="100" fill="none" stroke="#eceff5" stroke-width="9"/><circle class="bar" id="bar" cx="118" cy="118" r="100" fill="none" stroke-width="9"/></svg>
   <div class="ctr"><div class="big"><span id="pct">0</span><small>%</small></div><div class="sub" id="sub">พร้อมบูสต์</div></div>
  </div>
  <div class="modes"><div class="pill" id="pill"></div>
   <button data-m="low"><b>Low</b><span>เบา ปลอดภัย</span></button><button data-m="medium"><b>Medium</b><span>สมดุล</span></button><button data-m="high"><b>High</b><span>เต็มสูบ</span></button></div>
  <div class="rec" id="rec"></div>
  <button class="go" id="go">เริ่มบูสต์</button>
  <div class="meters"><div class="meter" id="mc"><div>CPU <b id="vc">0%</b></div><i></i></div><div class="meter" id="mr"><div>RAM <b id="vr">0%</b></div><i></i></div></div>
 </div>

 <div class="panel">
  <div class="tabs"><button class="on" data-p="log">กิจกรรม</button><button data-p="tune">ปรับแต่งโหมด</button><button data-p="set">ตั้งค่า</button></div>
  <div class="pg on" id="log"><div class="empty" id="empty"><h2>ยังไม่ได้บูสต์</h2>เลือกโหมดทางซ้ายแล้วกด “เริ่มบูสต์” ผลของแต่ละขั้นตอนจะแสดงที่นี่</div></div>
  <div class="pg" id="tune"></div>
  <div class="pg" id="set"></div>
 </div>
</div>

<div class="modal" id="tosm"><div class="card">
 <h2>ข้อตกลงการใช้งาน</h2>
 <div class="note">เลื่อนอ่านให้จบ แล้วเปิดสวิตช์ยืนยันเพื่อเริ่มใช้งาน</div>
 <div class="tos" id="tos">
  <h3>1. สิ่งที่โปรแกรมทำ</h3>โปรแกรมปรับค่าบนเครื่องของคุณเท่านั้น เช่น ล้างไฟล์ชั่วคราว ปรับ priority ของโปรเซส เปลี่ยนแผนไฟ และตั้งค่า Windows บางรายการ ซึ่งสามารถกด “คืนค่าเดิม” ได้ในหน้าตั้งค่า
  <h3>2. ไม่แก้ไขไฟล์เกม</h3>โปรแกรมไม่แก้ไข ฉีดโค้ด หรือยุ่งกับไฟล์เกม/Anti-cheat และไม่เกี่ยวข้องกับ Cfx.re, FiveM หรือ Rockstar Games การล้างแคช FiveM ลบเฉพาะโฟลเดอร์แคชที่เกมสร้างใหม่ได้เอง
  <h3>3. ไม่รับประกันผลลัพธ์</h3>ผลต่อ FPS ขึ้นกับฮาร์ดแวร์และเซิร์ฟเวอร์ที่เล่น โปรแกรมไม่รับประกันว่า FPS จะเพิ่มขึ้นตามที่ต้องการ
  <h3>4. ใช้ด้วยความรับผิดชอบของผู้ใช้</h3>โหมดที่เปิดการปิดแอปเบื้องหลัง อาจทำให้งานที่ยังไม่บันทึกในแอปเหล่านั้นหาย กรุณาบันทึกงานก่อนบูสต์ ผู้พัฒนาไม่รับผิดชอบต่อความเสียหายหรือข้อมูลสูญหายที่เกิดจากการใช้งาน
  <h3>5. ความเป็นส่วนตัว</h3>โปรแกรมไม่ส่งข้อมูลออกจากเครื่อง การตั้งค่าและบันทึกการยอมรับเก็บไว้ในไฟล์ config บนเครื่องคุณเท่านั้น
  <h3>6. การยอมรับ</h3>การกด “ยอมรับและเริ่มใช้งาน” หมายถึงคุณอ่านและเข้าใจข้อตกลงนี้แล้ว หากไม่ยอมรับ โปรแกรมจะปิดตัวลง
 </div>
 <div class="chk" id="chk"><div class="sw" id="chksw"></div><span>ฉันอ่านและยอมรับข้อตกลงทั้งหมด</span></div>
 <div class="acts"><button class="btn" id="dec">ไม่ยอมรับ</button><button class="go" id="acc" disabled>ยอมรับและเริ่มใช้งาน</button></div>
</div></div>

<script>
const $=i=>document.getElementById(i), ORDER=["low","medium","high"];
const COLORS=["#34c38f","#4f8cff","#8b6cff","#ff7a59","#f2a93b","#ec5f9a","#161a27"];
let S, mode="low", busy=false;

function mkSw(on,fn){const s=document.createElement("div");s.className="sw"+(on?" on":"");s.onclick=()=>{s.classList.toggle("on");fn(s.classList.contains("on"))};return s}
function opt(title,desc,sw){const d=document.createElement("div");d.className="opt";d.innerHTML=`<div><p>${title}</p><small>${desc}</small></div>`;d.appendChild(sw);return d}
function save(k,v){S.cfg[k]=v;pywebview.api.save(k,v)}

function setAccent(c){document.documentElement.style.setProperty("--accent",c)}
function setMode(m){mode=m;S.cfg.mode=m;pywebview.api.save("mode",m);
 $("pill").style.transform=`translateX(${ORDER.indexOf(m)*100}%)`;
 document.querySelectorAll(".modes button").forEach(b=>b.classList.toggle("sel",b.dataset.m===m));
 if(S)renderTune()}
document.querySelectorAll(".modes button").forEach(b=>b.onclick=()=>!busy&&setMode(b.dataset.m));
document.querySelectorAll(".tabs button").forEach(b=>b.onclick=()=>tab(b.dataset.p));
function tab(p){document.querySelectorAll(".tabs button").forEach(b=>b.classList.toggle("on",b.dataset.p===p));
 document.querySelectorAll(".pg").forEach(g=>g.classList.toggle("on",g.id===p))}

function countTo(el,to){const f=+el.textContent||0,t0=performance.now();(function s(t){const k=Math.min(1,(t-t0)/500);el.textContent=Math.round(f+(to-f)*(1-Math.pow(1-k,3)));if(k<1)requestAnimationFrame(s)})(t0)}
function prog(p){$("bar").style.strokeDashoffset=628*(1-p/100);countTo($("pct"),Math.round(p))}

function renderTune(){const el=$("tune");el.innerHTML="";
 const h=document.createElement("div");h.innerHTML=`<div class="sec">ขั้นตอนของโหมด ${mode.toUpperCase()}</div><div class="note">เปิด/ปิดแต่ละขั้นตอนได้ตามต้องการ บันทึกอัตโนมัติ</div>`;el.appendChild(h);
 S.tasks.forEach(([id,name,desc])=>{el.appendChild(opt(name,desc,mkSw(S.cfg.presets[mode].includes(id),on=>{
  const l=S.cfg.presets[mode];if(on&&!l.includes(id))l.push(id);if(!on)l.splice(l.indexOf(id),1);
  pywebview.api.save_preset(mode,S.tasks.map(t=>t[0]).filter(x=>l.includes(x)))})))});
 const r=document.createElement("button");r.className="btn";r.textContent="รีเซ็ตโหมดนี้เป็นค่าเริ่มต้น";
 r.onclick=()=>{S.cfg.presets[mode]=[...S.defaults[mode]];pywebview.api.save_preset(mode,S.cfg.presets[mode]);renderTune()};el.appendChild(r)}

function renderSet(){const el=$("set");el.innerHTML="";
 el.insertAdjacentHTML("beforeend",`<div class="sec">สีธีม</div>`);
 const row=document.createElement("div");row.className="sw2";
 COLORS.forEach(c=>{const b=document.createElement("button");b.className="col-sw"+(S.cfg.accent===c?" on":"");b.style.background=c;
  b.onclick=()=>{S.cfg.accent=c;pywebview.api.save("accent",c);setAccent(c);row.querySelectorAll(".col-sw").forEach(x=>x.classList.toggle("on",x===b))};row.appendChild(b)});el.appendChild(row);
 el.appendChild(opt("แอนิเมชัน","ปิดเพื่อประหยัดทรัพยากรเครื่อง",mkSw(S.cfg.anim,on=>{save("anim",on);document.body.classList.toggle("noanim",!on)})));
 el.insertAdjacentHTML("beforeend",`<div class="sec">อัตโนมัติ</div>`);
 el.appendChild(opt("บูสต์เมื่อเปิด FiveM","ทำงานเองหลังเกมเปิด 20 วินาที (ต้องเปิดแอปนี้ค้างไว้)",mkSw(S.cfg.auto,on=>save("auto",on))));
 const sel=document.createElement("select");ORDER.forEach(m=>sel.add(new Option("โหมด "+m.toUpperCase(),m)));sel.value=S.cfg.auto_mode;sel.onchange=()=>save("auto_mode",sel.value);el.appendChild(sel);
 el.insertAdjacentHTML("beforeend",`<div class="sec">แอปเบื้องหลัง</div>`);
 const inp=document.createElement("input");inp.type="text";inp.value=S.cfg.bg_apps.join(", ");inp.placeholder="chrome.exe, spotify.exe";
 inp.onchange=()=>save("bg_apps",inp.value.split(",").map(x=>x.trim()).filter(Boolean));el.appendChild(inp);
 el.appendChild(opt("ปิดแอปแทนการลด priority","ระวัง งานที่ไม่ได้บันทึกอาจหาย",mkSw(S.cfg.kill_bg,on=>save("kill_bg",on))));
 el.insertAdjacentHTML("beforeend",`<div class="sec">ข้อมูล</div><div class="note" id="info"></div>`);
 info();
 const rs=document.createElement("button");rs.className="btn";rs.textContent="คืนค่าเดิมทั้งหมด";rs.onclick=async()=>alert(await pywebview.api.restore());el.appendChild(rs);
 const tb=document.createElement("button");tb.className="btn";tb.textContent="อ่านข้อตกลงอีกครั้ง";tb.onclick=()=>showTos(false);el.appendChild(tb)}
function info(){const c=S.cfg.stats;$("info").innerHTML=`RAM ${S.ram_gb} GB · ${S.cores} เธรด · ${S.admin?"รันแบบ Admin":"ไม่ใช่ Admin (บางขั้นตอนอาจไม่ครบ)"}<br>บูสต์ไปแล้ว ${c.runs} ครั้ง · ล้าง/คืนรวม ${c.freed_mb} MB`}

$("go").onclick=()=>{if(busy)return;busy=true;$("go").disabled=true;$("go").textContent="กำลังบูสต์…";
 $("log").innerHTML="";tab("log");$("orb").classList.add("run");$("sub").textContent="กำลังทำงาน";$("pct").textContent="0";pywebview.api.boost(mode)};
let total=0,done=0;
window.onPlan=s=>{total=s.length;done=0;s.forEach((t,i)=>{const r=document.createElement("div");r.className="row";r.id="r"+i;r.style.animationDelay=i*70+"ms";
 r.innerHTML=`<span class="ico"></span><div><p>${t}</p><small>รอคิว…</small></div>`;$("log").appendChild(r)});if(!s.length)onDone(0,S.cfg.stats)};
window.onStep=(i,st,d)=>{const r=$("r"+i);if(!r)return;r.className="row "+st;r.querySelector("small").textContent=d||"กำลังทำ…";r.scrollIntoView({behavior:"smooth",block:"nearest"})};
window.onDone=(mb,st)=>{S.cfg.stats=st;$("orb").classList.remove("run");$("bar").style.transition="none";$("bar").style.strokeDashoffset=628;
 requestAnimationFrame(()=>requestAnimationFrame(()=>{$("bar").style.transition="";prog(100)}));
 $("sub").textContent=mb>0?`ล้างและคืนพื้นที่ ~${mb} MB`:"เสร็จเรียบร้อย";$("go").disabled=false;$("go").textContent="บูสต์อีกครั้ง";busy=false;if($("info"))info()};
window.onAuto=m=>{busy=true;$("go").disabled=true;setMode(m);$("log").innerHTML="";tab("log");$("orb").classList.add("run");$("sub").textContent="บูสต์อัตโนมัติ"};

function showTos(first){const m=$("tosm"),t=$("tos"),c=$("chk"),sw=$("chksw"),a=$("acc");
 m.classList.add("on");sw.classList.remove("on");a.disabled=true;a.style.display=first?"":"none";$("dec").textContent=first?"ไม่ยอมรับ":"ปิด";
 c.classList.toggle("ok",!first);c.style.display=first?"":"none";t.scrollTop=0;
 t.onscroll=()=>{if(t.scrollTop+t.clientHeight>=t.scrollHeight-6)c.classList.add("ok")};
 sw.onclick=()=>{sw.classList.toggle("on");a.disabled=!sw.classList.contains("on")};
 a.onclick=async()=>{await pywebview.api.tos_accept();m.classList.remove("on")};
 $("dec").onclick=()=>first?pywebview.api.quit():m.classList.remove("on")}

async function tick(){try{const s=await pywebview.api.stats();
 $("mc").style.setProperty("--v",s.cpu+"%");$("vc").textContent=Math.round(s.cpu)+"%";$("mr").style.setProperty("--v",s.ram+"%");$("vr").textContent=Math.round(s.ram)+"%";
 $("badge").classList.toggle("on",s.fivem);$("btxt").textContent=s.fivem?"FiveM กำลังทำงาน":"ยังไม่พบ FiveM"}catch(e){}}

window.addEventListener("pywebviewready",async()=>{
 S=await pywebview.api.get_state();setAccent(S.cfg.accent);document.body.classList.toggle("noanim",!S.cfg.anim);
 setMode(S.cfg.mode);renderTune();renderSet();
 $("rec").textContent=`แนะนำสำหรับเครื่องนี้ (RAM ${S.ram_gb} GB): ${S.rec.toUpperCase()}`;
 if(!S.tos_ok)showTos(true);tick();setInterval(tick,1500)});
</script></body></html>
"""


def main():
    w = webview.create_window("FiveM Booster", html=HTML, js_api=API, width=1000, height=700,
                              min_size=(900, 640), background_color="#FFFFFF")
    API._window = w
    threading.Thread(target=API.watcher, daemon=True).start()
    webview.start()


if __name__ == "__main__":
    main()