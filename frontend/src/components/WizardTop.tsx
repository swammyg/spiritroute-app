interface WizardTopProps {
  current: number;
  total?: number;
  onBack?: () => void;
}

export function WizardTop({ current, total = 3, onBack }: WizardTopProps) {
  return (
    <div className="wizard-top">
      <div className="wizard-back-slot">
        {onBack && (
          <button className="back-button" type="button" onClick={onBack}>
            <span aria-hidden="true">←</span> Back
          </button>
        )}
      </div>
      <div
        className="progress"
        role="progressbar"
        aria-label={`Step ${current} of ${total}`}
        aria-valuemin={1}
        aria-valuemax={total}
        aria-valuenow={current}
      >
        {Array.from({ length: total }, (_, index) => (
          <span
            key={index}
            className={`progress-dot${index < current ? " is-filled" : ""}`}
            aria-hidden="true"
          />
        ))}
      </div>
    </div>
  );
}
