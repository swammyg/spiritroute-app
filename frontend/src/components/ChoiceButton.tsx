interface ChoiceButtonProps {
  label: string;
  description?: string;
  selected: boolean;
  onSelect: () => void;
  variant?: "list" | "row" | "card";
}

export function ChoiceButton({ label, description, selected, onSelect, variant = "list" }: ChoiceButtonProps) {
  return (
    <button
      className={`choice choice--${variant}${selected ? " is-selected" : ""}`}
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
    >
      <span className="choice-label">{label}</span>
      {description && <span className="choice-description">{description}</span>}
    </button>
  );
}
