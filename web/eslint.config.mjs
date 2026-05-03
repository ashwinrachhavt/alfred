import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    // Guardrails for architectural conventions (see CLAUDE.md).
    // Deliberately scoped to app/components/features; lib/api is the sanctioned
    // place for fetch, so it's allowed to call fetch directly.
    files: [
      "app/**/*.{ts,tsx}",
      "components/**/*.{ts,tsx}",
      "features/**/*.{ts,tsx}",
      "hooks/**/*.{ts,tsx}",
    ],
    rules: {
      // Ban raw fetch() in UI — all HTTP should go through lib/api/client.
      "no-restricted-syntax": [
        "error",
        {
          selector:
            "CallExpression[callee.name='fetch']",
          message:
            "Use apiFetch() from @/lib/api/client. Direct fetch() calls bypass auth/error handling and break API consistency.",
        },
        {
          // Ban hex-literal Tailwind arbitrary values: bg-[#xxxxxx], text-[#xxx], border-[#xxx].
          // CSS-var bracket values (bg-[var(--token)]) and rgba() references to tokens are still allowed.
          selector:
            "Literal[value=/(bg|text|border|ring|fill|stroke|from|to|via|outline|decoration|divide|placeholder)-\\[#[0-9A-Fa-f]{3,8}/]",
          message:
            "Raw hex colors are not allowed in className. Use semantic tokens (bg-primary, text-foreground) or var(--alfred-*) CSS vars.",
        },
        {
          // Template literal equivalent.
          selector:
            "TemplateElement[value.raw=/(bg|text|border|ring|fill|stroke|from|to|via|outline|decoration|divide|placeholder)-\\[#[0-9A-Fa-f]{3,8}/]",
          message:
            "Raw hex colors are not allowed in className. Use semantic tokens (bg-primary, text-foreground) or var(--alfred-*) CSS vars.",
        },
      ],
    },
  },
  {
    // lib/api/ is the sanctioned place for fetch.
    files: ["lib/api/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-syntax": "off",
    },
  },
  {
    // Vendored upstream AI Elements components. These follow upstream patterns
    // we don't want to hand-edit (would have to re-apply on CLI updates).
    files: ["components/ai-elements/**/*.{ts,tsx}"],
    rules: {
      "react-hooks/refs": "off",
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/static-components": "off",
    },
  },
]);

export default eslintConfig;
