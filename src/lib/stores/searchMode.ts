import { writable } from 'svelte/store';

export type SearchMode = 'routes' | 'location';

// Load initial mode from localStorage
const storedMode = typeof window !== 'undefined'
  ? (localStorage.getItem('searchMode') as SearchMode) || 'routes'
  : 'routes';

export const searchMode = writable<SearchMode>(storedMode);

// Persist to localStorage on change
if (typeof window !== 'undefined') {
  searchMode.subscribe(mode => {
    localStorage.setItem('searchMode', mode);
  });
}
