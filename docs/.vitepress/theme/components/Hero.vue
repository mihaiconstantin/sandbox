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
        class="mt-16 mb-16 border-0 px-[24px] min-[640px]:px-[48px] min-[960px]:mt-20 min-[960px]:mb-21 min-[960px]:px-[64px]"
    >
        <div class="mx-auto max-w-[1152px] border-0">
            <div
                class="flex flex-col-reverse items-center gap-10 border-0 min-[960px]:flex-row min-[960px]:gap-25"
            >
                <!-- The title and description. -->
                <div
                    class="flex w-full flex-col items-center border-0 text-center min-[960px]:w-[570px] min-[960px]:items-start min-[960px]:text-left"
                >
                    <!-- The title. -->
                    <h1
                        class="title font-sandbox from-sandbox-500 dark:from-sandbox-400 !mb-[6px] bg-gradient-to-r from-[50px] to-[var(--vp-c-text-1)] to-[80px] bg-clip-text !text-5xl !font-bold text-transparent"
                    >
                        sandbox
                    </h1>

                    <!-- The description. -->
                    <div
                        class="mb-3 w-full border-0 text-3xl leading-10 font-light min-[460px]:max-[768px]:w-[400px] min-[768px]:max-[960px]:w-[500px] min-[960px]:text-5xl min-[960px]:leading-14"
                    >
                        Isolated Boxes for Local Projects
                    </div>

                    <!-- The tagline. -->
                    <div
                        class="w-full border-0 text-lg leading-8 font-light text-[var(--vp-c-text-2)] min-[460px]:max-[768px]:w-[400px] min-[768px]:max-[960px]:w-[500px] min-[960px]:text-2xl min-[960px]:leading-9"
                    >
                        Mount a host directory into a box built from reusable
                        Docker recipes to run tools, scripts, and AI agents off
                        your operating system.
                    </div>

                    <!-- The action button. -->
                    <div class="mt-6 border-0 select-none">
                        <button
                            class="!bg-sandbox-500 hover:!bg-sandbox-600 active:!bg-sandbox-700 rounded-3xl !px-5 !py-2 text-sm font-[600] !text-[var(--vp-button-brand-text)] transition-colors duration-[250ms]"
                            type="button"
                            @click="getStarted"
                        >
                            Get Started
                        </button>
                    </div>
                </div>

                <!-- The logo. -->
                <div
                    class="logo relative w-[210px] -rotate-3 border-0 min-[960px]:w-[250px]"
                >
                    <div
                        class="logo-background absolute inset-10 -z-10 border-0 bg-[linear-gradient(-45deg,var(--color-sandbox-200)_10%,var(--color-sandbox-400)_10%)] blur-[45px] dark:inset-8 dark:blur-[70px]"
                    ></div>
                    <img
                        class="mx-auto w-[320px] max-w-[320px] rounded-[2rem] drop-shadow-2xl select-none dark:drop-shadow-xl"
                        src="/sandbox-logo.png"
                        alt="sandbox logo"
                        draggable="false"
                    />
                </div>
            </div>
        </div>
    </div>
</template>
