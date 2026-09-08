import { useEffect, useRef } from "react";
import { createPointsField, type PointsFieldHandle } from "@/lib/particles/pointsField";

/**
 * ParticleCanvas — mounts the Three.js particle field into a container that
 * fills its parent, drives the requestAnimationFrame loop, keeps the canvas
 * sized to the container via ResizeObserver, and fully disposes the WebGL
 * resources on unmount (StrictMode's mount/unmount/mount cycle included).
 *
 * Purely decorative — hidden from assistive tech; the CTA carries the meaning.
 */
export function ParticleCanvas() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let handle: PointsFieldHandle | null = null;
    let raf = 0;
    let cancelled = false;
    let resizeObserver: ResizeObserver | null = null;

    createPointsField(container)
      .then((field) => {
        // Unmounted before the async glyph sampling finished — tear down now.
        if (cancelled) {
          field.dispose();
          return;
        }
        handle = field;

        let last = performance.now();
        const loop = (now: number) => {
          const dt = (now - last) / 1000;
          last = now;
          field.render(dt, now / 1000);
          raf = requestAnimationFrame(loop);
        };
        raf = requestAnimationFrame(loop);

        resizeObserver = new ResizeObserver(() => {
          field.resize(container.clientWidth, container.clientHeight);
        });
        resizeObserver.observe(container);
      })
      .catch(() => {
        // WebGL context creation failed. The container stays empty (black),
        // an acceptable degradation — WelcomePage gates on isWebGLAvailable().
      });

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      resizeObserver?.disconnect();
      handle?.dispose();
      handle = null;
    };
  }, []);

  return (
    <div
      ref={containerRef}
      data-testid="particle-canvas"
      className="absolute inset-0"
      aria-hidden="true"
    />
  );
}
