import { ChoiceButton } from "./ChoiceButton";
import { ScreenHeading } from "./ScreenHeading";
import { WizardTop } from "./WizardTop";

interface EmotionScreenProps {
  emotions: string[];
  selected: string | null;
  onSelect: (emotion: string) => void;
}

export function EmotionScreen({ emotions, selected, onSelect }: EmotionScreenProps) {
  return (
    <>
      <WizardTop current={1} />
      <ScreenHeading title="How does your heart feel right now?" />
      <div className="choice-stack">
        {emotions.map((emotion) => (
          <ChoiceButton
            key={emotion}
            label={emotion}
            selected={selected === emotion}
            onSelect={() => onSelect(emotion)}
          />
        ))}
      </div>
    </>
  );
}
