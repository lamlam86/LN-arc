"use client";

import * as React from "react";

import { SunMedium } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Slider } from "@/components/ui/slider";

const BRIGHT_KEY = "ln_brightness";
const MIN_BRIGHTNESS = 60;
const MAX_BRIGHTNESS = 120;

interface DisplaySettings {
  brightness: number;
  setBrightness: (value: number) => void;
}

const DisplaySettingsContext = React.createContext<DisplaySettings | null>(null);

function clampBrightness(value: number): number {
  if (!Number.isFinite(value)) return 100;
  return Math.min(MAX_BRIGHTNESS, Math.max(MIN_BRIGHTNESS, Math.round(value / 5) * 5));
}

export function DisplaySettingsProvider({ children }: { children: React.ReactNode }) {
  const [brightness, setBrightnessState] = React.useState(100);

  React.useEffect(() => {
    // Remove the old night-light preference; brightness is the only display setting.
    window.localStorage.removeItem("ln_night_light");
    const stored = Number(window.localStorage.getItem(BRIGHT_KEY) ?? "100");
    setBrightnessState(clampBrightness(stored));
  }, []);

  const setBrightness = React.useCallback((value: number) => {
    const next = clampBrightness(value);
    setBrightnessState(next);
    window.localStorage.setItem(BRIGHT_KEY, String(next));
  }, []);

  const dimOpacity = brightness < 100 ? ((100 - brightness) / 100) * 0.55 : 0;
  const brightOpacity = brightness > 100 ? ((brightness - 100) / 100) * 0.35 : 0;

  return (
    <DisplaySettingsContext.Provider value={{ brightness, setBrightness }}>
      {children}
      {/* Brightness overlay: darkens below 100%, lifts above 100%. */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-[9999] transition-opacity duration-300"
        style={{
          backgroundColor: brightness < 100 ? "#000" : "#fff",
          opacity: brightness < 100 ? dimOpacity : brightOpacity,
          mixBlendMode: brightness < 100 ? "multiply" : "screen",
        }}
      />
    </DisplaySettingsContext.Provider>
  );
}

export function useDisplaySettings(): DisplaySettings {
  const settings = React.useContext(DisplaySettingsContext);
  if (!settings) throw new Error("useDisplaySettings must be used inside DisplaySettingsProvider");
  return settings;
}

export function DisplaySettingsControl() {
  const { brightness, setBrightness } = useDisplaySettings();

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button size="icon" variant="ghost" aria-label="Screen brightness" title="Screen brightness">
          <SunMedium className="size-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-64">
        <div className="space-y-3">
          <div>
            <h4 className="font-medium text-sm">Brightness</h4>
            <p className="text-muted-foreground text-xs">Adjust the screen brightness of the app.</p>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-sm">Level</Label>
              <span className="text-muted-foreground text-xs tabular-nums">{brightness}%</span>
            </div>
            <Slider
              value={[brightness]}
              min={MIN_BRIGHTNESS}
              max={MAX_BRIGHTNESS}
              step={5}
              onValueChange={([value]) => setBrightness(value)}
            />
            <div className="flex justify-between text-[10px] text-muted-foreground">
              <span>Dimmer</span>
              <span>Brighter</span>
            </div>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
