// Ambient declarations for ThreeUI monorepo sibling modules referenced by unbundled components in LandingPages.tsx
declare module '*.html?raw' {
  const content: string;
  export default content;
}

declare module '*/tidecrestDocument.js' {
  export const buildTidecrestDocument: (variant: string) => string | undefined;
}

declare module '*/meridianDocument.js' {
  export const buildMeridianDocument: (variant: string, presentation?: string) => string | undefined;
}

declare module '*/asciiFieldDocuments.js' {
  export const buildAsciiFieldDocument: (variant: string) => string;
}

declare module '*/betawiseGlobeDocument.js' {
  export const buildBetawiseGlobeDocument: (variant: string) => string | undefined;
}

declare module '*/NocturneScene' {
  export const NOCTURNE_TITLES: Record<string, string>;
  export const NOCTURNE_VARIANTS: readonly string[];
  export type NocturneVariant = string;
  export const buildNocturneDocument: (variant: string) => string;
}

declare module '*/sandboxedPageDocument' {
  export const buildSandboxedPageDocument: (source: string, options: any) => string;
}

declare module '*/SylvaLivingWorldScene' {
  export const MAPLE_AUTUMN_STYLE: string;
  export const SAKURA_SUNSET_STYLE: string;
  export const SEQUOIA_MIST_STYLE: string;
  export const applyMapleAutumnVariant: (source: string) => string;
  export const applySakuraSunsetVariant: (source: string) => string;
  export const applySequoiaMistVariant: (source: string) => string;
}
