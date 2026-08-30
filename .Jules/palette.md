## 2024-08-30 - Added progress bar to pacman-wrapper
**Learning:** Terminal output needs a fallback (NO_COLOR) for accessibility and machine readability when adding visual UI components like progress bars. Using `#` and `-` characters is simple and easily read by screen readers.
**Action:** When adding CLI visual elements, ensure they gracefully degrade when color/formatting isn't supported and use accessible text characters.
