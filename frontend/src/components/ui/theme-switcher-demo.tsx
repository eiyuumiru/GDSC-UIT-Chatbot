import { ThemeSwitcher } from "@/components/ui/theme-switcher";
import { cn } from "@/lib/utils";
import { useState } from "react";

export function ThemeSwitcherDemo() {
  const [theme, setTheme] = useState<"light" | "dark" | "system">("system");

  return (
    <div
      className={cn(
        "flex min-h-[200px] w-full items-center justify-center rounded-2xl border border-dashed p-10 transition-colors",
        theme === "dark" ? "bg-black text-white" : "bg-white text-black"
      )}
    >
      <ThemeSwitcher value={theme} onChange={setTheme} />
    </div>
  );
}

export default ThemeSwitcherDemo;


