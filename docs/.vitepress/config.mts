// Imports.
import { defineConfig } from "vitepress";


// The site configuration.
export default defineConfig({
    // The site metadata.
    title: "sandbox",
    description: "Isolated development boxes for local projects.",
    lang: "en-US",

    // The URL and build behavior.
    cleanUrls: true,

    // Keep repository agent configuration out of the public site.
    srcExclude: ["agents/**"],
    lastUpdated: true,
    sitemap: {
        hostname: "https://sandbox.mihaiconstantin.com"
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
        logo: "/sandbox-logo.png",
        siteTitle: "sandbox",

        // The top navigation.
        nav: [
            { text: "Guide", link: "/guide/installation" },
            { text: "GitHub", link: "https://github.com/mihaiconstantin/sandbox" }
        ],

        // The guide sidebar.
        sidebar: {
            "/guide/": [
                {
                    text: "Guide",
                    items: [
                        { text: "Installation", link: "/guide/installation" }
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
            pattern: "https://github.com/mihaiconstantin/sandbox/edit/main/docs/:path",
            text: "Edit this page on GitHub"
        },

        // The social links.
        socialLinks: [
            { icon: "github", link: "https://github.com/mihaiconstantin/sandbox" }
        ]
    }
});
