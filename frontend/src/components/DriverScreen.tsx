import { DRIVER_DESCRIPTIONS } from "../constants";
import { ChoiceButton } from "./ChoiceButton";
import { ScreenHeading } from "./ScreenHeading";
import { WizardTop } from "./WizardTop";

interface DriverScreenProps {
  emotion: string;
  drivers: string[];
  selected: string | null;
  error: string | null;
  onSelect: (driver: string) => void;
  onSubmit: () => void;
  onBack: () => void;
}

export function DriverScreen({
  emotion,
  drivers,
  selected,
  error,
  onSelect,
  onSubmit,
  onBack,
}: DriverScreenProps) {
  const celebrating = emotion === "Happy";

  return (
    <>
      <WizardTop current={3} onBack={onBack} />
      <ScreenHeading
        title={
          celebrating
            ? "What are you celebrating most in this moment?"
            : "What feels most threatened or missing right now?"
        }
      />
      <div className="choice-stack">
        {drivers.map((driver) => (
          <ChoiceButton
            key={driver}
            label={driver}
            description={DRIVER_DESCRIPTIONS[driver]}
            variant="card"
            selected={selected === driver}
            onSelect={() => onSelect(driver)}
          />
        ))}
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="action-bar">
        <button className="primary-action" type="button" disabled={!selected} onClick={onSubmit}>
          Get Word of Hope
        </button>
      </div>
    </>
  );
}
