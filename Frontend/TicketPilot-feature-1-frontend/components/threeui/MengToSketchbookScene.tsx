'use client';

import React from 'react';
import { LandingPageFrame, type LandingPageProps } from '@/src/shaders/landing-pages/LandingPageFrame';
import {
  splitTypographyProps,
  usePageTypography,
  type PageTypographyProps,
} from '@/src/shaders/landing-pages/pageTypography';
import { MENG_TO_SKETCHBOOK_TYPOGRAPHY } from '@/src/shaders/landing-pages/pageRecipes';

export function MengToSketchbookLandingPage(props: LandingPageProps & PageTypographyProps) {
  const [type, frame] = splitTypographyProps(props);
  const customization = usePageTypography(MENG_TO_SKETCHBOOK_TYPOGRAPHY, type);

  return (
    <LandingPageFrame
      {...frame}
      customization={customization}
      title="Meng To — Singapore Sketchbook"
      sourceUrl="/landing-pages/meng-to-sketchbook.html"
    />
  );
}

export function Scene() {
  return (
    <div className="shader-frame w-full h-[650px] sm:h-[720px] rounded-2xl overflow-hidden border border-stone-300 shadow-glass-elevated bg-[#ece7dc]">
      <MengToSketchbookLandingPage
        headingFont="instrument-serif"
        bodyFont="newsreader"
        headingWeight="400"
        bodyWeight="400"
        primaryColor="#2b2721"
        headingSize={30}
        bodySize={20}
        headingLetterSpacing={0.01}
      />
    </div>
  );
}
