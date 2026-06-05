# NapCat + NoneBot2

This project now uses NoneBot2 with OneBot V11 for NapCat.

Start NoneBot:

```powershell
.\.venv\Scripts\python.exe bot.py
```

NapCat should connect back to NoneBot with WebSocket Client:

```text
ws://127.0.0.1:8080/onebot/v11/ws
```

Copy or merge `napcat/onebot11.json` into NapCat's OneBot11 configuration.
If NapCat already has a `onebot11.json`, keep its existing accounts/settings and
only add the `websocketClients` entry from this file.

The template uses array message format because NoneBot's OneBot adapter handles
CQ segments reliably in that form.
