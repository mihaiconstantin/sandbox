// Imports.
import type { Theme } from "vitepress";
import DefaultTheme from "vitepress/theme";

// Import the custom layout.
import Layout from "./layouts/Layout.vue";

// Import the custom components.
import Sandbox from "./components/Sandbox.vue";

// Import the custom styles.
import "../assets/css/styles.css";


// Export the custom theme.
export default {
    // Extend the default theme.
    extends: DefaultTheme,

    // Provide the custom layout.
    Layout: Layout,

    // Register the components available in Markdown.
    enhanceApp({ app }) {
        app.component("Sandbox", Sandbox);
    }
} satisfies Theme;
