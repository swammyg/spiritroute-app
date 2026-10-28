import { WizardTop } from "./WizardTop";

export function LoadingCard() {
  return (
    <>
      <WizardTop current={3} />
      <div className="loading" role="status" aria-live="polite">
        <p className="eyebrow">One quiet moment</p>
        <p className="loading-note">Finding a word for this moment…</p>
        <div className="skeleton-lines" aria-hidden="true">
          <span className="skeleton-line skeleton-line--title" />
          <span className="skeleton-line" />
          <span className="skeleton-line" />
          <span className="skeleton-line skeleton-line--short" />
        </div>
      </div>
    </>
  );
}
