import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { useLanguage } from "@/context/LanguageContext";
import { apiClient } from "@/api/client";
export function AccountProfileEditor() {
  const { user, refreshProfile } = useAuth();
  const { currentLanguage } = useLanguage();
  const zh = currentLanguage === "zh-CN";
  const [email, setEmail] = useState(user?.email || "");
  const [nickname, setNickname] = useState(user?.nickname || "");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  return (
    <form
      className="space-y-3 mt-6"
      onSubmit={async (event) => {
        event.preventDefault();
        setBusy(true);
        setMessage("");
        try {
          await apiClient.patch("/api/auth/users/me/", {
            email,
            nickname,
            current_password: password,
          });
          await refreshProfile();
          setPassword("");
          setMessage(zh ? "账户资料已更新" : "Account updated");
        } catch {
          setMessage(
            zh
              ? "保存失败：请检查当前密码、邮箱是否已使用，以及网络连接。"
              : "Save failed. Check your current password, email availability and connection.",
          );
        } finally {
          setBusy(false);
        }
      }}
    >
      <h3 className="font-semibold">
        {zh ? "编辑账户资料" : "Edit account details"}
      </h3>
      <label className="block">
        {zh ? "邮箱" : "Email"}
        <input
          required
          type="email"
          autoComplete="email"
          className="block w-full border rounded p-2 bg-background"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </label>
      <label className="block">
        {zh ? "昵称" : "Display name"}
        <input
          maxLength={80}
          className="block w-full border rounded p-2 bg-background"
          value={nickname}
          onChange={(e) => setNickname(e.target.value)}
        />
      </label>
      <label className="block">
        {zh ? "当前密码" : "Current password"}
        <input
          required
          type="password"
          autoComplete="current-password"
          className="block w-full border rounded p-2 bg-background"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </label>
      <button
        disabled={busy}
        className="rounded bg-blue-600 text-white px-4 py-2"
      >
        {busy
          ? zh
            ? "保存中…"
            : "Saving…"
          : zh
            ? "保存账户资料"
            : "Save account details"}
      </button>
      <p role="status">{message}</p>
    </form>
  );
}
