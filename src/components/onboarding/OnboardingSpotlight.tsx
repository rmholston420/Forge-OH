'use client';
import { useEffect, useRef, useState } from 'react';

interface Rect { top: number; left: number; width: number; height: number; }

interface Props {
  targetSelector: string;
  padding?: number;
}

export function OnboardingSpotlight({ targetSelector, padding = 8 }: Props) {
  const [rect, setRect] = useState<Rect | null>(null);
  const roRef = useRef<ResizeObserver | null>(null);

  useEffect(() => {
    function measure() {
      const el = document.querySelector(targetSelector);
      if (!el) { setRect(null); return; }
      const r = el.getBoundingClientRect();
      setRect({
        top:    r.top    - padding,
        left:   r.left   - padding,
        width:  r.width  + padding * 2,
        height: r.height + padding * 2,
      });
    }

    measure();
    roRef.current = new ResizeObserver(measure);
    const el = document.querySelector(targetSelector);
    if (el) roRef.current.observe(el);
    window.addEventListener('resize', measure);
    return () => {
      roRef.current?.disconnect();
      window.removeEventListener('resize', measure);
    };
  }, [targetSelector, padding]);

  if (!rect) {
    // Full dark overlay when target not found
    return <div className="onboarding-overlay" aria-hidden style={{ inset: 0 }} />;
  }

  // SVG clip-path cutout technique
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const { top, left, width, height } = rect;
  const r = 8; // corner radius on spotlight

  const clipPath = [
    `M 0 0 H ${vw} V ${vh} H 0 Z`,
    `M ${left + r} ${top}`,
    `Q ${left} ${top} ${left} ${top + r}`,
    `V ${top + height - r}`,
    `Q ${left} ${top + height} ${left + r} ${top + height}`,
    `H ${left + width - r}`,
    `Q ${left + width} ${top + height} ${left + width} ${top + height - r}`,
    `V ${top + r}`,
    `Q ${left + width} ${top} ${left + width - r} ${top}`,
    `Z`,
  ].join(' ');

  return (
    <svg
      className="onboarding-overlay"
      aria-hidden
      style={{ position: 'fixed', inset: 0, width: '100vw', height: '100vh',
               pointerEvents: 'none', zIndex: 9998 }}
    >
      <path
        d={clipPath}
        fill="oklch(0.1 0 0 / 0.72)"
        fillRule="evenodd"
      />
    </svg>
  );
}
