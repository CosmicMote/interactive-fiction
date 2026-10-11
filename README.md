# Interactive Fiction

A locally-run web app where you and a model co-write a story one turn at a time. Each turn the model returns a structured `StoryBeat` (narration, established facts, act, concluded), and that becomes the input to the next turn. See [the spec](<Interactive Fiction Generator - Spec for Claude Code.md>) for the design.

## Run it

Requires [uv](https://docs.astral.sh/uv/) and [Ollama](https://ollama.com/) (for local models).

```bash
uv run fiction
```

Then open http://127.0.0.1:8000.

- **Local models:** the app offers a fixed list (Qwen 3.6 35B-A3B, Gemma 4 26B, Llama 3.1 8B), sized for a 48 GB Mac. It doesn't offer every model you've pulled. When the home page loads, it asks Ollama which models are installed:
  - A listed model you haven't pulled is greyed out, with the command to pull it: `ollama pull qwen3.6:35b-a3b`, `ollama pull gemma4:26b`, or `ollama pull llama3.1`. Reload the page after pulling.
  - If the app can't reach Ollama, every local model is greyed out, with the address it tried.
  - To offer a different local model, add a `_ollama(...)` line to `MODELS` in `src/fiction/config.py`.
- **Claude models:** set `ANTHROPIC_API_KEY` in the environment before starting. Sonnet 5.5 is the default; Opus 5.5, Haiku 4.5 and Fable 5.1 are also offered.
- **Compare mode:** pick any two models, including the same one twice.
- **Story notes:** facts, progress and Save are in a drawer at the right edge. Hover to peek, or click the Notes tab to pin it open.
- **Port:** 8000 by default; set `PORT` to change it.
- **Saves:** written to `./saves` as JSON. Override the location with `FICTION_SAVES_DIR`. Delete them from the home page (with confirmation).
- **Theme:** Light / System / Dark switcher in the header, remembered per browser.
- **Ollama host:** Ollama on this machine by default. Use `OLLAMA_HOST` to point at another one (see below).
- **Listen address:** `127.0.0.1` by default. Set `HOST=0.0.0.0` to accept connections from other machines.
- **Path prefix:** served at `/` by default. Set `BASE_PATH` (e.g. `/interactive-fiction`) to serve it under a prefix behind a reverse proxy.

## Use Ollama on another machine

The app can run on one machine, such as a Linux laptop, while the local models run on another with a better GPU, such as a Mac mini. The app reaches Ollama over HTTP.

**1. On the Ollama machine, make Ollama listen on the network.** By default it only accepts connections from itself (`127.0.0.1`). It has to listen on all interfaces (`OLLAMA_HOST=0.0.0.0:11434`).

With a Homebrew install on macOS, `brew services` can't hold that setting: `brew services restart` regenerates its service file (`~/Library/LaunchAgents/sh.brew.ollama.plist`) and drops any added variables. Instead, run Ollama from your own LaunchAgent:

1. Stop the Homebrew-managed service:

   ```bash
   brew services stop ollama
   ```

2. Create `~/Library/LaunchAgents/local.ollama.plist`:

   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
     <key>Label</key><string>local.ollama</string>
     <key>EnvironmentVariables</key>
     <dict>
       <key>OLLAMA_HOST</key><string>0.0.0.0:11434</string>
       <key>OLLAMA_FLASH_ATTENTION</key><string>1</string>
       <key>OLLAMA_KV_CACHE_TYPE</key><string>q8_0</string>
     </dict>
     <key>ProgramArguments</key>
     <array><string>/opt/homebrew/opt/ollama/bin/ollama</string><string>serve</string></array>
     <key>RunAtLoad</key><true/>
     <key>KeepAlive</key><true/>
     <key>WorkingDirectory</key><string>/opt/homebrew/var</string>
     <key>StandardOutPath</key><string>/opt/homebrew/var/log/ollama.log</string>
     <key>StandardErrorPath</key><string>/opt/homebrew/var/log/ollama.log</string>
   </dict>
   </plist>
   ```

3. Load it:

   ```bash
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/local.ollama.plist
   ```

4. Check that it's listening on all interfaces. The output should show `*:11434`, not `127.0.0.1:11434`:

   ```bash
   lsof -nP -iTCP:11434 -sTCP:LISTEN
   ```

It then starts at login. `brew upgrade ollama` keeps working, because `/opt/homebrew/opt/ollama` always points at the current version. To restart Ollama, run `launchctl kickstart -k gui/$(id -u)/local.ollama`. To undo all this, run `launchctl bootout gui/$(id -u)/local.ollama`, delete the file, and run `brew services start ollama`.

Allow `ollama` through the macOS firewall if asked, and stop the machine from sleeping (or turn on "Wake for network access").

Ollama has no authentication, so anyone on your network can use it once it's listening there. Never forward port 11434 on your router. Tailscale is a good way to reach it privately.

**2. On the app machine, check that Ollama is reachable:**

```bash
curl http://192.168.1.50:11434/api/tags
```

Replace the IP with the Ollama machine's. A `.local` name such as `neutron.local` works if mDNS resolves on the app machine, but use an IP address for Docker.

**3. Point the app at it:**

```bash
OLLAMA_HOST=http://192.168.1.50:11434 uv run fiction
```

## Run in Docker

The image only holds the app, not any models. It uses Ollama elsewhere (`OLLAMA_HOST`) and/or the Claude API (`ANTHROPIC_API_KEY`), so it stays small.

Build it:

```bash
docker build -t interactive-fiction .
```

Run it:

```bash
docker run -d --name interactive-fiction --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  -e OLLAMA_HOST=http://192.168.1.50:11434 \
  -e ANTHROPIC_API_KEY \
  -v interactive-fiction-saves:/data/saves \
  interactive-fiction
```

Then open http://127.0.0.1:8000.

- **`OLLAMA_HOST`:** the Ollama machine's IP address. `.local` names usually don't resolve inside containers. Without it, the container looks for Ollama inside itself and every local model is greyed out.
- **`ANTHROPIC_API_KEY`:** `-e ANTHROPIC_API_KEY` with no value passes it through from your shell. Leave it out to use local models only.
- **Port:** `127.0.0.1:8000:8000` keeps the app on this machine. There's no login, so `-p 8000:8000` lets anyone on your network use it.
- **Saves:** kept in the `interactive-fiction-saves` named volume, so they survive removing and rebuilding the container. The container runs as UID 1000. To use a folder instead (`-v ./saves:/data/saves`), create it first so it's owned by you; if Docker creates it, it's owned by root and saving fails.
- **`BASE_PATH`:** set this (e.g. `-e BASE_PATH=/interactive-fiction`) to serve the app under a path prefix behind a reverse proxy that forwards the full path. The app is then at `/interactive-fiction/`, and `/` redirects there.

To update after pulling changes, rebuild, then remove and re-run the container:

```bash
docker build -t interactive-fiction .
docker rm -f interactive-fiction
```

and repeat the `docker run` command. Saves are kept in the volume.

## Develop

```bash
uv run pytest
```

Layout (`src/fiction/`):

| Module | Role |
|---|---|
| `schema.py` | `StoryBeat`, `StoryState`, `SaveFile` |
| `prompts.py` | System prompt, per-turn prompt (facts + last 2 exchanges + pacing), act targets |
| `engine.py` | `propose()` candidates from one or two backends, `commit()` the chosen one, enforce pacing |
| `backends/` | `OllamaBackend`, `ClaudeBackend`, sharing one `generate_beat(system, prompt)` interface |
| `storage.py` | Save, load, list |
| `web/` | FastAPI + Jinja2 + HTMX UI. The only layer that knows about HTTP |

The model catalog (with per-model Claude settings), length targets, and defaults are in `config.py`.
