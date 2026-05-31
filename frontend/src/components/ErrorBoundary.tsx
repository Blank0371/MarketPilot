import { Component, type ReactNode } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";

interface Props {
  children: ReactNode;
  onReset?: () => void;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  reset = () => {
    this.setState({ error: null });
    this.props.onReset?.();
  };

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="flex flex-col items-center justify-center gap-5 rounded-2xl border border-destructive/30 bg-destructive/5 p-10 text-center">
        <span className="grid h-14 w-14 place-items-center rounded-full bg-destructive/10">
          <AlertTriangle className="h-7 w-7 text-destructive" />
        </span>
        <div className="space-y-1.5">
          <p className="text-base font-semibold text-foreground">Something went wrong</p>
          <p className="max-w-sm text-sm text-muted-foreground">
            The dashboard could not be rendered. This is usually caused by an unexpected
            response shape from the backend.
          </p>
          <p className="mt-2 font-mono text-[11px] text-destructive/70">
            {this.state.error.message}
          </p>
        </div>
        <button
          type="button"
          onClick={this.reset}
          className="flex items-center gap-2 rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground shadow-[0_0_20px_-4px_var(--primary)] transition-all hover:brightness-110 active:scale-95"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          Try again
        </button>
      </div>
    );
  }
}
