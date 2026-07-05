import { useCallback, useEffect, useState } from "react";

// data-theme en <html> + persistencia. main.tsx ya lo aplica pre-paint.
export function useTheme() {
  const [theme, setTheme] = useState<"dark" | "light">(() =>
    localStorage.getItem("atlas-theme") === "light" ? "light" : "dark",
  );
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("atlas-theme", theme);
  }, [theme]);
  const toggle = useCallback(() => setTheme((t) => (t === "dark" ? "light" : "dark")), []);
  return { theme, toggle };
}
