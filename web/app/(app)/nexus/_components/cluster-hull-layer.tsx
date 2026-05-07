"use client";

import { useEffect, useRef } from "react";

import { polygonHull } from "d3-polygon";
import type Graph from "graphology";
import type Sigma from "sigma";

const PALETTE = [
  "#c47a5a", "#7a9e7e", "#8b7ec8", "#c2956b", "#6b9eb8",
  "#b87a8f", "#9bb86b", "#c4855a", "#6b7eb8", "#b8a06b",
];

type Props = {
  sigma: Sigma | null;
  graph: Graph;
  enabled: boolean;
};

/**
 * Draws a translucent convex-hull polygon around each Louvain community,
 * painted on a canvas layered over the Sigma canvas. Redraws on every
 * Sigma render (for pan/zoom) and on container resize.
 */
export function ClusterHullLayer({
  sigma,
  graph,
  enabled,
}: Props): React.ReactElement {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // When disabled or no sigma: just clear and exit.
    if (!sigma || !enabled) {
      const dpr = window.devicePixelRatio || 1;
      ctx.clearRect(0, 0, canvas.width / dpr, canvas.height / dpr);
      return;
    }

    const draw = () => {
      const container = sigma.getContainer();
      const { width, height } = container.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;

      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, width, height);

      // Bucket viewport-coordinate points by community.
      const groups = new Map<number, [number, number][]>();
      graph.forEachNode((_id, attrs) => {
        const comm = attrs.community as number | undefined;
        if (comm == null) return;
        const x = attrs.x as number | undefined;
        const y = attrs.y as number | undefined;
        if (x == null || y == null) return;
        const coords = sigma.graphToViewport({ x, y });
        const list = groups.get(comm) ?? [];
        list.push([coords.x, coords.y]);
        groups.set(comm, list);
      });

      // Paint each cluster's convex hull.
      groups.forEach((points, comm) => {
        if (points.length < 3) return;
        const hull = polygonHull(points);
        if (!hull) return;

        ctx.beginPath();
        ctx.moveTo(hull[0][0], hull[0][1]);
        for (let i = 1; i < hull.length; i++) {
          ctx.lineTo(hull[i][0], hull[i][1]);
        }
        ctx.closePath();

        const color = PALETTE[comm % PALETTE.length];
        ctx.fillStyle = color + "18"; // ~9% alpha
        ctx.strokeStyle = color + "55"; // ~33% alpha
        ctx.lineWidth = 1;
        ctx.fill();
        ctx.stroke();
      });
    };

    draw();
    sigma.on("afterRender", draw);

    const ro = new ResizeObserver(draw);
    ro.observe(sigma.getContainer());

    return () => {
      sigma.off("afterRender", draw);
      ro.disconnect();
    };
  }, [sigma, graph, enabled]);

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none absolute inset-0"
      aria-hidden="true"
    />
  );
}
