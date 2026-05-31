import { useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

// ─── Constants ────────────────────────────────────────────────────────────────

const W = 440;
const H = 210;
const BIRD_X = 80;
const PW = 52;           // plane sprite width on canvas
const PH = 42;           // plane sprite height on canvas
const GRAVITY = 0.36;
const JUMP = -6.4;
const PIPE_W = 50;
const PIPE_GAP = 90;
const PIPE_SPEED = 2.2;
const PIPE_SPAWN_FRAMES = 115;

// ─── Module-level image preload (Vite serves /public at /) ───────────────────

const IMG_BG     = Object.assign(new Image(), { src: "/loading-game/background.png" });
const IMG_PLANE  = Object.assign(new Image(), { src: "/loading-game/plane.png" });
const IMG_GREEN  = Object.assign(new Image(), { src: "/loading-game/candle_green.png" });
const IMG_RED    = Object.assign(new Image(), { src: "/loading-game/candle_red.png" });

// ─── Types ────────────────────────────────────────────────────────────────────

interface Pipe { x: number; topH: number; scored: boolean; }

interface GameState {
  birdY: number;
  velY: number;
  pipes: Pipe[];
  framesSincePipe: number;
  bgOffset: number;
  score: number;
  phase: "idle" | "running" | "dead";
}

function makeState(): GameState {
  return {
    birdY: H / 2,
    velY: 0,
    pipes: [],
    framesSincePipe: PIPE_SPAWN_FRAMES, // spawn first pipe early
    bgOffset: 0,
    score: 0,
    phase: "idle",
  };
}

function spawnPipe(): Pipe {
  const topH = 30 + Math.random() * (H - PIPE_GAP - 60);
  return { x: W + PIPE_W, topH, scored: false };
}

// ─── Draw helpers ─────────────────────────────────────────────────────────────

function drawBackground(ctx: CanvasRenderingContext2D, bgOffset: number) {
  if (!IMG_BG.complete || IMG_BG.naturalWidth === 0) {
    ctx.fillStyle = "#0a1628";
    ctx.fillRect(0, 0, W, H);
    return;
  }
  const scale = H / IMG_BG.naturalHeight;
  const sw = IMG_BG.naturalWidth * scale;
  // Tile from slightly before canvas left so no blank strip appears
  const startX = ((-bgOffset * scale) % sw) - sw;
  for (let x = startX; x < W; x += sw) {
    ctx.drawImage(IMG_BG, x, 0, sw, H);
  }
}

function drawPipe(ctx: CanvasRenderingContext2D, pipe: Pipe) {
  const { x, topH } = pipe;
  const botY = topH + PIPE_GAP;
  const botH = H - botY;

  // ── Top pipe: red candle flipped vertically ──
  if (IMG_RED.complete && topH > 0) {
    ctx.save();
    ctx.translate(x + PIPE_W / 2, topH);
    ctx.scale(1, -1);
    ctx.drawImage(IMG_RED, -PIPE_W / 2, 0, PIPE_W, topH);
    ctx.restore();
  }

  // ── Bottom pipe: green candle normal ──
  if (IMG_GREEN.complete && botH > 0) {
    ctx.drawImage(IMG_GREEN, x, botY, PIPE_W, botH);
  }
}

function drawPlane(ctx: CanvasRenderingContext2D, y: number, velY: number, dead: boolean) {
  if (!IMG_PLANE.complete) return;
  ctx.save();
  ctx.translate(BIRD_X, y);
  // Tilt up on jump, down on fall; clamp so it doesn't over-rotate
  const angle = dead ? 0.6 : Math.max(-0.4, Math.min(0.55, velY * 0.065));
  ctx.rotate(angle);
  if (dead) ctx.globalAlpha = 0.7;
  ctx.drawImage(IMG_PLANE, -PW / 2, -PH / 2, PW, PH);
  ctx.restore();
}

// ─── Component ────────────────────────────────────────────────────────────────

export function FlappyBird() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef<GameState>(makeState());
  const rafRef = useRef<number>(0);
  const [phase, setPhase] = useState<"idle" | "running" | "dead">("idle");
  const [score, setScore] = useState(0);
  const [best, setBest] = useState(0);

  function jump() {
    const s = stateRef.current;
    if (s.phase === "idle") {
      s.phase = "running";
      s.velY = JUMP;
      setPhase("running");
    } else if (s.phase === "running") {
      s.velY = JUMP;
    } else if (s.phase === "dead") {
      stateRef.current = { ...makeState(), phase: "running", velY: JUMP };
      setPhase("running");
      setScore(0);
    }
  }

  // ─── Game loop ──────────────────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    function tick() {
      if (!ctx) return;
      const s = stateRef.current;

      // Background
      if (s.phase === "running") s.bgOffset += 1.3;
      drawBackground(ctx, s.bgOffset);

      // Physics + pipe logic
      if (s.phase === "running") {
        s.velY += GRAVITY;
        s.birdY += s.velY;

        // Spawn
        s.framesSincePipe++;
        if (s.framesSincePipe >= PIPE_SPAWN_FRAMES) {
          s.pipes.push(spawnPipe());
          s.framesSincePipe = 0;
        }

        // Move & score
        for (const p of s.pipes) {
          p.x -= PIPE_SPEED;
          if (!p.scored && p.x + PIPE_W < BIRD_X - PW / 2) {
            p.scored = true;
            s.score++;
            setScore(s.score);
            setBest((b) => Math.max(b, s.score));
          }
        }
        s.pipes = s.pipes.filter((p) => p.x + PIPE_W > 0);

        // Collision (shrink hitbox to ~70% of sprite for fairness)
        const hw = PW * 0.35;
        const hh = PH * 0.35;
        const hitBound = s.birdY - hh < 0 || s.birdY + hh > H;
        const hitPipe = s.pipes.some((p) => {
          const inX = BIRD_X + hw > p.x + 4 && BIRD_X - hw < p.x + PIPE_W - 4;
          const inGap =
            s.birdY - hh > p.topH && s.birdY + hh < p.topH + PIPE_GAP;
          return inX && !inGap;
        });

        if (hitBound || hitPipe) {
          s.phase = "dead";
          setPhase("dead");
        }
      }

      // Draw pipes
      for (const p of s.pipes) drawPipe(ctx, p);

      // Draw plane
      drawPlane(ctx, s.birdY, s.velY, s.phase === "dead");

      // Score
      if (s.phase !== "idle") {
        ctx.save();
        ctx.font = "bold 15px monospace";
        ctx.textAlign = "center";
        ctx.fillStyle = "rgba(255,255,255,0.95)";
        ctx.shadowColor = "#22d3ee";
        ctx.shadowBlur = 8;
        ctx.fillText(String(s.score), W / 2, 26);
        ctx.restore();
      }

      rafRef.current = requestAnimationFrame(tick);
    }

    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  // Keyboard handler
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code === "Space" || e.code === "ArrowUp") {
        e.preventDefault();
        jump();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex flex-col items-center gap-2">
      {/* Game canvas */}
      <div
        className="relative cursor-pointer rounded-xl overflow-hidden border border-white/10 shadow-[0_0_32px_-14px_var(--primary)]"
        style={{ width: W, height: H, maxWidth: "100%" }}
        onClick={jump}
      >
        <canvas ref={canvasRef} width={W} height={H} style={{ display: "block" }} />

        {/* Idle overlay */}
        {phase === "idle" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/45 backdrop-blur-[2px]">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-primary/80">
              While you wait
            </p>
            <p className="text-xl font-bold text-white drop-shadow">Flappy MarketPilot</p>
            <p className="text-xs text-muted-foreground">Dodge the candles to survive</p>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); jump(); }}
              className="mt-1 rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground shadow-[0_0_20px_-4px_var(--primary)] transition-all hover:brightness-110 active:scale-95"
            >
              Tap / Space to start
            </button>
          </div>
        )}

        {/* Dead overlay */}
        {phase === "dead" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/55 backdrop-blur-[2px]">
            <p className="text-lg font-bold text-white">Score: {score}</p>
            {best > 0 && (
              <p className="text-xs font-medium text-primary/80">Best: {best}</p>
            )}
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); jump(); }}
              className="mt-2 rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground shadow-[0_0_20px_-4px_var(--primary)] transition-all hover:brightness-110 active:scale-95"
            >
              Try again
            </button>
          </div>
        )}
      </div>

      <p className="text-[10px] text-muted-foreground/40">
        Click or Space to flap · Best: {best}
      </p>
    </div>
  );
}

// ─── Expandable wrapper (used by PollingLoader) ───────────────────────────────

interface ExpandableFlappyBirdProps {
  defaultOpen?: boolean;
}

export function ExpandableFlappyBird({ defaultOpen = false }: ExpandableFlappyBirdProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="w-full flex flex-col items-center gap-3">
      {/* Toggle button */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-xs font-medium text-muted-foreground transition-all hover:border-primary/30 hover:bg-primary/5 hover:text-foreground"
      >
        {open ? (
          <>
            <ChevronUp className="h-3.5 w-3.5" />
            Hide game
          </>
        ) : (
          <>
            <ChevronDown className="h-3.5 w-3.5" />
            Play while you wait
          </>
        )}
      </button>

      {/* Game — only rendered (and loop running) when open */}
      {open && <FlappyBird />}
    </div>
  );
}
