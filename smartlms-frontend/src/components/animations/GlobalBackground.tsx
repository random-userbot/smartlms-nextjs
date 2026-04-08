'use client';

import React, { useState, useEffect } from 'react';
import { StringTuneGrid } from "./StringTuneGrid";
import { AikaOrb } from "./AikaOrb";

export const GlobalBackground = () => {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  return (
    <>
      <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden">
        <StringTuneGrid />
      </div>
      <AikaOrb />
    </>
  );
};
