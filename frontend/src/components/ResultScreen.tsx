import { useEffect, useRef } from "react";

import type { ResolveHeartResponse } from "../api";

interface ResultScreenProps {
  result: ResolveHeartResponse;
  onRestart: () => void;
}

export function ResultScreen({ result, onRestart }: ResultScreenProps) {
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus({ preventScroll: true });
  }, []);

  if (result.crisis_override) {
    return (
      <>
        <p className="eyebrow">Support is here</p>
        <h1 className="screen-title" tabIndex={-1} ref={headingRef}>
          You are not alone
        </h1>
        <p className="crisis-message">{result.message}</p>
        <ul className="resource-list">
          {result.resources.map((resource) => (
            <li className="resource" key={`${resource.name}-${resource.contact}`}>
              <span className="resource-name">{resource.name}</span>
              <span className="resource-contact">{resource.contact}</span>
            </li>
          ))}
        </ul>
        <div className="action-bar">
          <button className="primary-action" type="button" onClick={onRestart}>
            Reflect on New Emotion
          </button>
        </div>
      </>
    );
  }

  return (
    <>
      <h1 className="sr-only" tabIndex={-1} ref={headingRef}>
        Your word of hope
      </h1>
      <p className="block-label">Verified scripture</p>
      <blockquote className="scripture">
        <p className="scripture-text">“{result.scripture_text}”</p>
        <cite>{result.source}</cite>
      </blockquote>
      <hr className="rule" />
      <section>
        <h2 className="block-label">Word of hope</h2>
        <p className="reflection-text">{result.word_of_hope}</p>
      </section>
      <hr className="rule" />
      <section>
        <h2 className="block-label">Prayer &amp; reflection</h2>
        <p className="reflection-text">{result.prayer_reflection}</p>
      </section>
      <div className="action-bar">
        <button className="primary-action" type="button" onClick={onRestart}>
          Reflect on New Emotion
        </button>
      </div>
    </>
  );
}
