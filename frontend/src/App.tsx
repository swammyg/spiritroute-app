import { useEffect, useRef, useState, type ReactNode } from "react";

import { ApiError, fetchBeliefSystems, fetchDiagnosticOptions, resolveHeart } from "./api";
import type { DiagnosticOptions, ResolveHeartResponse } from "./api";
import { BeliefScreen } from "./components/BeliefScreen";
import { CircleScreen } from "./components/CircleScreen";
import { DriverScreen } from "./components/DriverScreen";
import { EmotionScreen } from "./components/EmotionScreen";
import { LoadingCard } from "./components/LoadingCard";
import { ResultScreen } from "./components/ResultScreen";
import { ScreenHeading } from "./components/ScreenHeading";

type Step = "belief" | "emotion" | "circle" | "driver" | "result";

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) {
      return "No matching scripture is available for that combination yet. Try a different answer.";
    }
    if (error.status >= 500) {
      return "The server couldn't complete the lookup right now. Please try again.";
    }
    return error.message;
  }
  return "Something unexpected happened. Please try again.";
}

export default function App() {
  const [options, setOptions] = useState<DiagnosticOptions | null>(null);
  const [beliefSystems, setBeliefSystems] = useState<string[] | null>(null);
  const [bootError, setBootError] = useState<string | null>(null);
  const [bootAttempt, setBootAttempt] = useState(0);

  const [step, setStep] = useState<Step>("belief");
  const [beliefSystem, setBeliefSystem] = useState<string | null>(null);
  const [emotion, setEmotion] = useState<string | null>(null);
  const [circle, setCircle] = useState<string | null>(null);
  const [driver, setDriver] = useState<string | null>(null);
  const [result, setResult] = useState<ResolveHeartResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const advanceTimer = useRef<number | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setBootError(null);
    Promise.all([fetchDiagnosticOptions(controller.signal), fetchBeliefSystems(controller.signal)])
      .then(([nextOptions, nextBeliefs]) => {
        setOptions(nextOptions);
        setBeliefSystems(nextBeliefs);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setBootError(describeError(error));
      });
    return () => controller.abort();
  }, [bootAttempt]);

  useEffect(() => {
    return () => {
      if (advanceTimer.current !== null) window.clearTimeout(advanceTimer.current);
    };
  }, []);

  function retryBoot() {
    setBootAttempt((attempt) => attempt + 1);
  }

  function scheduleStep(next: Step) {
    if (advanceTimer.current !== null) window.clearTimeout(advanceTimer.current);
    advanceTimer.current = window.setTimeout(() => {
      advanceTimer.current = null;
      setStep(next);
    }, 200);
  }

  function chooseBelief(value: string) {
    setBeliefSystem(value);
    scheduleStep("emotion");
  }

  function chooseEmotion(value: string) {
    setEmotion(value);
    setSubmitError(null);
    if (driver && !options?.drivers_by_emotion[value]?.includes(driver)) {
      setDriver(null);
    }
    scheduleStep("circle");
  }

  function chooseCircle(value: string) {
    setCircle(value);
    setSubmitError(null);
    setStep("driver");
  }

  function chooseDriver(value: string) {
    setDriver(value);
    setSubmitError(null);
  }

  function goBack() {
    setSubmitError(null);
    if (step === "circle") setStep("emotion");
    else if (step === "driver") setStep("circle");
  }

  async function submit() {
    if (isLoading || !beliefSystem || !emotion || !circle || !driver) return;
    setIsLoading(true);
    setSubmitError(null);
    try {
      const response = await resolveHeart({
        belief_system: beliefSystem,
        user_emotion: emotion,
        user_circle: circle,
        user_driver: driver,
      });
      setResult(response);
      setStep("result");
    } catch (error) {
      setSubmitError(describeError(error));
    } finally {
      setIsLoading(false);
    }
  }

  function restart() {
    if (advanceTimer.current !== null) {
      window.clearTimeout(advanceTimer.current);
      advanceTimer.current = null;
    }
    setResult(null);
    setSubmitError(null);
    setEmotion(null);
    setCircle(null);
    setDriver(null);
    setStep("emotion");
  }

  let cardKey = "boot";
  let content: ReactNode = <BootSplash />;

  if (bootError) {
    cardKey = "boot-error";
    content = (
      <BootMessage
        eyebrow="A small pause"
        title="We couldn't start the wizard"
        message={bootError}
        onRetry={retryBoot}
      />
    );
  } else if (options === null || beliefSystems === null) {
    cardKey = "boot";
    content = <BootSplash />;
  } else if (beliefSystems.length === 0) {
    cardKey = "no-scriptures";
    content = (
      <BootMessage
        eyebrow="A small pause"
        title="No scriptures loaded yet"
        message="The server is running, but its library is empty. Add a belief system's scriptures, then try again."
        onRetry={retryBoot}
      />
    );
  } else if (step === "belief") {
    cardKey = "belief";
    content = (
      <BeliefScreen beliefSystems={beliefSystems} selected={beliefSystem} onSelect={chooseBelief} />
    );
  } else if (step === "emotion") {
    cardKey = "emotion";
    content = <EmotionScreen emotions={options.emotions} selected={emotion} onSelect={chooseEmotion} />;
  } else if (step === "circle") {
    cardKey = "circle";
    content = (
      <CircleScreen
        circles={options.circles}
        selected={circle}
        onSelect={chooseCircle}
        onBack={goBack}
      />
    );
  } else if (step === "driver") {
    const activeEmotion = emotion ?? "";
    const drivers = options.drivers_by_emotion[activeEmotion] ?? [];
    if (isLoading) {
      cardKey = "driver-loading";
      content = <LoadingCard />;
    } else {
      cardKey = "driver";
      content = (
        <DriverScreen
          emotion={activeEmotion}
          drivers={drivers}
          selected={driver}
          error={submitError}
          onSelect={chooseDriver}
          onSubmit={submit}
          onBack={goBack}
        />
      );
    }
  } else if (step === "result" && result) {
    cardKey = "result";
    content = <ResultScreen result={result} onRestart={restart} />;
  }

  return (
    <main className="stage">
      <p className="brand">
        <span className="brand-mark" aria-hidden="true" />
        SpiritRoute
      </p>
      <section className="card" key={cardKey}>
        {content}
      </section>
      <p className="footnote">A quiet space for a heavy moment. Your answers are not stored.</p>
    </main>
  );
}

function BootSplash() {
  return (
    <div className="boot-splash" role="status">
      <p className="eyebrow">Preparing</p>
      <p className="loading-note">Getting the space ready…</p>
      <div className="skeleton-lines" aria-hidden="true">
        <span className="skeleton-line skeleton-line--title" />
        <span className="skeleton-line" />
        <span className="skeleton-line skeleton-line--short" />
      </div>
    </div>
  );
}

interface BootMessageProps {
  eyebrow: string;
  title: string;
  message: string;
  onRetry: () => void;
}

function BootMessage({ eyebrow, title, message, onRetry }: BootMessageProps) {
  return (
    <>
      <ScreenHeading eyebrow={eyebrow} title={title} subtitle={message} />
      <div className="action-bar">
        <button className="primary-action" type="button" onClick={onRetry}>
          Try again
        </button>
      </div>
    </>
  );
}
