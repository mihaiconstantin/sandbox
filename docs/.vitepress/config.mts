// Imports.
import { defineConfig } from "vitepress";


// The site configuration.
export default defineConfig({
    // The site metadata.
    title: "sandbox",
    description: "Isolated development environments for local projects.",
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
        ["link", { rel: "icon", href: "/sandbox-logo.png" }],
        ["meta", { name: "theme-color", content: "#ffffff" }]
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
