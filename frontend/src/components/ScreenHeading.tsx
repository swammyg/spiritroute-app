import { useEffect, useRef } from "react";

interface ScreenHeadingProps {
  title: string;
  subtitle?: string;
  eyebrow?: string;
}

export function ScreenHeading({ title, subtitle, eyebrow }: ScreenHeadingProps) {
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus({ preventScroll: true });
  }, []);

  return (
    <div className="screen-heading">
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <h1 className="screen-title" tabIndex={-1} ref={headingRef}>
        {title}
      </h1>
      {subtitle && <p className="screen-subtitle">{subtitle}</p>}
    </div>
  );
}
