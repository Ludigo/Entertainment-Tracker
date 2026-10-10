"""Consistent positioning on the application's current display."""
import os
import tkinter as tk


def centred_coordinates(width, height, bounds):
    left, top, right, bottom = bounds
    return left + max(0, (right-left-width)//2), top + max(0, (bottom-top-height)//2)


def screen_bounds(window):
    """Use the active monitor's usable area, including negative monitor origins."""
    if os.name == 'nt':
        try:
            import ctypes
            from ctypes import wintypes
            class MonitorInfo(ctypes.Structure):
                _fields_ = [('cbSize',wintypes.DWORD),('rcMonitor',wintypes.RECT),
                            ('rcWork',wintypes.RECT),('dwFlags',wintypes.DWORD)]
            api=ctypes.windll.user32
            api.MonitorFromWindow.argtypes=[wintypes.HWND,wintypes.DWORD]
            api.MonitorFromWindow.restype=wintypes.HANDLE
            api.GetMonitorInfoW.argtypes=[wintypes.HANDLE,ctypes.POINTER(MonitorInfo)]
            api.GetMonitorInfoW.restype=wintypes.BOOL
            owner=window.master.winfo_toplevel() if window.master is not None else window
            monitor=api.MonitorFromWindow(owner.winfo_id(),2)
            info=MonitorInfo();info.cbSize=ctypes.sizeof(info)
            if api.GetMonitorInfoW(monitor,ctypes.byref(info)):
                area=info.rcWork
                return area.left,area.top,area.right,area.bottom
        except (OSError,AttributeError,tk.TclError):
            pass
    return 0,0,window.winfo_screenwidth(),window.winfo_screenheight()


def centre_window(window):
    try:
        if not window.winfo_exists() or window.state()!='normal':return
        width=max(window.winfo_width(),window.winfo_reqwidth())
        height=max(window.winfo_height(),window.winfo_reqheight())
        # Tk geometry retains explicit requested sizes/minimums after layout.
        size=window.geometry().split('+')[0].split('-')[0]
        if 'x' in size:
            w,h=size.split('x');width=max(width,int(w));height=max(height,int(h))
        x,y=centred_coordinates(width,height,screen_bounds(window))
        if os.name=='nt':
            # Native coordinates avoid Tk's right/bottom-relative negative offsets.
            import ctypes
            from ctypes import wintypes
            api=ctypes.windll.user32
            api.GetParent.argtypes=[wintypes.HWND];api.GetParent.restype=wintypes.HWND
            api.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
            api.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,
                                      ctypes.c_int,ctypes.c_int,wintypes.UINT]
            handle=api.GetParent(window.winfo_id()) or window.winfo_id()
            rectangle=wintypes.RECT()
            if api.GetWindowRect(handle,ctypes.byref(rectangle)):
                x,y=centred_coordinates(rectangle.right-rectangle.left,
                                        rectangle.bottom-rectangle.top,screen_bounds(window))
                api.SetWindowPos(handle,None,x,y,0,0,0x0001|0x0004|0x0010)
                return
        window.geometry(f'{width}x{height}{x:+d}{y:+d}')
    except (tk.TclError,ValueError,OSError,AttributeError):pass


def centre_modal(modal):
    try:
        if modal._closed:return
        left,top,right,bottom=screen_bounds(modal.host)
        # The overlay is clipped to its host; keep the entire card reachable.
        x=(left+right)//2-modal.host.winfo_rootx()
        y=(top+bottom)//2-modal.host.winfo_rooty()
        width=modal.host.winfo_width();height=modal.host.winfo_height()
        x=max(modal._width//2,min(x,width-modal._width//2))
        y=max(modal._height//2,min(y,height-modal._height//2))
        modal.place_configure(relx=0,rely=0,x=x,y=y,anchor='center')
    except tk.TclError:pass


def install(root):
    """Centre each Tk secondary window once, after its initial layout."""
    def mapped(event):
        window=event.widget
        if not isinstance(window,tk.Toplevel) or getattr(window,'_et_centred',False):return
        window._et_centred=True
        window.after_idle(lambda:centre_window(window))
    root.bind_all('<Map>',mapped,add='+')


def maximise_main(window):
    try:window.state('zoomed')
    except tk.TclError:
        try:window.attributes('-zoomed',True)
        except tk.TclError:pass
