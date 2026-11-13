// Imports.
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vitepress";


// Define the website description string.
const description = "sandbox is a tool to create and manage isolated development boxes for local projects.";


// The site configuration.
export default defineConfig({
    // Website configuration.
    title: "sandbox",
    lang: "en-US",
    description: description,
    srcDir: "content",
    lastUpdated: true,
    cleanUrls: true,
    metaChunk: true,
    sitemap: {
        hostname: "https://sandbox.mihaiconstantin.com"
    },

    // `vite` configuration.
    vite: {
        // Plugins.
        plugins: [tailwindcss()]
    },

    // The document head.
    head: [
        // Icons links.
        ["link", { rel: "icon", href: "/favicon.ico", sizes: "any" }],
        ["link", { rel: "icon", type: "image/png", sizes: "32x32", href: "/favicon-32x32.png" }],
        ["link", { rel: "icon", type: "image/png", sizes: "16x16", href: "/favicon-16x16.png" }],
        ["link", { rel: "apple-touch-icon", sizes: "180x180", href: "/apple-touch-icon.png" }],
        ["link", { rel: "manifest", href: "/site.webmanifest" }],
        ["meta", { name: "theme-color", content: "#ffffff" }],
    ],

    // The theme configuration.
    themeConfig: {
        // The site branding.
        logo: "/images/sandbox-logo.png",
        siteTitle: "sandbox",

        // The top navigation.
        nav: [
            { text: "Guide", link: "/guide/overview" },
            { text: "GitHub", link: "https://github.com/mihaiconstantin/sandbox" }
        ],

        // The guide sidebar.
        sidebar: {
            "/guide/": [
                {
                    text: "Guide",
                    items: [
                        { text: "Overview", link: "/guide/overview" },
                        { text: "Installation", link: "/guide/installation" },
                        { text: "Usage", link: "/guide/usage" },
                    ]
                }
            ]
        },

        // The local search.
        search: {
            provider: "local"
        },

        // The page edit link.
        editLink: {
            pattern: "https://github.com/mihaiconstantin/sandbox/edit/main/docs/content/:path",
            text: "Edit this page on GitHub"
        }
    }
});
