// src/hooks/useDebounce.js
import { useState, useEffect } from 'react';
export function useDebounce(value, delay = 400) {
  const [dv, setDv] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDv(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return dv;
}

// src/hooks/useAsync.js — not a separate file but included below for convenience
