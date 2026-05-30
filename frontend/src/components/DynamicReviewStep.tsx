import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ChipList } from "./ChipList";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { Loader2, Calculator } from "lucide-react";
import type {
  EditableField,
  EditableFieldGroup,
  EditableFieldValue,
} from "@/lib/types";

interface DynamicReviewStepProps {
  groups: EditableFieldGroup[];
  loading: boolean;
  onChange: (next: EditableFieldGroup[]) => void;
  onCalculate: () => void;
}

export function DynamicReviewStep({
  groups,
  loading,
  onChange,
  onCalculate,
}: DynamicReviewStepProps) {
  const updateField = (
    categoryIdx: number,
    fieldKey: string,
    value: EditableFieldValue,
  ) => {
    const next = groups.map((g, gi) =>
      gi !== categoryIdx
        ? g
        : {
            ...g,
            fields: g.fields.map((f) =>
              f.key === fieldKey ? { ...f, value } : f,
            ),
          },
    );
    onChange(next);
  };

  return (
    <Card className="border-white/10 bg-card/60 shadow-[0_0_60px_-30px_var(--accent)] backdrop-blur">
      <CardHeader className="space-y-1.5">
        <CardTitle className="text-xl">Review editable assumptions</CardTitle>
        <CardDescription className="text-muted-foreground">
          The backend returned structured fields from your prompt. Review, edit, remove, or add information before calculating the result.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-8">
        {groups.map((group, gi) => (
          <section key={group.category} className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="h-px flex-1 bg-gradient-to-r from-white/10 to-transparent" />
              <h3 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                {group.category}
              </h3>
              <div className="h-px flex-1 bg-gradient-to-l from-white/10 to-transparent" />
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {group.fields.map((f) => (
                <FieldRenderer
                  key={f.key}
                  field={f}
                  wide={f.type === "tags"}
                  onChange={(v) => updateField(gi, f.key, v)}
                />
              ))}
            </div>
          </section>
        ))}

        <div className="flex flex-col items-stretch justify-end gap-3 border-t border-white/10 pt-6 sm:flex-row sm:items-center">
          <Button
            onClick={onCalculate}
            disabled={loading}
            size="lg"
            className="bg-gradient-to-r from-primary to-accent font-medium text-primary-foreground shadow-[0_0_28px_-8px_var(--primary)] hover:opacity-95"
          >
            {loading ? (
              <>
                <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                Calculating decision...
              </>
            ) : (
              <>
                <Calculator className="mr-1 h-4 w-4" />
                Calculate
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function FieldRenderer({
  field,
  wide,
  onChange,
}: {
  field: EditableField;
  wide?: boolean;
  onChange: (v: EditableFieldValue) => void;
}) {
  const colSpan = wide ? "md:col-span-2 lg:col-span-3" : undefined;

  return (
    <div className={colSpan}>
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <Label className="text-xs font-medium text-foreground/85">
          {field.label}
        </Label>
        {field.confidence && <ConfidenceBadge level={field.confidence} />}
      </div>
      {renderControl(field, onChange)}
      {field.helper && (
        <p className="mt-1 text-[11px] text-muted-foreground">{field.helper}</p>
      )}
    </div>
  );
}

function renderControl(
  field: EditableField,
  onChange: (v: EditableFieldValue) => void,
) {
  const inputClass =
    "border-white/10 bg-background/60 backdrop-blur focus-visible:border-primary/60 focus-visible:ring-primary/30";

  switch (field.type) {
    case "text":
      return (
        <Input
          className={inputClass}
          value={String(field.value)}
          onChange={(e) => onChange(e.target.value)}
        />
      );
    case "number":
      return (
        <Input
          type="number"
          className={inputClass}
          value={Number(field.value)}
          onChange={(e) => onChange(Number(e.target.value))}
        />
      );
    case "currency":
      return (
        <div className="relative">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
            €
          </span>
          <Input
            type="number"
            className={`${inputClass} pl-7`}
            value={Number(field.value)}
            onChange={(e) => onChange(Number(e.target.value))}
          />
        </div>
      );
    case "percentage":
      return (
        <div className="relative">
          <Input
            type="number"
            className={`${inputClass} pr-8`}
            value={Number(field.value)}
            onChange={(e) => onChange(Number(e.target.value))}
          />
          <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
            %
          </span>
        </div>
      );
    case "select":
      return (
        <Select value={String(field.value)} onValueChange={(v) => onChange(v)}>
          <SelectTrigger className={inputClass}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(field.options ?? []).map((opt) => (
              <SelectItem key={opt} value={opt}>
                {opt}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      );
    case "tags":
      return (
        <ChipList
          values={Array.isArray(field.value) ? field.value : []}
          onChange={(v) => onChange(v)}
          placeholder="Add value"
        />
      );
  }
}
