import webview
import psutil
import threading
import time
import os

# รายชื่อคำและโปรแกรมที่เข้าข่ายโกงหรือเครื่องมือแฮกทั่วไป (สามารถเพิ่มลดได้ตามต้องการ)
SUSPICIOUS_KEYWORDS = [
    "cheatengine", "processhacker", "xenos", "injector", "extreme injector",
    "ghost", "nexus", "skiptrace", "modmenu", "lua injector", "loader",
    "kiero", "d3dcompiler", "custom_script", "executor", "skinchanger"
]

class SecurityScannerAPI:
    def scan_system(self):
        results = {
            "processes": [],
            "powershell": [],
            "status": "clean"
        }
        
        # 1. ตรวจสอบ Running Processes ทั้งหมดในเครื่อง
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                pinfo = proc.info
                name = (pinfo['name'] or "").lower()
                cmdline = " ".join(pinfo['cmdline'] or []).lower()
                
                # เช็คชื่อ Process กับคีย์เวิร์ดโปรแกรมโกง
                for kw in SUSPICIOUS_KEYWORDS:
                    if kw in name or kw in cmdline:
                        results["processes"].append({
                            "pid": pinfo['pid'],
                            "name": pinfo['name'],
                            "detail": f"พบโปรแกรมหรือคีย์เวิร์ดต้องสงสัย: {kw}"
                        })
                        results["status"] = "warning"
                        break
                        
                # 2. ตรวจสอบ PowerShell หรือกระบวนการรันคำสั่งที่ซ่อนตัว / รันไฟล์แปลกๆ
                if "powershell" in name or "pwsh" in name or "cmd" in name:
                    if any(flag in cmdline for flag in ["-encodedcommand", "-e ", "iex", "downloadstring", "bypass", "-hidden"]):
                        results["powershell"].append({
                            "pid": pinfo['pid'],
                            "cmd": cmdline[:120] + "..." if len(cmdline) > 120 else cmdline,
                            "detail": "ตรวจพบการรันคำสั่ง PowerShell ที่ซ่อนเร้นหรือดาวน์โหลดสคริปต์ภายนอก"
                        })
                        results["status"] = "warning"
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
                
        return results

# หน้าตา UI (HTML / Tailwind CSS / Animations)
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <title>FiveM Security Guard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Prompt', sans-serif; }
        @keyframes float {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-6px); }
        }
        .animate-float { animation: float 3s ease-in-out infinite; }
    </style>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen flex flex-col justify-between selection:bg-blue-500 selection:text-white">
    
    <!-- Header -->
    <header class="bg-white border-b border-slate-200 px-8 py-4 flex items-center justify-between shadow-xs">
        <div class="flex items-center space-x-3">
            <div class="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center text-white font-bold text-lg shadow-md shadow-blue-200">
                🛡️
            </div>
            <div>
                <h1 class="text-lg font-bold text-slate-900">FiveM Security Guard</h1>
                <p class="text-xs text-slate-400">ระบบตรวจสอบโปรแกรมโกงและสคริปต์แปลกปลอม</p>
            </div>
        </div>
        <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
            <span class="w-2 h-2 mr-1.5 bg-emerald-500 rounded-full animate-ping"></span> ระบบพร้อมสแกน
        </span>
    </header>

    <!-- Main Content -->
    <main class="max-w-3xl w-full mx-auto p-8 flex-1 flex flex-col items-center justify-center">
        
        <!-- Welcome View -->
        <div id="welcome-view" class="text-center space-y-6">
            <div class="w-24 h-24 bg-blue-50 rounded-3xl mx-auto flex items-center justify-center text-4xl shadow-sm border border-blue-100 animate-float">
                🔍
            </div>
            <div class="space-y-2">
                <h2 class="text-2xl font-bold text-slate-800">ตรวจสอบความปลอดภัยเครื่องของคุณ</h2>
                <p class="text-slate-500 max-w-md mx-auto text-sm leading-relaxed">
                    ระบบจะทำการวิเคราะห์ Process ที่กำลังทำงานอยู่, ตรวจสอบ PowerShell คำสั่งต้องสงสัย และโปรแกรมโกง FiveM ยอดฮิตทั้งหมด
                </p>
            </div>
            <button onclick="startScan()" class="px-8 py-3.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-2xl shadow-lg shadow-blue-200 transition-all duration-200 transform hover:-translate-y-0.5 active:translate-y-0 flex items-center space-x-2 mx-auto">
                <span>เริ่มตรวจสอบระบบ</span>
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>
            </button>
        </div>

        <!-- Scanning View -->
        <div id="scanning-view" class="hidden text-center space-y-6">
            <div class="relative w-28 h-28 mx-auto flex items-center justify-center">
                <div class="absolute inset-0 border-4 border-blue-100 rounded-full animate-ping"></div>
                <div class="absolute inset-0 border-4 border-t-blue-600 border-r-transparent border-b-transparent border-l-transparent rounded-full animate-spin"></div>
                <span class="text-2xl">⚡</span>
            </div>
            <div class="space-y-2">
                <h2 class="text-xl font-bold text-slate-800" id="scan-status-text">กำลังเจาะลึกตรวจสอบ Process...</h2>
                <p class="text-slate-400 text-xs">กรุณารอสักครู่ ระบบกำลังประมวลผลข้อมูลความปลอดภัย</p>
            </div>
        </div>

        <!-- Results View -->
        <div id="results-view" class="hidden w-full space-y-6">
            <div id="result-badge" class="p-6 rounded-2xl border flex items-center justify-between shadow-xs">
                <div class="flex items-center space-x-4">
                    <div id="result-icon" class="w-12 h-12 rounded-xl flex items-center justify-center text-2xl"></div>
                    <div>
                        <h3 id="result-title" class="text-base font-bold"></h3>
                        <p id="result-subtitle" class="text-xs opacity-80 mt-0.5"></p>
                    </div>
                </div>
                <button onclick="resetScan()" class="px-4 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-semibold rounded-xl shadow-xs transition-all">
                    สแกนอีกครั้ง
                </button>
            </div>

            <div class="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-4">
                <h4 class="font-semibold text-slate-700 text-sm flex items-center space-x-2">
                    <span>📋</span> <span>ผลการตรวจสอบรายละเอียด</span>
                </h4>
                <div id="result-details" class="space-y-3 max-h-80 overflow-y-auto pr-2"></div>
            </div>
        </div>

    </main>

    <!-- Footer -->
    <footer class="bg-white border-t border-slate-200 py-3 px-8 text-center text-xs text-slate-400">
        FiveM Security Guard Engine • Python pywebview UI
    </footer>

    <script>
        function startScan() {
            document.getElementById('welcome-view').classList.add('hidden');
            document.getElementById('scanning-view').classList.remove('hidden');

            setTimeout(() => {
                document.getElementById('scan-status-text').innerText = 'กำลังตรวจสอบสคริปต์ PowerShell และคำสั่งแปลกปลอม...';
            }, 1200);

            setTimeout(async () => {
                const data = await window.pywebview.api.scan_system();
                renderResults(data);
            }, 2500);
        }

        function resetScan() {
            document.getElementById('results-view').classList.add('hidden');
            document.getElementById('welcome-view').classList.remove('hidden');
        }

        function renderResults(data) {
            document.getElementById('scanning-view').classList.add('hidden');
            document.getElementById('results-view').classList.remove('hidden');

            const badge = document.getElementById('result-badge');
            const icon = document.getElementById('result-icon');
            const title = document.getElementById('result-title');
            const subtitle = document.getElementById('result-subtitle');
            const detailsContainer = document.getElementById('result-details');
            
            detailsContainer.innerHTML = '';
            const totalIssues = data.processes.length + data.powershell.length;

            if (totalIssues === 0) {
                badge.className = "p-6 rounded-2xl border border-emerald-200 bg-emerald-50/60 flex items-center justify-between shadow-xs text-emerald-900";
                icon.className = "w-12 h-12 rounded-xl bg-emerald-500 text-white flex items-center justify-center text-xl shadow-md shadow-emerald-200";
                icon.innerHTML = "✅";
                title.innerText = "ไม่พบโปรแกรมโกงหรือความผิดปกติใดๆ";
                subtitle.innerText = "ระบบของคุณสะอาดและปลอดภัย พร้อมเข้าเล่นเกม";
                detailsContainer.innerHTML = '<div class="text-center py-8 text-slate-400 text-sm">ยอดเยี่ยม! ไม่พบ Process หรือ PowerShell ที่น่าสงสัยรันอยู่บนเครื่อง</div>';
            } else {
                badge.className = "p-6 rounded-2xl border border-rose-200 bg-rose-50/60 flex items-center justify-between shadow-xs text-rose-900";
                icon.className = "w-12 h-12 rounded-xl bg-rose-500 text-white flex items-center justify-center text-xl shadow-md shadow-rose-200";
                icon.innerHTML = "⚠️";
                title.innerText = `ตรวจพบความผิดปกติ (${totalIssues} รายการ)`;
                subtitle.innerText = "พบโปรแกรมหรือคำสั่งที่เข้าข่ายการโกงหรือเป็นอันตราย";

                data.processes.forEach(p => {
                    detailsContainer.innerHTML += `
                        <div class="p-4 rounded-xl bg-rose-50/50 border border-rose-100 flex items-start justify-between">
                            <div>
                                <div class="font-semibold text-rose-900 text-sm">${p.name} <span class="text-xs text-rose-500 font-normal">(PID: ${p.pid})</span></div>
                                <div class="text-xs text-rose-600 mt-0.5">${p.detail}</div>
                            </div>
                            <span class="px-2.5 py-1 bg-rose-200/60 text-rose-800 text-xs font-medium rounded-lg">Process</span>
                        </div>
                    `;
                });

                data.powershell.forEach(ps => {
                    detailsContainer.innerHTML += `
                        <div class="p-4 rounded-xl bg-amber-50/50 border border-amber-100 flex items-start justify-between">
                            <div>
                                <div class="font-semibold text-amber-900 text-sm">PowerShell Script <span class="text-xs text-amber-600 font-normal">(PID: ${ps.pid})</span></div>
                                <div class="text-xs text-slate-700 mt-1 font-mono bg-white p-2 rounded border border-amber-200 break-all">${ps.cmd}</div>
                            </div>
                            <span class="px-2.5 py-1 bg-amber-200/60 text-amber-800 text-xs font-medium rounded-lg">PowerShell</span>
                        </div>
                    `;
                });
            }
        }
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    api = SecurityScannerAPI()
    # สร้างหน้าต่าง pywebview ธีมสีขาว ขนาดกำลังพอดี ปรับแต่งสวยงาม
    window = webview.create_window(
        'FiveM Security Guard - ตัวตรวจสอบโปรแกรมโกง',
        html=HTML_CONTENT,
        js_api=api,
        width=850,
        height=600,
        resizable=False,
        min_size=(800, 550)
    )
    webview.start(debug=False)
