import { useState } from "react";
import { X, Plus } from "lucide-react";

interface ChipListProps {
  values: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
}

export function ChipList({ values, onChange, placeholder = "Add..." }: ChipListProps) {
  const [draft, setDraft] = useState("");

  const commit = () => {
    const v = draft.trim();
    if (!v) return;
    if (values.includes(v)) {
      setDraft("");
      return;
    }
    onChange([...values, v]);
    setDraft("");
  };

  return (
    <div className="flex flex-wrap items-center gap-1.5 rounded-md border border-input bg-card px-2 py-2 focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/15">
      {values.map((v) => (
        <span
          key={v}
          className="inline-flex items-center gap-1 rounded-full bg-secondary px-2.5 py-1 text-xs font-medium text-secondary-foreground"
        >
          {v}
          <button
            type="button"
            onClick={() => onChange(values.filter((x) => x !== v))}
            className="text-muted-foreground transition-colors hover:text-foreground"
            aria-label={`Remove ${v}`}
          >
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
      <div className="flex flex-1 items-center gap-1">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              commit();
            }
          }}
          placeholder={placeholder}
          className="min-w-[80px] flex-1 border-0 bg-transparent text-xs text-foreground outline-none placeholder:text-muted-foreground"
        />
        {draft && (
          <button
            type="button"
            onClick={commit}
            className="rounded-full p-1 text-muted-foreground hover:bg-secondary hover:text-foreground"
            aria-label="Add"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}
