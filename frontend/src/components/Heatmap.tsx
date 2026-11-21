import { useEffect, useRef } from "react";

/** Draws the traffic heat grid (0..1) and vehicle trajectories (normalised points) over an optional frame. */
export function HeatmapCanvas({ grid, trajectories, background, showHeat = true, showTracks = true }:
  { grid: number[][] | null | undefined; trajectories?: number[][][]; background?: string | null; showHeat?: boolean; showTracks?: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    const W = (c.width = 960), H = (c.height = 540);
    const paint = (img?: HTMLImageElement) => {
      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = "#0B1426"; ctx.fillRect(0, 0, W, H);
      if (img) { ctx.globalAlpha = 0.85; ctx.drawImage(img, 0, 0, W, H); ctx.globalAlpha = 1; }
      else {
        ctx.strokeStyle = "rgba(120,150,200,.12)";
        for (let x = 0; x <= W; x += 60) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
        for (let y = 0; y <= H; y += 60) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
      }
      if (showHeat && grid?.length) {
        const rows = grid.length, cols = grid[0].length, cw = W / cols, ch = H / rows;
        for (let y = 0; y < rows; y++) for (let x = 0; x < cols; x++) {
          const v = grid[y][x];
          if (v < 0.03) continue;
          const g = ctx.createRadialGradient((x + 0.5) * cw, (y + 0.5) * ch, 0, (x + 0.5) * cw, (y + 0.5) * ch, cw * 2.4);
          const hue = 200 - v * 200; // blue -> red
          g.addColorStop(0, `hsla(${hue},95%,55%,${0.25 + v * 0.55})`); g.addColorStop(1, `hsla(${hue},95%,55%,0)`);
          ctx.fillStyle = g; ctx.fillRect((x - 2) * cw, (y - 2) * ch, cw * 5, ch * 5);
        }
      }
      if (showTracks && trajectories?.length) {
        ctx.lineWidth = 2; ctx.lineJoin = "round";
        trajectories.forEach((t, i) => {
          ctx.strokeStyle = `hsla(${(i * 47) % 360},85%,65%,.8)`;
          ctx.beginPath();
          t.forEach(([x, y], k) => (k ? ctx.lineTo(x * W, y * H) : ctx.moveTo(x * W, y * H)));
          ctx.stroke();
          const [lx, ly] = t[t.length - 1];
          ctx.fillStyle = ctx.strokeStyle; ctx.beginPath(); ctx.arc(lx * W, ly * H, 4, 0, 7); ctx.fill();
        });
      }
    };
    if (background) {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => paint(img);
      img.onerror = () => paint();
      img.src = background;
    } else paint();
  }, [grid, trajectories, background, showHeat, showTracks]);
  return <canvas ref={ref} className="aspect-video w-full rounded-xl border border-line" role="img" aria-label="Traffic heatmap and vehicle movement paths" />;
}
