// Imports.
import type { Theme } from "vitepress";
import DefaultTheme from "vitepress/theme";

// Import the custom layout.
import Layout from "./layouts/Layout.vue";

// Import the custom styles.
import "../assets/css/styles.css";


// Export the custom theme.
export default {
    // Extend the default theme.
    extends: DefaultTheme,

    // Provide the custom layout.
    Layout: Layout
} satisfies Theme;
