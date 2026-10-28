import { ChoiceButton } from "./ChoiceButton";
import { ScreenHeading } from "./ScreenHeading";

interface BeliefScreenProps {
  beliefSystems: string[];
  selected: string | null;
  onSelect: (belief: string) => void;
}

export function BeliefScreen({ beliefSystems, selected, onSelect }: BeliefScreenProps) {
  return (
    <>
      <ScreenHeading
        eyebrow="Before we begin"
        title="Select your spiritual anchor"
        subtitle="This filters the global library to show texts aligned with your worldview."
      />
      <div className="choice-stack">
        {beliefSystems.map((belief) => (
          <ChoiceButton
            key={belief}
            label={belief}
            selected={selected === belief}
            onSelect={() => onSelect(belief)}
          />
        ))}
      </div>
    </>
  );
}
