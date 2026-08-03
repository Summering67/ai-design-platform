"use client";

import { useRouter } from "next/navigation";

import { Home } from "@repo/ui/blocks/home";

const HomePage = () => {
  const router = useRouter();

  return (
    <Home
      onPromptSubmit={(prompt) => {
        sessionStorage.setItem("aidp-prompt", prompt);
        router.push(`/workspace?prompt=${encodeURIComponent(prompt)}`);
      }}
    />
  );
};

export default HomePage;
