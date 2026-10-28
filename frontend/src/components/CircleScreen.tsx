import { ChoiceButton } from "./ChoiceButton";
import { ScreenHeading } from "./ScreenHeading";
import { WizardTop } from "./WizardTop";

interface CircleScreenProps {
  circles: string[];
  selected: string | null;
  onSelect: (circle: string) => void;
  onBack: () => void;
}

export function CircleScreen({ circles, selected, onSelect, onBack }: CircleScreenProps) {
  return (
    <>
      <WizardTop current={2} onBack={onBack} />
      <ScreenHeading title="This feeling is closely tied to..." />
      <div className="choice-row">
        {circles.map((circle) => (
          <ChoiceButton
            key={circle}
            label={circle}
            variant="row"
            selected={selected === circle}
            onSelect={() => onSelect(circle)}
          />
        ))}
      </div>
    </>
  );
}
