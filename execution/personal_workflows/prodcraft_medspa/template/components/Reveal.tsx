'use client';

// components/Reveal.tsx
// Fade+translateY reveal on scroll via IntersectionObserver, gated behind
// prefers-reduced-motion (the CSS in globals.css neutralizes the animation
// for reduced-motion users regardless of the JS state).

import { useEffect, useRef, useState } from 'react';
import type { PropsWithChildren } from 'react';

export default function Reveal({
  children,
  className = '',
}: PropsWithChildren<{ className?: string }>) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    if (typeof IntersectionObserver === 'undefined') {
      setVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setVisible(true);
            observer.disconnect();
          }
        }
      },
      { threshold: 0.15 }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={ref} className={`reveal ${visible ? 'is-visible' : ''} ${className}`}>
      {children}
    </div>
  );
}
