import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const SCENARIOS = [
  { id: "patrol", label: "Patrol" },
  { id: "gas_leak", label: "Gas leak" },
  { id: "fire", label: "Fire" },
  { id: "rescue", label: "Rescue" },
  { id: "blocked", label: "Blocked" },
];

const COMMANDS = [
  { id: "forward", label: "Forward", glyph: "▲" },
  { id: "backward", label: "Back", glyph: "▼" },
  { id: "left", label: "Left", glyph: "◀" },
  { id: "right", label: "Right", glyph: "▶" },
  { id: "stop", label: "Stop", glyph: "■" },
  { id: "auto", label: "Auto", glyph: "A" },
];

function getWsUrl() {
  const { protocol, hostname, port } = window.location;
  const wsProtocol = protocol === "https:" ? "wss:" : "ws:";
  if (port === "5173") {
    return `${wsProtocol}//${hostname}:8000/ws/ui`;
  }
  const hostPort = port ? `${hostname}:${port}` : hostname;
  return `${wsProtocol}//${hostPort}/ws/ui`;
}

function fmtNum(n, digits = 1) {
  if (n == null || Number.isNaN(n)) return "—";
  return Number(n).toFixed(digits);
}

function fmtTime(ts) {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function severityClass(sev) {
  const s = (sev || "none").toLowerCase();
  if (s === "critical" || s === "high") return "sev-high";
  if (s === "medium") return "sev-medium";
  if (s === "low") return "sev-low";
  return "sev-none";
}

function Sensor({ label, value, unit, sub, alert }) {
  return (
    <div className={`sensor ${alert ? "sensor-alert" : ""}`}>
      <div className="sensor-label">{label}</div>
      <div className="sensor-value">
        <span>{value}</span>
        {unit ? <span className="sensor-unit">{unit}</span> : null}
      </div>
      {sub ? <div className="sensor-sub">{sub}</div> : null}
    </div>
  );
}

const EMPTY_STATE = {
  telemetry: null,
  hazards: [],
  active_hazards: [],
  navigation: null,
  path: [],
  source: "idle",
  last_update_ts: 0,
};

export default function App() {
  const [state, setState] = useState(EMPTY_STATE);
  const [wsStatus, setWsStatus] = useState("connecting");
  const [events, setEvents] = useState([]);
  const [activeScenario, setActiveScenario] = useState("patrol");
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);
  const canvasRef = useRef(null);
  const mapWrapRef = useRef(null);
  const lastHazardSigRef = useRef("");

  const pushEvent = useCallback((text, kind = "info") => {
    setEvents((prev) => [{ id: `${Date.now()}-${Math.random()}`, ts: Date.now(), text, kind }, ...prev].slice(0, 80));
  }, []);

  const sendWs = useCallback(
    (payload) => {
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(payload));
        return true;
      }
      pushEvent("WebSocket offline — command not sent", "warn");
      return false;
    },
    [pushEvent],
  );

  const sendControl = useCallback(
    (command) => {
      if (sendWs({ type: "control", command })) {
        pushEvent(`Manual control: ${command}`, "ctrl");
      }
    },
    [sendWs, pushEvent],
  );

  const sendScenario = useCallback(
    (scenario) => {
      setActiveScenario(scenario);
      if (sendWs({ type: "scenario", scenario, duration_sec: 25 })) {
        pushEvent(`Scenario started: ${scenario}`, "scenario");
      }
    },
    [sendWs, pushEvent],
  );

  useEffect(() => {
    let alive = true;

    function connect() {
      if (!alive) return;
      const url = getWsUrl();
      setWsStatus("connecting");
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!alive) return;
        setWsStatus("connected");
        pushEvent(`Linked to ${url}`, "info");
      };

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === "state" && msg.data) {
            setState(msg.data);
            const active = msg.data.active_hazards || [];
            const sig = active.map((h) => h.id).join("|");
            if (sig && sig !== lastHazardSigRef.current) {
              lastHazardSigRef.current = sig;
              const top = active[0];
              pushEvent(`Hazard: ${top.message || top.hazard_type}`, "hazard");
            }
            if (!sig) lastHazardSigRef.current = "";
          }
        } catch {
          /* ignore malformed frames */
        }
      };

      ws.onerror = () => {
        if (!alive) return;
        setWsStatus("error");
      };

      ws.onclose = () => {
        if (!alive) return;
        setWsStatus("disconnected");
        wsRef.current = null;
        reconnectRef.current = window.setTimeout(connect, 2000);
      };
    }

    connect();

    return () => {
      alive = false;
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [pushEvent]);

  const tel = state.telemetry;
  const nav = state.navigation;
  const path = state.path || [];
  const activeHazards = state.active_hazards || [];
  const hazardLog = state.hazards || [];

  const gasAlert = useMemo(() => {
    if (!tel?.gas) return false;
    const g = tel.gas;
    return g.co_ppm > 35 || g.ch4_ppm > 500 || g.h2s_ppm > 10;
  }, [tel]);

  const thermalAlert = tel?.thermal?.anomaly === true;
  const acousticAlert = tel?.acoustic?.event && tel.acoustic.event !== "none";

  const roverMeta = useMemo(() => {
    const st = tel?.status;
    return {
      battery: st ? `${fmtNum(st.battery_pct, 0)}%` : "—",
      mode: st?.mode ?? "—",
      speed: st ? `${fmtNum(st.speed_mps, 2)} m/s` : "—",
      heading: tel?.position ? `${fmtNum(tel.position.heading_deg, 0)}°` : "—",
      pos: tel?.position
        ? `X ${fmtNum(tel.position.x, 1)} · Y ${fmtNum(tel.position.y, 1)}`
        : "—",
    };
  }, [tel]);

  const drawMap = useCallback(() => {
    const canvas = canvasRef.current;
    const wrap = mapWrapRef.current;
    if (!canvas || !wrap) return;

    const dpr = window.devicePixelRatio || 1;
    const w = wrap.clientWidth;
    const h = wrap.clientHeight;
    if (w < 10 || h < 10) return;

    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;

    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    ctx.fillStyle = "#0a0c0e";
    ctx.fillRect(0, 0, w, h);

    const gridStep = 32;
    ctx.strokeStyle = "rgba(47, 158, 143, 0.12)";
    ctx.lineWidth = 1;
    for (let x = 0; x <= w; x += gridStep) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
    for (let y = 0; y <= h; y += gridStep) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    const points = path.length ? path : tel?.position ? [tel.position] : [];
    if (!points.length) {
      ctx.fillStyle = "rgba(224, 162, 26, 0.5)";
      ctx.font = "12px IBM Plex Mono, monospace";
      ctx.fillText("Awaiting path telemetry…", 16, 24);
      return;
    }

    const xs = points.map((p) => p.x);
    const ys = points.map((p) => p.y);
    activeHazards.forEach((hz) => {
      if (hz.position) {
        xs.push(hz.position.x);
        ys.push(hz.position.y);
      }
    });

    const minX = Math.min(...xs) - 2;
    const maxX = Math.max(...xs) + 2;
    const minY = Math.min(...ys) - 2;
    const maxY = Math.max(...ys) + 2;
    const pad = 24;

    const scale = Math.min((w - pad * 2) / (maxX - minX || 1), (h - pad * 2) / (maxY - minY || 1));

    const toScreen = (p) => ({
      x: pad + (p.x - minX) * scale,
      y: h - pad - (p.y - minY) * scale,
    });

    if (points.length > 1) {
      ctx.strokeStyle = "rgba(47, 158, 143, 0.85)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      points.forEach((p, i) => {
        const s = toScreen(p);
        if (i === 0) ctx.moveTo(s.x, s.y);
        else ctx.lineTo(s.x, s.y);
      });
      ctx.stroke();
    }

    activeHazards.forEach((hz) => {
      if (!hz.position) return;
      const s = toScreen(hz.position);
      const r = hz.severity === "critical" || hz.severity === "high" ? 9 : 6;
      ctx.fillStyle = "rgba(224, 84, 84, 0.35)";
      ctx.beginPath();
      ctx.arc(s.x, s.y, r + 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#e05454";
      ctx.beginPath();
      ctx.arc(s.x, s.y, r, 0, Math.PI * 2);
      ctx.fill();
    });

    const rover = tel?.position || points[points.length - 1];
    if (rover) {
      const s = toScreen(rover);
      const heading = ((rover.heading_deg || 0) * Math.PI) / 180;
      ctx.save();
      ctx.translate(s.x, s.y);
      ctx.rotate(-heading + Math.PI / 2);
      ctx.fillStyle = "#e0a21a";
      ctx.strokeStyle = "#2f9e8f";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(0, -10);
      ctx.lineTo(8, 8);
      ctx.lineTo(-8, 8);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.restore();
    }

    ctx.fillStyle = "rgba(255,255,255,0.45)";
    ctx.font = "11px IBM Plex Mono, monospace";
    ctx.fillText(`points ${points.length}`, 12, h - 10);
  }, [path, tel, activeHazards]);

  useEffect(() => {
    drawMap();
    const wrap = mapWrapRef.current;
    if (!wrap) return undefined;
    const ro = new ResizeObserver(() => drawMap());
    ro.observe(wrap);
    return () => ro.disconnect();
  }, [drawMap]);

  const wsPillClass =
    wsStatus === "connected" ? "pill pill-ok" : wsStatus === "connecting" ? "pill pill-warn" : "pill pill-bad";

  return (
    <div className="app fadeIn">
      <header className="topbar">
        <div className="brand">
          MHA<span className="brand-accent">RS</span>
          <span className="brand-sub">Mine Hazard Autonomous Response</span>
        </div>
        <div className="topbar-meta">
          <span className={wsPillClass}>{wsStatus.toUpperCase()}</span>
          <span className="pill pill-neutral">SRC {state.source || "idle"}</span>
          <span className="pill pill-neutral">UPD {fmtTime(state.last_update_ts)}</span>
        </div>
      </header>

      <main className="grid">
        <section className="panel panel-wide">
          <div className="panel-head">
            <h2>Live telemetry</h2>
            <span className="panel-tag">Sensors</span>
          </div>
          <div className="sensor-grid">
            <Sensor
              label="Gas — CO"
              value={fmtNum(tel?.gas?.co_ppm, 1)}
              unit="ppm"
              sub={`CH₄ ${fmtNum(tel?.gas?.ch4_ppm, 0)} · H₂S ${fmtNum(tel?.gas?.h2s_ppm, 2)}`}
              alert={gasAlert}
            />
            <Sensor
              label="Environment"
              value={fmtNum(tel?.environment?.temperature_c, 1)}
              unit="°C"
              sub={`RH ${fmtNum(tel?.environment?.humidity_pct, 0)}% · CO₂ ${fmtNum(tel?.gas?.co2_ppm, 0)} ppm`}
            />
            <Sensor
              label="Thermal max"
              value={fmtNum(tel?.thermal?.max_c, 1)}
              unit="°C"
              sub={`avg ${fmtNum(tel?.thermal?.avg_c, 1)} · min ${fmtNum(tel?.thermal?.min_c, 1)}`}
              alert={thermalAlert}
            />
            <Sensor
              label="Acoustic"
              value={fmtNum(tel?.acoustic?.level_db, 0)}
              unit="dB"
              sub={tel?.acoustic?.event ? `event ${tel.acoustic.event} (${fmtNum(tel.acoustic.confidence * 100, 0)}%)` : "no event"}
              alert={acousticAlert}
            />
            <Sensor
              label="Proximity F/L/R"
              value={`${fmtNum(tel?.proximity?.front_cm, 0)}/${fmtNum(tel?.proximity?.left_cm, 0)}/${fmtNum(tel?.proximity?.right_cm, 0)}`}
              unit="cm"
              sub={tel?.proximity?.rear_cm != null ? `rear ${fmtNum(tel.proximity.rear_cm, 0)} cm` : undefined}
            />
            <Sensor
              label="Visual feed"
              value={tel?.visual_available ? "LIVE" : "OFF"}
              unit=""
              sub={tel?.frame_jpeg_b64 ? "JPEG frame buffered" : "no frame"}
            />
          </div>
        </section>

        <section className="panel panel-map">
          <div className="panel-head">
            <h2>Tunnel map</h2>
            <span className="panel-tag">Path canvas</span>
          </div>
          <div className="tunnel map-wrap" ref={mapWrapRef}>
            <canvas ref={canvasRef} className="map-canvas" aria-label="Rover path map" />
          </div>
          <div className="rover-meta">
            <div className="meta">
              <span className="meta-k">Battery</span>
              <span className="meta-v">{roverMeta.battery}</span>
            </div>
            <div className="meta">
              <span className="meta-k">Mode</span>
              <span className="meta-v">{roverMeta.mode}</span>
            </div>
            <div className="meta">
              <span className="meta-k">Speed</span>
              <span className="meta-v">{roverMeta.speed}</span>
            </div>
            <div className="meta">
              <span className="meta-k">Heading</span>
              <span className="meta-v">{roverMeta.heading}</span>
            </div>
            <div className="meta meta-wide">
              <span className="meta-k">Position</span>
              <span className="meta-v">{roverMeta.pos}</span>
            </div>
          </div>
        </section>

        <section className="panel">
          <div className="panel-head">
            <h2>Active hazards</h2>
            <span className="panel-tag">{activeHazards.length} live</span>
          </div>
          <ul className="hazard-list">
            {activeHazards.length === 0 ? (
              <li className="hazard hazard-clear">No active hazards</li>
            ) : (
              activeHazards.map((h) => (
                <li key={h.id} className={`hazard ${severityClass(h.severity)}`}>
                  <div className="hazard-top">
                    <strong>{h.hazard_type}</strong>
                    <span className="hazard-sev">{h.severity}</span>
                  </div>
                  <p>{h.message}</p>
                  <div className="hazard-foot">
                    <span>{fmtTime(h.ts)}</span>
                    <span>{(h.modalities || []).join(", ") || "—"}</span>
                  </div>
                </li>
              ))
            )}
          </ul>
        </section>

        <section className="panel">
          <div className="panel-head">
            <h2>Navigation</h2>
            <span className="panel-tag">{nav?.action ?? "—"}</span>
          </div>
          <p className="nav-reason">{nav?.reason ?? "Waiting for navigation decision…"}</p>
          <p className="nav-obstacle">Obstacle clearance: {nav ? `${fmtNum(nav.obstacle_cm, 0)} cm` : "—"}</p>
          <div className="controls">
            <div className="dpad">
              <button type="button" className="ctrl-btn ctrl-up" onClick={() => sendControl("forward")} aria-label="Forward">
                ▲
              </button>
              <button type="button" className="ctrl-btn ctrl-left" onClick={() => sendControl("left")} aria-label="Left">
                ◀
              </button>
              <button type="button" className="ctrl-btn ctrl-stop pulseGlow" onClick={() => sendControl("stop")} aria-label="Stop">
                ■
              </button>
              <button type="button" className="ctrl-btn ctrl-right" onClick={() => sendControl("right")} aria-label="Right">
                ▶
              </button>
              <button type="button" className="ctrl-btn ctrl-down" onClick={() => sendControl("backward")} aria-label="Backward">
                ▼
              </button>
            </div>
            <div className="ctrl-row">
              {COMMANDS.filter((c) => c.id === "auto" || c.id === "stop").map((c) => (
                <button
                  key={c.id}
                  type="button"
                  className={`ctrl-btn ctrl-wide ${c.id === "stop" ? "ctrl-danger" : "ctrl-auto"}`}
                  onClick={() => sendControl(c.id)}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>
          <div className="scenario-block">
            <div className="panel-head panel-head-tight">
              <h3>Demo scenarios</h3>
            </div>
            <div className="chip-row">
              {SCENARIOS.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className={`chip ${activeScenario === s.id ? "chip-active" : ""}`}
                  onClick={() => sendScenario(s.id)}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="panel panel-wide">
          <div className="panel-head">
            <h2>Event log</h2>
            <span className="panel-tag">{hazardLog.length} hazard records</span>
          </div>
          <div className="event-log">
            {events.length === 0 ? (
              <div className="event event-muted">System idle — events will appear here.</div>
            ) : (
              events.map((e) => (
                <div key={e.id} className={`event event-${e.kind}`}>
                  <span className="event-time">{new Date(e.ts).toLocaleTimeString()}</span>
                  <span>{e.text}</span>
                </div>
              ))
            )}
          </div>
        </section>
      </main>

      <footer className="footer-note">
        MHARS control room · WebSocket {getWsUrl()} · Simulation & hardware modes via backend API
      </footer>
    </div>
  );
}
