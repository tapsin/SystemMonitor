import winreg
key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run', 0, winreg.KEY_SET_VALUE)
winreg.SetValueEx(key, 'SystemMonitor', 0, winreg.REG_SZ, r'"C:\Users\tapsin\Desktop\SystemMonitor.exe"')
winreg.CloseKey(key)
print('Startup updated to .exe')