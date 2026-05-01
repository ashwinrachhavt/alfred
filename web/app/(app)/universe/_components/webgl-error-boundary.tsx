"use client";

import { Component, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { hasError: boolean };

export class WebGLErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-full flex-col items-center justify-center gap-4 bg-[#0F0E0D]">
          <p className="font-sans text-sm text-white/60">
            3D rendering isn&apos;t available in this browser.
          </p>
          <p className="max-w-sm text-center font-sans text-xs text-white/30">
            Your browser doesn&apos;t support WebGL, which is required for
            the 3D universe view. Try Chrome, Firefox, or Safari with
            hardware acceleration enabled.
          </p>
          <a
            href="/knowledge"
            className="rounded-md bg-[#E8590C] px-4 py-2 font-sans text-xs text-white"
          >
            View as list instead
          </a>
        </div>
      );
    }

    return this.props.children;
  }
}
