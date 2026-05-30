import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Loader2, BarChart3, Pencil, Trash2, Plus, Check, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface ConfirmDescriptionsProps {
  descriptions: string[];
  loading: boolean;
  onChange: (next: string[]) => void;
  onConfirm: () => void;
}

export function ConfirmDescriptions({
  descriptions,
  loading,
  onChange,
  onConfirm,
}: ConfirmDescriptionsProps) {
  return (
    <Card className="relative overflow-hidden border-white/10 bg-card/60 shadow-[0_0_60px_-30px_var(--accent)] backdrop-blur">
      <div
        aria-hidden
        className="pointer-events-none absolute -top-20 right-0 h-56 w-56 rounded-full opacity-25 blur-3xl"
        style={{ background: "radial-gradient(circle, var(--accent), transparent 70%)" }}
      />
      <CardHeader className="space-y-1.5">
        <CardTitle className="text-xl">Confirm the market drivers</CardTitle>
        <CardDescription className="max-w-xl text-sm text-muted-foreground">
          These descriptions drive the forecast. Each one maps to a time-series signal the
          model uses to predict your revenue. Edit, remove irrelevant ones, or add what's
          missing — the more precise, the sharper the forecast.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <ul className="space-y-2">
          {descriptions.map((desc, idx) => (
            <DescriptionRow
              key={idx}
              value={desc}
              index={idx}
              disabled={loading}
              onEdit={(next) => {
                const updated = [...descriptions];
                updated[idx] = next;
                onChange(updated);
              }}
              onDelete={() => onChange(descriptions.filter((_, i) => i !== idx))}
            />
          ))}
        </ul>

        <AddRow
          disabled={loading}
          onAdd={(text) => onChange([...descriptions, text])}
        />

        <div className="flex flex-col items-stretch justify-between gap-3 border-t border-white/10 pt-5 sm:flex-row sm:items-center">
          <p className="text-xs text-muted-foreground">
            {descriptions.length} factor{descriptions.length !== 1 ? "s" : ""} confirmed
            — Sybilion will forecast each one.
          </p>
          <Button
            onClick={onConfirm}
            disabled={loading || descriptions.length === 0}
            size="lg"
            className="bg-gradient-to-r from-primary to-accent font-medium text-primary-foreground shadow-[0_0_28px_-8px_var(--primary)] hover:opacity-95"
          >
            {loading ? (
              <>
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                Submitting…
              </>
            ) : (
              <>
                <BarChart3 className="mr-1.5 h-4 w-4" />
                Confirm &amp; forecast
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Single editable row ──────────────────────────────────────────────────────

function DescriptionRow({
  value,
  index,
  disabled,
  onEdit,
  onDelete,
}: {
  value: string;
  index: number;
  disabled: boolean;
  onEdit: (next: string) => void;
  onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);

  const startEdit = () => {
    setDraft(value);
    setEditing(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const commit = () => {
    const trimmed = draft.trim();
    if (trimmed) onEdit(trimmed);
    else setDraft(value);
    setEditing(false);
  };

  const cancel = () => {
    setDraft(value);
    setEditing(false);
  };

  return (
    <li
      className={cn(
        "group flex items-center gap-3 rounded-xl border border-white/8 bg-background/40 px-3.5 py-2.5 transition-colors",
        editing ? "border-primary/40 bg-primary/5" : "hover:border-white/15",
      )}
    >
      <span className="shrink-0 text-xs font-semibold tabular-nums text-muted-foreground/60 w-5 text-right">
        {index + 1}
      </span>

      {editing ? (
        <>
          <Input
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") commit();
              if (e.key === "Escape") cancel();
            }}
            className="h-7 flex-1 border-0 bg-transparent p-0 text-sm text-foreground shadow-none focus-visible:ring-0"
          />
          <button
            type="button"
            onClick={commit}
            className="shrink-0 rounded p-1 text-decision-launch hover:bg-decision-launch/10 transition-colors"
            aria-label="Save"
          >
            <Check className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={cancel}
            className="shrink-0 rounded p-1 text-muted-foreground hover:bg-white/5 transition-colors"
            aria-label="Cancel"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </>
      ) : (
        <>
          <span className="flex-1 text-sm text-foreground/90 leading-snug">{value}</span>
          <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
            <button
              type="button"
              disabled={disabled}
              onClick={startEdit}
              className="rounded p-1 text-muted-foreground hover:bg-white/8 hover:text-foreground transition-colors disabled:opacity-40"
              aria-label="Edit"
            >
              <Pencil className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              disabled={disabled}
              onClick={onDelete}
              className="rounded p-1 text-muted-foreground hover:bg-decision-danger/10 hover:text-decision-danger transition-colors disabled:opacity-40"
              aria-label="Delete"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        </>
      )}
    </li>
  );
}

// ─── Add new row ──────────────────────────────────────────────────────────────

function AddRow({
  disabled,
  onAdd,
}: {
  disabled: boolean;
  onAdd: (text: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const submit = () => {
    const trimmed = value.trim();
    if (trimmed) {
      onAdd(trimmed);
      setValue("");
      setOpen(false);
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        disabled={disabled}
        onClick={() => {
          setOpen(true);
          setTimeout(() => inputRef.current?.focus(), 0);
        }}
        className="flex w-full items-center gap-2 rounded-xl border border-dashed border-white/15 px-3.5 py-2.5 text-sm text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground disabled:opacity-40"
      >
        <Plus className="h-4 w-4" />
        Add a factor
      </button>
    );
  }

  return (
    <div className="flex items-center gap-2 rounded-xl border border-primary/30 bg-primary/5 px-3.5 py-2">
      <Input
        ref={inputRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Describe the market factor…"
        onKeyDown={(e) => {
          if (e.key === "Enter") submit();
          if (e.key === "Escape") {
            setValue("");
            setOpen(false);
          }
        }}
        className="h-7 flex-1 border-0 bg-transparent p-0 text-sm shadow-none placeholder:text-muted-foreground/50 focus-visible:ring-0"
      />
      <button
        type="button"
        onClick={submit}
        className="rounded px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10 transition-colors"
      >
        Add
      </button>
      <button
        type="button"
        onClick={() => { setValue(""); setOpen(false); }}
        className="rounded p-1 text-muted-foreground hover:bg-white/5 transition-colors"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
