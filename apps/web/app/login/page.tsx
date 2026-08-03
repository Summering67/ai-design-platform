"use client";

import { FormEvent, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { login } from "../workspace/chat-api";

const LoginPage = () => {
  const router = useRouter();
  const search = useSearchParams();
  const [email, setEmail] = useState("developer@local.test");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    try {
      await login(email, password);
      router.replace(search.get("next") || "/workspace");
    } catch {
      setError("邮箱或密码错误");
    }
  };
  return (
    <main className="mx-auto flex min-h-screen max-w-sm items-center px-6">
      <form
        className="w-full space-y-4"
        onSubmit={(event) => void submit(event)}
      >
        <h1 className="text-2xl font-semibold">登录</h1>
        <label className="block space-y-1">
          <span>邮箱</span>
          <input
            className="w-full rounded border p-2"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
        <label className="block space-y-1">
          <span>密码</span>
          <input
            className="w-full rounded border p-2"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {error ? <p role="alert">{error}</p> : null}
        <button
          className="w-full rounded bg-black p-2 text-white"
          type="submit"
        >
          登录
        </button>
      </form>
    </main>
  );
};
export default LoginPage;
