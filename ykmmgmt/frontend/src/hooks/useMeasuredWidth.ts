// ── Container width measurement that survives conditional rendering ──────
// react-grid-layout v2's useContainerWidth attaches its ResizeObserver once
// at mount; if the ref'd div does not exist yet (tiles still loading, popup
// closed, ...) the width stays at the default forever. This hook uses a
// ref-callback so measurement (re)starts whenever the container appears.

import { useCallback, useEffect, useState } from "react";

export function useMeasuredWidth() {
  const [node, setNode] = useState<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(0);
  const [mounted, setMounted] = useState(false);

  const containerRef = useCallback((el: HTMLDivElement | null) => {
    setNode(el);
  }, []);

  useEffect(() => {
    if (!node) return;
    const measure = () => {
      const w = Math.round(node.clientWidth);
      setWidth((prev) => (prev === w ? prev : w));
      setMounted(true);
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(measure);
    ro.observe(node);
    return () => ro.disconnect();
  }, [node]);

  return { width, mounted, containerRef };
}
