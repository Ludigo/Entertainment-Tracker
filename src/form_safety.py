"""Unsaved-change and focused validation helpers for collection forms."""
import tkinter as tk
from modal import ModalFrame
from theme import PANEL, PANEL_ALT, TEXT, MUTED, BORDER
from utils import parse_time
from window_style import install as polish_dialog


def required(label):
    return lambda value: '' if value.strip() else f'Please enter {label}.'


def whole_number(label):
    def check(value):
        try:
            if int(value.strip()) >= 0:return ''
        except ValueError:pass
        return f'{label} must be a non-negative whole number.'
    return check


def duration(label):
    def check(value):
        try:parse_time(value.strip());return ''
        except ValueError:return f'{label} must use H:MM:SS (minutes and seconds 00–59).'
    return check


class SafeFormModal(ModalFrame):
    has_unsaved_changes=None
    close_prompt=None

    def watch(self,fields,variables=()):
        self._form_values=lambda:tuple(field.get() for field in fields)+tuple(variable.get() for variable in variables)
        self._initial_values=self._form_values()
        self.has_unsaved_changes=lambda:self._form_values()!=self._initial_values

    def close_saved(self):
        super().destroy()

    def destroy(self):
        if self._closed:return
        if self.has_unsaved_changes is None or not self.has_unsaved_changes():
            super().destroy();return
        if self.close_prompt is not None:
            self.close_prompt.lift();return
        confirmation=tk.Toplevel(self);self.close_prompt=confirmation
        polish_dialog(confirmation)
        confirmation.title('Unsaved Changes');confirmation.geometry('430x210')
        confirmation.configure(bg=PANEL);confirmation.transient(self.host)
        tk.Label(confirmation,text='Discard unsaved changes?',bg=PANEL,fg=TEXT,
                 font=('Arial',14,'bold')).pack(anchor='w',padx=20,pady=(20,10))
        tk.Label(confirmation,text='Your edits have not been saved. Keep editing or discard them.',
                 bg=PANEL,fg=MUTED,wraplength=390,justify='left').pack(anchor='w',padx=20)
        def keep(event=None):
            confirmation.destroy();self.close_prompt=None
            self.grab_set();self.focus_set()
            return 'break'
        def discard():
            confirmation.destroy();self.close_prompt=None;self.close_saved()
        actions=tk.Frame(confirmation,bg=PANEL);actions.pack(side='bottom',fill='x',padx=20,pady=20)
        keep_button=tk.Button(actions,text='Keep Editing',command=keep,bg=self.accent,fg='white',relief='flat',padx=12,pady=8)
        keep_button.pack(side='right')
        tk.Button(actions,text='Discard Changes',command=discard,bg=PANEL_ALT,fg=TEXT,
                  relief='flat',padx=12,pady=8).pack(side='right',padx=(0,8))
        confirmation.protocol('WM_DELETE_WINDOW',keep);confirmation.bind('<Escape>',keep)
        confirmation.grab_set();keep_button.focus_set()


class FormValidation:
    def __init__(self,status,checks,cross_check=None):
        self.status=status;self.checks=checks;self.cross_check=cross_check
        self.last_error=None
        for field,validator in checks:
            field.bind('<FocusOut>',lambda event,w=field:self.check_field(w),add='+')
            field.bind('<KeyRelease>',lambda event,w=field:self.clear_field(w),add='+')

    def clear_field(self,field):
        field.configure(highlightbackground=BORDER,highlightthickness=1)
        if self.last_error is field:
            self.status.configure(text='');self.last_error=None

    def mark_error(self,field,message,focus=False):
        field.configure(highlightbackground='#d96a76',highlightthickness=2)
        self.status.configure(text=message,fg='#d96a76',wraplength=360)
        self.last_error=field
        if focus:field.focus_set()

    def check_field(self,field):
        validator=next(check for widget,check in self.checks if widget is field)
        message=validator(field.get())
        if message:self.mark_error(field,message)
        else:self.clear_field(field)

    def validate(self):
        for field,validator in self.checks:
            message=validator(field.get())
            if message:self.mark_error(field,message,True);return False
            self.clear_field(field)
        if self.cross_check:
            problem=self.cross_check()
            if problem:
                self.mark_error(problem[0],problem[1],True);return False
        self.status.configure(text='');return True
