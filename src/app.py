#!/usr/bin/env python3
"""Nono LLM — GNOME-App zur Steuerung des nono-sandboxed Ollama-Servers + Chat-UI."""
import json
import re
import subprocess
import threading
import urllib.request

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

APP_ID = "de.muellermax.NonoLLM"
OLLAMA_URL = "http://127.0.0.1:11434"
MODEL = "gemma2:9b"

START_CMD = (
    "cd {workdir} && {nono} run --detached --allow-cwd "
    "--allow ~/.ollama -- /home/linuxbrew/.linuxbrew/bin/ollama serve"
).format(workdir="~/llm-chat", nono="/home/linuxbrew/.linuxbrew/bin/nono")

NONO_BIN = "/home/linuxbrew/.linuxbrew/bin/nono"


def run_host(cmd: str, timeout: int = 60) -> tuple:
    """Befehl auf dem HOST ausführen (im Flatpak via flatpak-spawn --host)."""
    try:
        p = subprocess.run(
            ["flatpak-spawn", "--host", "sh", "-lc", cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        p = subprocess.run(["sh", "-lc", cmd], capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr


def ollama_running() -> bool:
    try:
        urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=2)
        return True
    except Exception:
        return False


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Nono LLM")
        self.set_default_size(720, 760)
        self.last_status = None
        self.history = []

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar()
        outer.append(header)

        # --- Steuerungsbereich ---
        control = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                          margin_top=12, margin_bottom=12,
                          margin_start=14, margin_end=14)
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.status_dot = Gtk.Label(label="●")
        self.status_label = Gtk.Label(label="Status wird geprüft …", hexpand=True,
                                      xalign=0.0)
        status_box.append(self.status_dot)
        status_box.append(self.status_label)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.start_btn = Gtk.Button(label="Server starten",
                                    css_classes=["suggested-action"])
        self.start_btn.connect("clicked", self.on_start)
        self.stop_btn = Gtk.Button(label="Server stoppen",
                                   css_classes=["destructive-action"])
        self.stop_btn.connect("clicked", self.on_stop)
        self.refresh_btn = Gtk.Button(label="Aktualisieren")
        self.refresh_btn.connect("clicked", lambda *_: self.refresh_status())
        btn_box.append(self.start_btn)
        btn_box.append(self.stop_btn)
        btn_box.append(self.refresh_btn)

        control.append(status_box)
        control.append(btn_box)
        outer.append(control)
        outer.append(Gtk.Separator())

        # --- Chatbereich ---
        chat_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        scrolled = Gtk.ScrolledWindow(vexpand=True)
        self.chat_list = Gtk.ListBox(css_classes=["boxed-list-separate"],
                                     selection_mode=Gtk.SelectionMode.NONE)
        scrolled.set_child(self.chat_list)
        chat_box.append(scrolled)

        entry_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                            margin_top=8, margin_bottom=10,
                            margin_start=14, margin_end=14)
        self.entry = Gtk.Entry(hexpand=True, placeholder_text=f"Nachricht an {MODEL} …")
        self.entry.connect("activate", self.on_send)
        send_btn = Gtk.Button(label="Senden",
                              css_classes=["suggested-action"])
        send_btn.connect("clicked", self.on_send)
        entry_box.append(self.entry)
        entry_box.append(send_btn)
        chat_box.append(Gtk.Separator())
        chat_box.append(entry_box)

        outer.append(chat_box)
        self.set_content(outer)
        self.refresh_status()
        GLib.timeout_add_seconds(5, self.refresh_status)

    # ---------- Status ----------
    def notify(self, title, body=""):
        n = Gio.Notification.new(title)
        n.set_body(body)
        self.get_application().send_notification(None, n)

    def set_status(self, running: bool):
        if running:
            self.status_dot.set_markup('<span foreground="#2ec27e">●</span>')
            self.status_label.set_text(f"Läuft — {MODEL} bereit (localhost:11434)")
            self.start_btn.set_sensitive(False)
            self.stop_btn.set_sensitive(True)
        else:
            self.status_dot.set_markup('<span foreground="#e01b24">●</span>')
            self.status_label.set_text("Gestoppt — nono/Ollama läuft nicht")
            self.start_btn.set_sensitive(True)
            self.stop_btn.set_sensitive(False)

    def refresh_status(self):
        def worker():
            running = ollama_running()
            GLib.idle_add(self.apply_status, running)
        threading.Thread(target=worker, daemon=True).start()
        return True

    def apply_status(self, running):
        if self.last_status is None:
            self.last_status = running
            self.set_status(running)
            return False
        if running != self.last_status:
            self.last_status = running
            self.set_status(running)
            if running:
                self.notify("Ollama-Server läuft",
                            "Der nono-sandboxed Server ist erreichbar.")
            else:
                self.notify("Ollama-Server gestoppt",
                            "Die nono-Session wurde beendet.")
        return False

    # ---------- Start / Stop ----------
    def on_start(self, *_):
        self.start_btn.set_sensitive(False)
        self.status_label.set_text("Starte nono-Sandbox …")

        def worker():
            rc, out, err = run_host(START_CMD)
            sid = ""
            m = re.search(r"session ([A-Za-z0-9]+)", out)
            if m:
                sid = m.group(1)
            GLib.idle_add(self.start_done, rc, sid, out.strip() + " " + err.strip())
        threading.Thread(target=worker, daemon=True).start()

    def start_done(self, rc, sid, output):
        ok = rc == 0
        if ok:
            msg = f"nono-Session {sid} gestartet." if sid else "nono hat den Server gestartet."
            self.notify("LLM-Server gestartet", msg)
        else:
            self.notify("Start fehlgeschlagen", output[:200])
        self.refresh_status()
        return False

    def on_stop(self, *_):
        def worker():
            rc, out, _ = run_host(f"{NONO_BIN} ps --json", timeout=15)
            sid = None
            if rc == 0 and out.strip():
                try:
                    data = json.loads(out)
                    sessions = data if isinstance(data, list) else data.get("sessions", [])
                    for s in sessions:
                        cmd = " ".join(str(s.get(k, "")) for k in ("command", "cmd"))
                        if "ollama" in cmd and s.get("status") != "exited":
                            sid = s.get("id") or s.get("session")
                            break
                except Exception:
                    pass
            if sid:
                run_host(f"{NONO_BIN} stop {sid}", timeout=30)
            else:
                run_host("pkill ollama", timeout=15)
            GLib.idle_add(self.refresh_status)
        threading.Thread(target=worker, daemon=True).start()

    # ---------- Chat ----------
    def add_message(self, sender: str, text: str):
        bubble = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4,
                         margin_top=6, margin_bottom=6,
                         margin_start=10, margin_end=10)
        title = Gtk.Label(xalign=0.0)
        if sender == "user":
            title.set_markup('<b foreground="#3584e4">Du</b>')
            bubble.add_css_class("card")
        else:
            title.set_markup('<b foreground="#9141ac">gemma2:9b</b>')
        body = Gtk.Label(xalign=0.0, wrap=True, selectable=True)
        body.set_text(text)
        bubble.append(title)
        bubble.append(body)
        self.chat_list.append(bubble)

    def on_send(self, *_):
        text = self.entry.get_text().strip()
        if not text:
            return
        self.entry.set_text("")
        self.add_message("user", text)
        self.history.append({"role": "user", "content": text})

        def worker():
            try:
                req = urllib.request.Request(
                    OLLAMA_URL + "/api/chat",
                    data=json.dumps({"model": MODEL,
                                     "messages": self.history,
                                     "stream": False}).encode(),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=600) as r:
                    answer = json.loads(r.read())["message"]["content"]
                self.history.append({"role": "assistant", "content": answer})
                GLib.idle_add(self.add_message, "assistant", answer)
            except Exception as e:
                GLib.idle_add(self.add_message, "assistant", f"Fehler: {e}")

        if not ollama_running():
            self.add_message("assistant",
                             "Der Server läuft nicht. Bitte zuerst starten.")
            return
        threading.Thread(target=worker, daemon=True).start()


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_activate(self):
        win = MainWindow(self)
        win.present()


if __name__ == "__main__":
    App().run([])
