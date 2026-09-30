import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  label: string;
}

interface State {
  error: Error | null;
}

/**
 * Without this, any uncaught exception in a tab's render (a null field from
 * the API, a bad assumption about response shape) unmounts the entire React
 * tree — the user sees a blank page with no clue why. This isolates the
 * failure to the tab that broke and shows what actually went wrong.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`Error rendering ${this.props.label}:`, error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="panel error-panel">
          <h2>Something broke in {this.props.label}</h2>
          <p className="muted">
            This is a bug, not expected behavior — other tabs should still work.
          </p>
          <pre className="error-detail">{this.state.error.message}</pre>
          <button onClick={() => this.setState({ error: null })}>Try again</button>
        </div>
      );
    }
    return this.props.children;
  }
}
