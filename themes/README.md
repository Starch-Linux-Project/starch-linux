# Starch COSMIC themes

For COSMIC Settings exports, use `<folder>/<folder>-dark.ron` and/or
`<folder>/<folder>-light.ron`. The palette name is the label in Appearance.
The build uses COSMIC Settings' headless importer to render the system presets.
Set `default.txt` here to the export folder for new accounts. Starch starts
in dark mode and seeds both variants when supplied. Users can switch or
customize the theme normally after account creation.

Put native system bundles in a folder named for their wallpaper. For example,
`themes/meridian/` pairs with `wallpapers/meridian.jpg`. Matching uses the
folder name and image filename without its extension, ignoring case. Each
matching name must identify a single image across the wallpaper collection.

Place the native `com.system76.CosmicThemeBundle.<slug>.Theme` and matching
`.Builder` directories directly inside the folder. Include the upstream
`.Package` metadata and `LICENSE` files when supplied. Multiple bundles in one
folder (such as dark and light variants) share the same wallpaper.

The build writes the staged image path into each matching bundle's
`.Background/v1/base`. Without a matching image, supply the bundle's own
`.Background` directory. The account's first-login wallpaper is selected
separately by `wallpapers/default.txt`.
