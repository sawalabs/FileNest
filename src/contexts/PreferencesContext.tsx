import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  ReactNode,
} from "react";
import { ApiService } from "@/services/api";
import type { GeneralSettings } from "@/types";

export type ThemeMode = "light" | "dark" | "system";
export type FileViewMode = "list" | "grid";
export type TableDensity = "comfortable" | "compact";

interface PreferencesContextType {
  theme: ThemeMode;
  effectiveTheme: "light" | "dark";
  setTheme: (theme: ThemeMode) => void;
  defaultFileView: FileViewMode;
  setDefaultFileView: (view: FileViewMode) => void;
  defaultTableDensity: TableDensity;
  setDefaultTableDensity: (density: TableDensity) => void;
  showFileExtensions: boolean;
  setShowFileExtensions: (show: boolean) => void;
  showHiddenFiles: boolean;
  setShowHiddenFiles: (show: boolean) => void;
  generalSettings: GeneralSettings | null;
  isLoading: boolean;
  refreshPreferences: () => Promise<void>;
  updateGeneralPreferences: (partial: Partial<GeneralSettings>) => Promise<void>;
}

const STORAGE_KEYS = {
  THEME: "filenest_theme",
  FILE_VIEW: "filenest_default_file_view",
  TABLE_DENSITY: "filenest_table_density",
  SHOW_EXTENSIONS: "filenest_show_extensions",
  SHOW_HIDDEN: "filenest_show_hidden",
};

const PreferencesContext = createContext<PreferencesContextType | undefined>(undefined);

function getSystemTheme(): "light" | "dark" {
  if (typeof window !== "undefined" && window.matchMedia) {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return "light";
}

function applyThemeToDOM(resolvedTheme: "light" | "dark") {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  if (resolvedTheme === "dark") {
    root.classList.add("dark");
    root.style.colorScheme = "dark";
  } else {
    root.classList.remove("dark");
    root.style.colorScheme = "light";
  }
}

async function syncTauriDesktopBehavior(general: GeneralSettings): Promise<void> {
  if (typeof window === "undefined" || !("__TAURI_INTERNALS__" in window)) {
    return;
  }
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    await invoke("sync_desktop_behavior", {
      launchOnStartup: Boolean(general.start_on_startup),
      minimizeToTray: Boolean(general.minimize_to_tray),
    });
  } catch (err) {
    console.warn("Failed to synchronize desktop tray/startup behavior with Tauri:", err);
  }
}

export const PreferencesProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  // 1. Initial synchronous state from localStorage for instantaneous hydration (zero flicker)
  const [theme, setThemeState] = useState<ThemeMode>(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.THEME) as ThemeMode | null;
    return saved === "dark" || saved === "light" || saved === "system" ? saved : "system";
  });

  const [effectiveTheme, setEffectiveTheme] = useState<"light" | "dark">(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.THEME) as ThemeMode | null;
    if (saved === "dark") return "dark";
    if (saved === "light") return "light";
    return getSystemTheme();
  });

  const [defaultFileView, setDefaultFileViewState] = useState<FileViewMode>(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.FILE_VIEW) as FileViewMode | null;
    return saved === "grid" ? "grid" : "list";
  });

  const [defaultTableDensity, setDefaultTableDensityState] = useState<TableDensity>(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.TABLE_DENSITY) as TableDensity | null;
    return saved === "compact" ? "compact" : "comfortable";
  });

  const [showFileExtensions, setShowFileExtensionsState] = useState<boolean>(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.SHOW_EXTENSIONS);
    return saved !== null ? saved === "true" : true;
  });

  const [showHiddenFiles, setShowHiddenFilesState] = useState<boolean>(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.SHOW_HIDDEN);
    return saved !== null ? saved === "true" : false;
  });

  const [generalSettings, setGeneralSettings] = useState<GeneralSettings | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // 2. Synchronize theme with DOM and system listeners
  useEffect(() => {
    const resolved = theme === "system" ? getSystemTheme() : theme;
    setEffectiveTheme(resolved);
    applyThemeToDOM(resolved);
    localStorage.setItem(STORAGE_KEYS.THEME, theme);

    if (theme === "system" && typeof window !== "undefined" && window.matchMedia) {
      const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
      const handleChange = (e: MediaQueryListEvent) => {
        const sys = e.matches ? "dark" : "light";
        setEffectiveTheme(sys);
        applyThemeToDOM(sys);
      };
      mediaQuery.addEventListener("change", handleChange);
      return () => mediaQuery.removeEventListener("change", handleChange);
    }
  }, [theme]);

  // 3. Load persisted settings from backend API
  const refreshPreferences = useCallback(async () => {
    try {
      const data = await ApiService.getCategorySettings<GeneralSettings>("general");
      if (data) {
        setGeneralSettings(data);
        if (data.theme) {
          const t = data.theme as ThemeMode;
          setThemeState(t);
          localStorage.setItem(STORAGE_KEYS.THEME, t);
        }
        if (data.default_file_view) {
          const fv = data.default_file_view as FileViewMode;
          setDefaultFileViewState(fv);
          localStorage.setItem(STORAGE_KEYS.FILE_VIEW, fv);
        }
        if (data.default_table_density) {
          const td = data.default_table_density as TableDensity;
          setDefaultTableDensityState(td);
          localStorage.setItem(STORAGE_KEYS.TABLE_DENSITY, td);
        }
        if (typeof data.show_file_extensions === "boolean") {
          setShowFileExtensionsState(data.show_file_extensions);
          localStorage.setItem(STORAGE_KEYS.SHOW_EXTENSIONS, String(data.show_file_extensions));
        }
        if (typeof data.show_hidden_files === "boolean") {
          setShowHiddenFilesState(data.show_hidden_files);
          localStorage.setItem(STORAGE_KEYS.SHOW_HIDDEN, String(data.show_hidden_files));
        }
        await syncTauriDesktopBehavior(data);
      }
    } catch (err) {
      console.warn("Could not load remote preferences from backend; using cached settings:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshPreferences();
  }, [refreshPreferences]);

  // 4. Update and persist general preferences
  const updateGeneralPreferences = useCallback(
    async (partial: Partial<GeneralSettings>) => {
      // Optimistic local state update
      if (partial.theme) {
        const t = partial.theme as ThemeMode;
        setThemeState(t);
        localStorage.setItem(STORAGE_KEYS.THEME, t);
      }
      if (partial.default_file_view) {
        const fv = partial.default_file_view as FileViewMode;
        setDefaultFileViewState(fv);
        localStorage.setItem(STORAGE_KEYS.FILE_VIEW, fv);
      }
      if (partial.default_table_density) {
        const td = partial.default_table_density as TableDensity;
        setDefaultTableDensityState(td);
        localStorage.setItem(STORAGE_KEYS.TABLE_DENSITY, td);
      }
      if (typeof partial.show_file_extensions === "boolean") {
        setShowFileExtensionsState(partial.show_file_extensions);
        localStorage.setItem(STORAGE_KEYS.SHOW_EXTENSIONS, String(partial.show_file_extensions));
      }
      if (typeof partial.show_hidden_files === "boolean") {
        setShowHiddenFilesState(partial.show_hidden_files);
        localStorage.setItem(STORAGE_KEYS.SHOW_HIDDEN, String(partial.show_hidden_files));
      }

      // Persist to backend SQLite
      try {
        const updated = await ApiService.updateCategorySettings<GeneralSettings>("general", partial);
        setGeneralSettings(updated);
        await syncTauriDesktopBehavior(updated);
      } catch (err) {
        console.error("Failed to save preferences to backend:", err);
        throw err;
      }
    },
    []
  );

  const setTheme = useCallback((newTheme: ThemeMode) => {
    setThemeState(newTheme);
    localStorage.setItem(STORAGE_KEYS.THEME, newTheme);
  }, []);

  const setDefaultFileView = useCallback((view: FileViewMode) => {
    setDefaultFileViewState(view);
    localStorage.setItem(STORAGE_KEYS.FILE_VIEW, view);
  }, []);

  const setDefaultTableDensity = useCallback((density: TableDensity) => {
    setDefaultTableDensityState(density);
    localStorage.setItem(STORAGE_KEYS.TABLE_DENSITY, density);
  }, []);

  const setShowFileExtensions = useCallback((show: boolean) => {
    setShowFileExtensionsState(show);
    localStorage.setItem(STORAGE_KEYS.SHOW_EXTENSIONS, String(show));
  }, []);

  const setShowHiddenFiles = useCallback((show: boolean) => {
    setShowHiddenFilesState(show);
    localStorage.setItem(STORAGE_KEYS.SHOW_HIDDEN, String(show));
  }, []);

  return (
    <PreferencesContext.Provider
      value={{
        theme,
        effectiveTheme,
        setTheme,
        defaultFileView,
        setDefaultFileView,
        defaultTableDensity,
        setDefaultTableDensity,
        showFileExtensions,
        setShowFileExtensions,
        showHiddenFiles,
        setShowHiddenFiles,
        generalSettings,
        isLoading,
        refreshPreferences,
        updateGeneralPreferences,
      }}
    >
      {children}
    </PreferencesContext.Provider>
  );
};

export const usePreferences = (): PreferencesContextType => {
  const context = useContext(PreferencesContext);
  if (!context) {
    throw new Error("usePreferences must be used within a PreferencesProvider");
  }
  return context;
};
