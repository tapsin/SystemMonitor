import psutil
for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        if proc.info['name'] == 'python.exe' and 'SystemMonitor' in str(proc.info['cmdline']):
            print(f'PID: {proc.info["pid"]}, Cmd: {proc.info["cmdline"]}')
    except:
        pass