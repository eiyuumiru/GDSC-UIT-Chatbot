import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode
} from "react";

type Theme = "light" | "dark" | "system";

type ThemeProviderState = {
  theme: Theme;
  resolvedTheme: "light" | "dark";
  setTheme: (theme: Theme) => void;
};

type ThemeProviderProps = {
  children: ReactNode;
  defaultTheme?: Theme;
  storageKey?: string;
};

const ThemeProviderContext = createContext<ThemeProviderState | undefined>(undefined);

const mediaQuery = "(prefers-color-scheme: dark)";

const getSystemPreference = (): "light" | "dark" => {
  if (typeof window === "undefined") {
    return "light";
  }

  return window.matchMedia(mediaQuery).matches ? "dark" : "light";
};

const applyDocumentClass = (value: Theme) => {
  if (typeof document === "undefined") {
    return value === "dark" ? "dark" : "light";
  }

  const root = document.documentElement;
  const resolved = value === "system" ? getSystemPreference() : value;

  root.classList.remove("light", "dark");
  root.classList.add(resolved);
  root.style.setProperty("color-scheme", resolved);

  return resolved;
};

export function ThemeProvider({
  children,
  defaultTheme = "system",
  storageKey = "gdgoc-ui-theme"
}: ThemeProviderProps) {
  const getInitialTheme = (): Theme => {
    if (typeof window === "undefined") {
      return defaultTheme;
    }

    const stored = window.localStorage.getItem(storageKey) as Theme | null;
    return stored ?? defaultTheme;
  };

  const [theme, setThemeState] = useState<Theme>(() => getInitialTheme());
  const [resolvedTheme, setResolvedTheme] = useState<"light" | "dark">(() =>
    applyDocumentClass(getInitialTheme())
  );

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    setResolvedTheme(applyDocumentClass(theme));
    window.localStorage.setItem(storageKey, theme);
  }, [theme, storageKey]);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }

    const media = window.matchMedia(mediaQuery);

    const handleChange = () => {
      if (theme === "system") {
        setResolvedTheme(applyDocumentClass("system"));
      }
    };

    media.addEventListener("change", handleChange);
    return () => media.removeEventListener("change", handleChange);
  }, [theme]);

  const value = useMemo<ThemeProviderState>(
    () => ({
      theme,
      resolvedTheme,
      setTheme: setThemeState
    }),
    [theme, resolvedTheme]
  );

  return (
    <ThemeProviderContext.Provider value={value}>{children}</ThemeProviderContext.Provider>
  );
}

export const useTheme = () => {
  const context = useContext(ThemeProviderContext);

  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }

  return context;
};


