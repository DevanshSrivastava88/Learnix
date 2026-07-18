'use client';

import * as React from 'react';
import { useMotionValue, useSpring } from 'motion/react';

type CountingNumberProps = {
  number: number;
  fromNumber?: number;
  padStart?: boolean;
  decimalSeparator?: string;
  decimalPlaces?: number;
  /** delay in ms before the count starts */
  delay?: number;
  className?: string;
};

export function CountingNumber({
  number,
  fromNumber = 0,
  padStart = false,
  decimalSeparator = '.',
  decimalPlaces = 0,
  delay = 0,
  className,
}: CountingNumberProps) {
  const ref = React.useRef<HTMLSpanElement>(null);
  const mv = useMotionValue(fromNumber);
  const spring = useSpring(mv, { damping: 30, stiffness: 110, mass: 0.9 });

  const format = React.useCallback(
    (v: number) => {
      const fixed = Math.abs(v).toFixed(decimalPlaces);
      const [intPart, decPart] = fixed.split('.');
      let intStr = parseInt(intPart, 10).toLocaleString('en-US');
      if (padStart) {
        const targetLen = Math.trunc(Math.abs(number)).toString().length;
        intStr = intStr.padStart(targetLen, '0');
      }
      if (v < 0) intStr = '-' + intStr;
      return decimalPlaces > 0 && decPart != null
        ? `${intStr}${decimalSeparator}${decPart}`
        : intStr;
    },
    [decimalPlaces, decimalSeparator, padStart, number],
  );

  const [display, setDisplay] = React.useState(() => format(fromNumber));

  React.useEffect(() => {
    const t = setTimeout(() => mv.set(number), delay);
    return () => clearTimeout(t);
  }, [number, delay, mv]);

  React.useEffect(() => {
    const unsub = spring.on('change', (v) => setDisplay(format(v)));
    return () => unsub();
  }, [spring, format]);

  return (
    <span ref={ref} className={className}>
      {display}
    </span>
  );
}
