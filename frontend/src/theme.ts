// Read the same design tokens used by CSS for WebGL and map layers.
export const themeColor = (token: string) =>
  getComputedStyle(document.documentElement).getPropertyValue('--' + token).trim()
