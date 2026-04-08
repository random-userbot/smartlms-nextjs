'use client';

import React, { useRef, useState, useEffect } from 'react';
import { motion, useSpring, useMotionValue, useTransform } from 'framer-motion';

interface StringProps {
  index: number;
  isVertical: boolean;
  count: number;
  mouseX: any;
  mouseY: any;
}

const InteractiveString = ({ index, isVertical, count, mouseX, mouseY }: StringProps) => {
  const pathRef = useRef<SVGPathElement>(null);
  const [windowSize, setWindowSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    setWindowSize({ width: window.innerWidth, height: window.innerHeight });
    const handleResize = () => setWindowSize({ width: window.innerWidth, height: window.innerHeight });
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Spring for the displacement
  const displacement = useSpring(0, { stiffness: 400, damping: 12, mass: 0.5 });
  
  // Calculate specific coordinate for this string
  const posRatio = (index + 1) / (count + 1);
  const fixedCoord = isVertical ? posRatio * windowSize.width : posRatio * windowSize.height;

  const lastPos = useRef(0);
  const lastTime = useRef(Date.now());

  useEffect(() => {
    const handleMove = (v: number) => {
      const now = Date.now();
      const dt = now - lastTime.current;
      const dx = v - lastPos.current;
      const velocity = dt > 0 ? Math.abs(dx / dt) : 0;
      
      lastPos.current = v;
      lastTime.current = now;

      const dist = Math.abs(v - fixedCoord);
      if (dist < 150) {
        // Force is proportional to velocity and proximity
        const force = (1 - dist / 150) * Math.min(velocity * 20, 100);
        displacement.set(dx > 0 ? force : -force);
      } else {
        displacement.set(0);
      }
    };

    const unsubscribe = isVertical ? mouseX.on('change', handleMove) : mouseY.on('change', handleMove);

    return () => unsubscribe();
  }, [fixedCoord, isVertical, mouseX, mouseY, displacement]);

  const pathData = useTransform(displacement, (d) => {
    if (isVertical) {
      const midY = windowSize.height / 2;
      return `M ${fixedCoord} 0 Q ${fixedCoord + d} ${midY} ${fixedCoord} ${windowSize.height}`;
    } else {
      const midX = windowSize.width / 2;
      return `M 0 ${fixedCoord} Q ${midX} ${fixedCoord + d} ${windowSize.width} ${fixedCoord}`;
    }
  });

  return (
    <motion.path
      d={pathData}
      stroke="var(--color-primary)"
      strokeWidth="1.5"
      strokeOpacity={useTransform(displacement, [0, 100], [0.1, 0.5])}
      fill="transparent"
      className="pointer-events-none"
    />
  );
};

export const StringTuneGrid = () => {
  const mouseX = useMotionValue(-1000);
  const mouseY = useMotionValue(-1000);
  const hCount = 12;
  const vCount = 12;

  const handleMouseMove = (e: React.MouseEvent) => {
    mouseX.set(e.clientX);
    mouseY.set(e.clientY);
  };

  return (
    <div 
      className="absolute inset-0 z-0 overflow-hidden"
      onMouseMove={handleMouseMove}
    >
      <svg className="w-full h-full">
        {[...Array(hCount)].map((_, i) => (
          <InteractiveString 
            key={`h-${i}`} 
            index={i} 
            isVertical={false} 
            count={hCount} 
            mouseX={mouseX} 
            mouseY={mouseY} 
          />
        ))}
        {[...Array(vCount)].map((_, i) => (
          <InteractiveString 
            key={`v-${i}`} 
            index={i} 
            isVertical={true} 
            count={vCount} 
            mouseX={mouseX} 
            mouseY={mouseY} 
          />
        ))}
      </svg>
    </div>
  );
};
