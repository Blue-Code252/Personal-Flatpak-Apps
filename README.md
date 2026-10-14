# Nono LLM — GNOME-App für deinen nono-sandboxed Ollama-Server

Eine GTK4/libadwaita-App, die:

- **Status** zeigt: Läuft der Ollama-Server in der nono-Sandbox? (Polling alle 5 s)
- **Starten/Stoppen** kann — sie führt auf dem Host aus:
  - Start: `cd ~/llm-chat && nono run --detached --allow-cwd --allow ~/.ollama -- ollama serve`
  - Stop: `nono stop <session-id>` (aus `nono ps --json`), Fallback `pkill ollama`
- **GNOME-Benachrichtigungen** (native Popups) sendet, wenn der Server startet/stoppt/abstürzt
- **Chat-Fenster** mit Verlauf hat — sie spricht direkt mit `http://127.0.0.1:11434` (Modell: `gemma2:9b`)

## Wie die App auf den Host kommt

Im Flatpak läuft die App in ihrer eigenen Sandbox. Damit sie `nono`
auf deinem echten System starten kann, nutzt sie `flatpak-spawn --host`
(dafür steht `--talk-name=org.freedesktop.Flatpak` im Manifest).
Netzwerkzugriff für localhost:11434 über `--share=network`.

## Als Flatpak bauen

Im Projektordner:

```bash
cd flatpak
flatpak-builder --force-clean --user --install \
  build-dir de.muellermax.NonoLLM.json
```

Danach findest du „Nono LLM" im GNOME-App-Menü.

Mit **Bazaar**: Bazaar kann Flatpaks aus einem Manifest (JSON) bauen —
wähle dort „Aus Manifest/Quelle bauen" und gib
`flatpak/de.muellermax.NonoLLM.json` an, Repository-Root ist der
Projektordner.

## Zum Testen ohne Flatpak (auf dem Host)

```bash
python3 src/app.py
```

(Voraussetzung: `python3-gobject` mit GTK4/libadwaita installiert.)

## Anpassen

- Anderes Modell? In `src/app.py` oben `MODEL = "gemma2:9b"` ändern.
- Anderer Start-Ordner? `START_CMD` anpassen.

## Voraussetzungen auf dem Host

- `nono` v0.79.0 (installiert)
- Ollama (per brew installiert), Modelle in `~/.ollama`
- Der Ordner `~/llm-chat` existiert
