<!-- Script. -->
<script setup>
    // Imports.
    import DefaultTheme from "vitepress/theme";
    import Hero from "../components/Hero.vue";
    import Footer from "../components/Footer.vue";

    // Extract the default layout.
    const { Layout } = DefaultTheme;
</script>

<!-- Template. -->
<template>
    <Layout>
        <!-- Insert the hero before the default home hero. -->
        <template #home-hero-before>
            <Hero />
        </template>

        <!-- Insert the footer after the home features. -->
        <template #home-features-after>
            <Footer />
        </template>
    </Layout>
</template>
