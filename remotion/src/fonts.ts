import { staticFile } from "remotion";

/**
 * Registers the four brand families.
 *
 * The Inter double-registration is deliberate and load-bearing: the .ttf on disk
 * reports its family as "Inter 24pt" (Google now ships optical sizes, not
 * weights), while the built diagram SVGs in 02_Vector_Library reference plain
 * "Inter". Registering both names means either resolves — without this, diagram
 * label text silently falls back to a substitute face.
 */
export const registerFonts = (): void => {
  const face = (family: string, file: string, weight = 400) => `
    @font-face {
      font-family: "${family}";
      src: url("${staticFile(`fonts/${file}`)}") format("truetype");
      font-weight: ${weight};
      font-display: block;
    }`;

  const css = [
    face("Space Grotesk", "SpaceGrotesk-Medium.ttf", 500),
    face("Space Grotesk", "SpaceGrotesk-Bold.ttf", 700),
    face("Inter", "Inter_24pt-Regular.ttf"),
    face("Inter 24pt", "Inter_24pt-Regular.ttf"), // alias — see docstring
    face("Fira Code", "FiraCode-Regular.ttf"),
    face("Fira Code", "FiraCode-Bold.ttf", 700),
    face("JetBrains Mono", "JetBrainsMono-Regular.ttf"),
    face("JetBrains Mono", "JetBrainsMono-Bold.ttf", 700),
  ].join("\n");

  const el = document.createElement("style");
  el.textContent = css;
  document.head.appendChild(el);
};
