<!-- Script. -->
<script setup>
    // Imports.
    import { useRouter } from "vitepress";

    // Get the router instance.
    const router = useRouter();

    // Navigate to the installation guide.
    const getStarted = () => {
        router.go("/guide/installation");
    };
</script>

<!-- Template. -->
<template>
    <div
        id="hero"
        class="mt-16 mb-16 border-0 px-6 sm:px-12 vp-lg:mt-20 vp-lg:mb-21 vp-lg:px-16"
    >
        <div class="mx-auto max-w-6xl border-0">
            <div
                class="flex flex-col-reverse items-center gap-10 border-0 vp-lg:flex-row vp-lg:gap-25"
            >
                <!-- The title and description. -->
                <div
                    class="flex w-full flex-col items-center border-0 text-center vp-lg:w-142.5 vp-lg:items-start vp-lg:text-left"
                >
                    <!-- The title. -->
                    <h1
                        class="title font-sandbox from-sandbox-500 dark:from-sandbox-400 mb-1.5 bg-linear-to-r from-[50px] to-(--vp-c-text-1) to-[80px] bg-clip-text text-5xl font-bold text-transparent"
                    >
                        sandbox
                    </h1>

                    <!-- The description. -->
                    <div
                        class="mb-3 w-full border-0 text-3xl leading-10 font-light xs:max-md:w-100 md:max-vp-lg:w-125 vp-lg:text-5xl vp-lg:leading-14"
                    >
                        Isolated Boxes for Local Projects
                    </div>

                    <!-- The tagline. -->
                    <div
                        class="w-full border-0 text-lg leading-8 font-light text-(--vp-c-text-2) xs:max-md:w-100 md:max-vp-lg:w-125 vp-lg:text-2xl vp-lg:leading-9"
                    >
                        Mount a host directory into a box built from reusable
                        Docker recipes to run tools, scripts, and AI agents off
                        your operating system.
                    </div>

                    <!-- The action button. -->
                    <div class="mt-6 border-0 select-none">
                        <button
                            class="bg-sandbox-500 hover:bg-sandbox-600 active:bg-sandbox-700 rounded-3xl px-5 py-2 leading-6 text-sm font-semibold text-(--vp-button-brand-text) transition-colors duration-250"
                            type="button"
                            @click="getStarted"
                        >
                            Get Started
                        </button>
                    </div>
                </div>

                <!-- The logo. -->
                <div
                    class="logo relative w-52.5 -rotate-3 border-0 vp-lg:w-62.5"
                >
                    <div
                        class="logo-background absolute inset-10 -z-10 border-0 bg-[linear-gradient(-45deg,var(--color-sandbox-200)_10%,var(--color-sandbox-400)_10%)] blur-[45px] dark:inset-8 dark:blur-[70px]"
                    ></div>
                    <img
                        class="mx-auto w-80 max-w-full rounded-4xl drop-shadow-xl select-none dark:drop-shadow-xl"
                        src="/images/sandbox-logo.png"
                        alt="sandbox logo"
                        draggable="false"
                    />
                </div>
            </div>
        </div>
    </div>
</template>
