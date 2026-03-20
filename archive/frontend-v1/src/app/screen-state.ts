import type { ScreenKey } from '../types/console';

export const screens: Array<{ key: ScreenKey; label: string; stage: string }> = [
  { key: 'stage-1', label: 'Scenario Setup', stage: '01' },
  { key: 'stage-2', label: 'Population Sampling', stage: '02' },
  { key: 'stage-3', label: 'Simulation', stage: '03' },
  { key: 'stage-4-report', label: 'Full Report', stage: '04A' },
  { key: 'stage-4-opinions', label: 'Opinions Feed', stage: '04B' },
  { key: 'stage-4-friction', label: 'Friction Map', stage: '04C' },
  { key: 'stage-5-hub', label: 'Interaction Hub', stage: '05' },
];

const defaultScreen: ScreenKey = 'stage-1';

export function getScreenFromLocation(): ScreenKey {
  const raw = window.location.hash.replace('#', '').trim() as ScreenKey;
  return screens.some((screen) => screen.key === raw) ? raw : defaultScreen;
}

export function pushScreen(screen: ScreenKey): void {
  window.location.hash = screen;
}

export function getDefaultScreen(): ScreenKey {
  return defaultScreen;
}
