# -*- coding: utf-8 -*-
"""System Monitor - Masaüstü Widget for Windows 11 (Desktop Level)"""

import ctypes
import ctypes.wintypes
import sys
import threading
import time
from datetime import datetime
from tkinter import *
from tkinter import ttk
import psutil

# Windows API constants
GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_CHILD = 0x40000000
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_CLIPCHILDREN = 0x02000000
WS_CLIPSIBLINGS = 0x04000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
HWND_BOTTOM = 1
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_NOZORDER = 0x0004
LWA_ALPHA = 0x00000002
WM_WINDOWPOSCHANGING = 0x0046
WM_SHOWWINDOW = 0x0018

# Get desktop window handle
user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32

# Find the correct WorkerW (desktop icons container)
def get_desktop_workerw():
    """Get the WorkerW window that contains SHELLDLL_DefView (desktop icons)."""
    progman = user32.FindWindowW("Progman", None)
    if progman:
        # Send message to spawn WorkerW
        user32.SendMessageTimeoutW(progman, 0x052C, 0, 0, 0, 1000, None)
    
    # Enumerate windows to find WorkerW with SHELLDLL_DefView
    def enum_windows(hwnd, lparam):
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        if cls.value == "WorkerW":
            # Check if this WorkerW has SHELLDLL_DefView child
            defview = user32.FindWindowExW(hwnd, 0, "SHELLDLL_DefView", None)
            if defview:
                # Found the desktop icons container
                ctypes.cast(lparam, ctypes.POINTER(ctypes.c_void_p)).contents.value = hwnd
                return False
        return True
    
    result = ctypes.c_void_p(0)
    enum_func = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(enum_windows)
    user32.EnumWindows(enum_func, ctypes.byref(result))
    
    return result.value if result.value else progman


class SystemMonitorApp(Tk):
    def __init__(self):
        super().__init__()
        
        # Window attributes - no title bar
        self.overrideredirect(True)
        
        # Dark theme colors
        self.bg_color = '#1e1e1e'
        self.fg_color = '#ffffff'
        self.accent_cpu = '#ff6b6b'
        self.accent_mem = '#4ecdc4'
        self.accent_net = '#ffe66d'
        self.btn_bg = '#3a3a3a'
        self.btn_fg = '#ffffff'
        self.semicolor = '#3d3d3d'
        self.locked_color = '#27ae60'
        self.unlocked_color = '#e74c3c'
        
        self.configure(bg=self.bg_color)
        
        # Monitor size
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        
        # Position: right-top corner (20px margin)
        widget_w, widget_h = 340, 420
        self.geometry(f"{widget_w}x{widget_h}+{screen_w - widget_w - 20}+{20}")
        
        # State variables
        self.cpu_val = StringVar(value="CPU --%")
        self.mem_val = StringVar(value="MEM --%")
        self.net_up_val = StringVar(value="↑ 0 KB/s")
        self.net_down_val = StringVar(value="↓ 0 KB/s")
        self.selected_tab = StringVar(value="cpu")
        self.processes_cpu = []
        self.processes_mem = []
        self.last_net_io = None
        self.last_time = None
        
        # Position lock state
        self.position_locked = True  # Start locked
        self.drag_data = {"x": 0, "y": 0}
        
        self._build_ui()
        self._bind_events()
        
        # Apply desktop-level parenting after window is realized
        self.after(200, self._setup_desktop_level)
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def _setup_desktop_level(self):
        """Set window as desktop-level widget (child of WorkerW, stays on desktop)."""
        try:
            hwnd = self.winfo_id()
            
            # Get current styles
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            
            # Remove WS_POPUP and WS_EX_TOOLWINDOW, add WS_CHILD
            new_style = (style & ~WS_POPUP) | WS_CHILD | WS_VISIBLE | WS_CLIPCHILDREN | WS_CLIPSIBLINGS
            user32.SetWindowLongW(hwnd, GWL_STYLE, new_style)
            
            # Extended styles: layered, noactivate, transparent for clicks on titlebar area
            new_ex_style = (ex_style & ~WS_EX_TOOLWINDOW) | WS_EX_LAYERED | WS_EX_NOACTIVATE
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_ex_style)
            
            # Set transparency (0-255, 235 = ~92% opaque)
            user32.SetLayeredWindowAttributes(hwnd, 0, 235, LWA_ALPHA)
            
            # Parent to desktop WorkerW (icons container)
            desktop_parent = get_desktop_workerw()
            if desktop_parent:
                user32.SetParent(hwnd, desktop_parent)
                print(f"Parented to WorkerW: {desktop_parent}")
            
            # Position at top-right of desktop
            self._position_at_desktop_corner()
            
            # Ensure it stays visible and at correct Z-order
            self.after(500, self._ensure_desktop_position)
            
        except Exception as e:
            print(f"Desktop level setup error: {e}")
    
    def _position_at_desktop_corner(self):
        """Position widget at top-right of desktop work area."""
        try:
            hwnd = self.winfo_id()
            # Get work area (excludes taskbar)
            rect = ctypes.wintypes.RECT()
            user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)  # SPI_GETWORKAREA
            
            widget_w = 340
            widget_h = 420
            x = rect.right - widget_w - 20
            y = rect.top + 20
            
            user32.SetWindowPos(hwnd, HWND_TOPMOST, x, y, widget_w, widget_h,
                              SWP_NOACTIVATE | SWP_SHOWWINDOW)
        except Exception as e:
            print(f"Position error: {e}")
    
    def _ensure_desktop_position(self):
        """Periodically ensure widget stays on desktop and visible."""
        try:
            hwnd = self.winfo_id()
            if not user32.IsWindowVisible(hwnd):
                user32.ShowWindow(hwnd, 5)  # SW_SHOW
            
            # Re-parent if needed (e.g., after explorer restart)
            parent = user32.GetParent(hwnd)
            desktop_parent = get_desktop_workerw()
            if desktop_parent and parent != desktop_parent:
                user32.SetParent(hwnd, desktop_parent)
                self._position_at_desktop_corner()
            
            # Keep at top of desktop layer (but behind fullscreen apps)
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                              SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        except:
            pass
        if self.winfo_exists():
            self.after(2000, self._ensure_desktop_position)
    
    def _build_ui(self):
        """Build the UI components."""
        # Main frame with padding
        main_frame = Frame(self, bg=self.bg_color)
        main_frame.pack(fill=BOTH, expand=YES, padx=8, pady=8)
        
        # Title bar (draggable area when unlocked)
        title_bar = Frame(main_frame, bg='#2d2d2d', height=32)
        title_bar.pack(fill=X)
        title_bar.pack_propagate(False)
        
        title_label = Label(title_bar, text="⚡ SYSTEM MONITOR", 
                           fg=self.fg_color, bg='#2d2d2d', font=('Segoe UI', 9, 'bold'))
        title_label.pack(side=LEFT, padx=10, pady=6)
        
        # Lock/Unlock button
        self.lock_btn = Button(title_bar, text="🔒", fg=self.fg_color, bg=self.locked_color,
                              font=('Segoe UI', 10), width=2, height=1,
                              relief=FLAT, cursor='hand2', command=self._toggle_lock)
        self.lock_btn.pack(side=RIGHT, padx=4, pady=4)
        
        # Close button
        close_btn = Button(title_bar, text="✕", fg=self.fg_color, bg='#c0392b',
                          font=('Segoe UI', 9, 'bold'), width=2, height=1,
                          relief=FLAT, cursor='hand2', command=self.destroy)
        close_btn.pack(side=RIGHT, padx=8, pady=4)
        
        # Stats row - CPU
        cpu_frame = Frame(main_frame, bg=self.bg_color)
        cpu_frame.pack(fill=X, pady=(6, 2))
        
        cpu_bar_frame = Frame(cpu_frame, bg=self.bg_color)
        cpu_bar_frame.pack(side=LEFT, fill=X, expand=True)
        
        self.cpu_label = Label(cpu_bar_frame, textvariable=self.cpu_val,
                              fg=self.accent_cpu, bg=self.bg_color,
                              font=('Segoe UI', 11, 'bold'))
        self.cpu_label.pack(side=LEFT)
        
        self.cpu_bar = ttk.Progressbar(cpu_bar_frame, orient=HORIZONTAL,
                                  length=180, mode='determinate',
                                  maximum=100, value=0,
                                  takefocus=0)
        self.cpu_bar['value'] = 0
        self.cpu_bar.pack(side=RIGHT, fill=X, expand=True, padx=(8, 0), pady=3)
        self.cpu_bar_style = ttk.Style()
        self.cpu_bar_style.theme_use('clam')
        self.cpu_bar.configure(style='red.Horizontal.TProgressbar')
        self.cpu_bar_style.configure('red.Horizontal.TProgressbar',
                                    troughcolor='#2d2d2d',
                                    background=self.accent_cpu,
                                    thickness=8)
        
        # Stats row - MEM
        mem_frame = Frame(main_frame, bg=self.bg_color)
        mem_frame.pack(fill=X, pady=(2, 6))
        
        mem_bar_frame = Frame(mem_frame, bg=self.bg_color)
        mem_bar_frame.pack(side=LEFT, fill=X, expand=True)
        
        self.mem_label = Label(mem_bar_frame, textvariable=self.mem_val,
                              fg=self.accent_mem, bg=self.bg_color,
                              font=('Segoe UI', 11, 'bold'))
        self.mem_label.pack(side=LEFT)
        
        self.mem_bar = ttk.Progressbar(mem_bar_frame, orient=HORIZONTAL,
                                  length=180, mode='determinate',
                                  maximum=100, value=0)
        self.mem_bar.pack(side=RIGHT, fill=X, expand=True, padx=(8, 0), pady=3)
        self.mem_bar.configure(style='teal.Horizontal.TProgressbar')
        self.cpu_bar_style.configure('teal.Horizontal.TProgressbar',
                                    troughcolor='#2d2d2d',
                                    background=self.accent_mem,
                                    thickness=8)
        
        # Network stats
        net_frame = Frame(main_frame, bg=self.bg_color)
        net_frame.pack(fill=X, pady=(2, 6))
        
        self.net_label = Label(net_frame, textvariable=self.net_down_val,
                              fg=self.accent_net, bg=self.bg_color,
                              font=('Segoe UI', 10))
        self.net_label.pack(side=LEFT)
        
        self.net_up_label = Label(net_frame, textvariable=self.net_up_val,
                                 fg='#aaa', bg=self.bg_color,
                                 font=('Segoe UI', 9))
        self.net_up_label.pack(side=RIGHT)
        
        # Separator
        sep = Frame(main_frame, height=2, bg=self.semicolor)
        sep.pack(fill=X, pady=6)
        
        # Tab buttons
        tab_frame = Frame(main_frame, bg=self.bg_color)
        tab_frame.pack(fill=X, pady=(0, 6))
        
        self.cpu_tab = Button(tab_frame, text="📊 CPU", fg=self.fg_color,
                        bg=self.btn_bg if self.selected_tab.get() == 'cpu' else '#2d2d2d',
                        activebackground=self.accent_cpu, activeforeground=self.bg_color,
                        font=('Segoe UI', 9), width=10, height=2, relief=FLAT,
                        cursor='hand2', command=lambda: self._switch_tab('cpu'))
        self.cpu_tab.pack(side=LEFT, padx=(0, 3))
        
        self.mem_tab = Button(tab_frame, text="💾 Memory", fg=self.fg_color,
                        bg=self.btn_bg if self.selected_tab.get() == 'mem' else '#2d2d2d',
                        activebackground=self.accent_mem, activeforeground=self.bg_color,
                        font=('Segoe UI', 9), width=10, height=2, relief=FLAT,
                        cursor='hand2', command=lambda: self._switch_tab('mem'))
        self.mem_tab.pack(side=LEFT, padx=(3, 0))
        
        # Scrollable process list
        list_container = Frame(main_frame, bg=self.bg_color,
                              highlightthickness=1, highlightbackground=self.semicolor)
        list_container.pack(fill=BOTH, expand=True)
        
        self.list_canvas = Canvas(list_container, bg=self.bg_color,
                                 highlightthickness=0)
        scrollbar = Scrollbar(list_container, orient=VERTICAL,
                             bg='#2d2d2d', activebackground=self.accent_cpu,
                             command=self.list_canvas.yview)
        self.list_scroll = Frame(self.list_canvas, bg=self.bg_color)
        
        self.list_canvas.configure(yscrollcommand=scrollbar.set)
        self.list_canvas.create_window((0, 0), window=self.list_scroll,
                                      anchor='nw')
        
        self.list_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        # Bind canvas events for scrolling
        self.list_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.list_canvas.bind("<Configure>", self._on_canvas_configure)
        
        # Initial process list
        self._update_process_list()
        self._update_lock_button()
    
    def _toggle_lock(self):
        """Toggle position lock."""
        self.position_locked = not self.position_locked
        self._update_lock_button()
    
    def _update_lock_button(self):
        """Update lock button appearance."""
        if self.position_locked:
            self.lock_btn.configure(text="🔒", bg=self.locked_color)
        else:
            self.lock_btn.configure(text="🔓", bg=self.unlocked_color)
    
    def _switch_tab(self, tab_name):
        self.selected_tab.set(tab_name)
        self._update_process_list()
        self.after(10, self._refresh_tabs)
    
    def _refresh_tabs(self):
        """Update tab button colors after selection changes."""
        try:
            main_frame = self.winfo_children()[0]
            for child in main_frame.winfo_children():
                if isinstance(child, Frame):
                    for w in child.winfo_children():
                        if isinstance(w, Button) and w.cget('text') in ('📊 CPU', '💾 Memory'):
                            target_tab = 'cpu' if 'CPU' in w.cget('text') else 'mem'
                            w.configure(bg=self.btn_bg if self.selected_tab.get() == target_tab else '#2d2d2d')
        except:
            pass
    
    def _on_mousewheel(self, event):
        if self.winfo_exists():
            self.list_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def _on_canvas_configure(self, event):
        if self.winfo_exists():
            self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all"))
    
    def _update_process_list(self):
        """Clear and rebuild the process list."""
        # Clear existing
        for widget in self.list_scroll.winfo_children():
            widget.destroy()
        
        if self.selected_tab.get() == 'cpu':
            processes = sorted(self.processes_cpu, key=lambda x: x[0], reverse=True)[:5]
        else:
            processes = sorted(self.processes_mem, key=lambda x: x[1], reverse=True)[:5]
        
        if not processes:
            empty = Label(self.list_scroll, text="Veri toplanıyor...",
                         fg='#888', bg=self.bg_color, font=('Segoe UI', 9))
            empty.pack(pady=20)
            return
        
        for proc_name, cpu_pct, mem_pct in processes:
            proc_frame = Frame(self.list_scroll, bg=self.bg_color)
            proc_frame.pack(fill=X, pady=2)
            
            name_label = Label(proc_frame, text=proc_name[:20],
                             fg=self.fg_color, bg=self.bg_color,
                             font=('Segoe UI', 9), anchor=W)
            name_label.pack(side=LEFT, padx=(5, 0), fill=X, expand=True)
            
            stats = f"CPU:{cpu_pct:.1f}% | MEM:{mem_pct:.1f}%"
            stats_label = Label(proc_frame, text=stats,
                              fg='#aaa', bg=self.bg_color,
                              font=('Segoe UI', 8))
            stats_label.pack(side=LEFT, padx=5)
            
            kill_btn = Button(proc_frame, text="KILL", fg='white',
                            bg='#c0392b', font=('Segoe UI', 8, 'bold'),
                            width=5, relief=FLAT, cursor='hand2',
                            command=lambda n=proc_name: self._kill_process(n))
            kill_btn.pack(side=RIGHT, padx=5)
    
    def _kill_process(self, name):
        """Kill a process by name."""
        try:
            killed = False
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    pname = proc.info['name']
                    if pname and pname.lower() == name.lower():
                        proc.kill()
                        killed = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            if killed:
                self._update_process_list()
        except Exception as e:
            pass
    
    def _bind_events(self):
        """Bind drag events to title bar."""
        title_bar = self.winfo_children()[0].winfo_children()[0]  # main_frame -> title_bar
        title_bar.bind('<Button-1>', self._drag_start)
        title_bar.bind('<B1-Motion>', self._drag)
        title_bar.bind('<ButtonRelease-1>', self._drag_end)
    
    def _drag_start(self, event):
        if not self.position_locked:
            # Get cursor position (screen coordinates)
            pt = ctypes.wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            self.drag_data["cursor_x"] = pt.x
            self.drag_data["cursor_y"] = pt.y
            # Get parent window (WorkerW)
            self.drag_data["parent_hwnd"] = user32.GetParent(self.winfo_id())
            # Get current window position in parent's client coordinates
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(self.winfo_id(), ctypes.byref(rect))
            # Convert to parent client coordinates
            if self.drag_data["parent_hwnd"]:
                pt_parent = ctypes.wintypes.POINT(rect.left, rect.top)
                user32.ScreenToClient(self.drag_data["parent_hwnd"], ctypes.byref(pt_parent))
                self.drag_data["win_x"] = pt_parent.x
                self.drag_data["win_y"] = pt_parent.y
            else:
                self.drag_data["win_x"] = rect.left
                self.drag_data["win_y"] = rect.top
    
    def _drag(self, event):
        if not self.position_locked:
            # Get current cursor position (screen coordinates)
            pt = ctypes.wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            cur_x = pt.x
            cur_y = pt.y
            
            # Convert cursor to parent client coordinates
            parent_hwnd = self.drag_data.get("parent_hwnd")
            if parent_hwnd:
                pt_client = ctypes.wintypes.POINT(cur_x, cur_y)
                user32.ScreenToClient(parent_hwnd, ctypes.byref(pt_client))
                cur_x = pt_client.x
                cur_y = pt_client.y
                
                # Convert start cursor to parent client coordinates
                start_pt = ctypes.wintypes.POINT(self.drag_data["cursor_x"], self.drag_data["cursor_y"])
                user32.ScreenToClient(parent_hwnd, ctypes.byref(start_pt))
                start_x = start_pt.x
                start_y = start_pt.y
            else:
                start_x = self.drag_data["cursor_x"]
                start_y = self.drag_data["cursor_y"]
            
            # Calculate delta in parent client coordinates
            deltax = cur_x - start_x
            deltay = cur_y - start_y
            
            # New position in parent client coordinates
            x = self.drag_data["win_x"] + deltax
            y = self.drag_data["win_y"] + deltay
            
            # Constrain to parent client area (work area)
            try:
                if parent_hwnd:
                    parent_rect = ctypes.wintypes.RECT()
                    user32.GetClientRect(parent_hwnd, ctypes.byref(parent_rect))
                    w = self.winfo_width()
                    h = self.winfo_height()
                    x = max(0, min(x, parent_rect.right - w))
                    y = max(0, min(y, parent_rect.bottom - h))
            except:
                pass
            
            # Use SetWindowPos for child window (coordinates are relative to parent)
            hwnd = self.winfo_id()
            user32.SetWindowPos(hwnd, 0, x, y, 0, 0,
                              SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_SHOWWINDOW)
    
    def _drag_end(self, event):
        # Position is already set by SetWindowPos
        pass
    
    def _monitor_loop(self):
        """Background monitoring loop."""
        while True:
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=None)
                
                # Memory
                memory = psutil.virtual_memory()
                mem_percent = memory.percent
                
                # Network
                net_io = psutil.net_io_counters()
                now = time.time()
                
                if self.last_net_io and self.last_time:
                    delta_time = now - self.last_time
                    if delta_time > 0:
                        delta_recv = net_io.bytes_recv - self.last_net_io.bytes_recv
                        delta_sent = net_io.bytes_sent - self.last_net_io.bytes_sent
                        down_speed = delta_recv / delta_time / 1024  # KB/s
                        up_speed = delta_sent / delta_time / 1024    # KB/s
                        
                        self.net_down_val.set(f"↓ {down_speed:.1f} KB/s")
                        self.net_up_val.set(f"↑ {up_speed:.1f} KB/s")
                
                self.last_net_io = net_io
                self.last_time = now
                
                # Update labels
                self.cpu_val.set(f"CPU {cpu_percent}%")
                self.mem_val.set(f"MEM {mem_percent}%")
                
                # Update progress bars
                self.cpu_bar['value'] = cpu_percent
                self.mem_bar['value'] = mem_percent
                
                # Update process lists (every few seconds to save resources)
                if int(now) % 3 == 0:  # Every ~3 seconds
                    self.processes_cpu = []
                    self.processes_mem = []
                    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
                        try:
                            if proc.info['name']:
                                self.processes_cpu.append((
                                    proc.info['name'],
                                    proc.info['cpu_percent'] or 0,
                                    proc.info['memory_info'].rss / 1024 / 1024  # MB
                                ))
                                self.processes_mem.append((
                                    proc.info['name'],
                                    proc.info['cpu_percent'] or 0,
                                    proc.info['memory_info'].rss / 1024 / 1024
                                ))
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                    
                    self._update_process_list()
                    self.after(0, self._refresh_tabs)
                
                # Force canvas update
                if hasattr(self, 'list_canvas') and self.winfo_exists():
                    try:
                        self.list_canvas.update_idletasks()
                    except:
                        pass
                        
            except Exception as e:
                pass
            
            time.sleep(1)


def main():
    app = SystemMonitorApp()
    app.mainloop()


if __name__ == "__main__":
    main()