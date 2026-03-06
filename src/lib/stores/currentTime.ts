import { readable } from 'svelte/store';

function decimalHour(): number {
    const now = new Date();
    return now.getHours() + now.getMinutes() / 60;
}

export const currentDecimalHour = readable(decimalHour(), (set) => {
    const interval = setInterval(() => set(decimalHour()), 60000);
    return () => clearInterval(interval);
});