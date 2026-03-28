"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
    const router = useRouter();
    const [tab, setTab] = useState<"login" | "register">("login");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const [loginForm, setLoginForm] = useState({
        username: "",
        password: "",
    });

    const [registerForm, setRegisterForm] = useState({
        username: "",
        email: "",
        password: "",
        full_name: "",
        department: "",
    });

    async function handleLogin() {
        setLoading(true);
        setError("");
        try {
            const res = await fetch("/api/auth/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(loginForm),
            });
            const data = await res.json();
            if (!res.ok) {
                setError(data.detail || "登录失败");
                return;
            }
            localStorage.setItem("token", data.access_token);
            localStorage.setItem("user", JSON.stringify(data));
            router.push("/ingest");
        } finally {
            setLoading(false);
        }
    }

    async function handleRegister() {
        setLoading(true);
        setError("");
        try {
            const res = await fetch("/api/auth/register", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(registerForm),
            });
            const data = await res.json();
            if (!res.ok) {
                setError(data.detail || "注册失败");
                return;
            }
            localStorage.setItem("token", data.access_token);
            localStorage.setItem("user", JSON.stringify(data));
            router.push("/ingest");
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="flex items-center justify-center min-h-screen px-4">
            <div className="w-full max-w-md">

                {/* Logo */}
                <div className="text-center mb-8">
                    <div className="text-2xl font-bold text-white mb-1">CPS 知识库</div>
                    <div className="text-sm text-gray-500">航空工艺规范智能问答系统</div>
                </div>

                {/* 卡片 */}
                <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8">

                    {/* Tab */}
                    <div className="flex gap-1 bg-gray-800 rounded-lg p-1 mb-6">
                        {(["login", "register"] as const).map(t => (
                            <button
                                key={t}
                                onClick={() => { setTab(t); setError(""); }}
                                className={`flex-1 py-1.5 rounded-md text-sm transition-colors ${tab === t
                                    ? "bg-indigo-600 text-white"
                                    : "text-gray-400 hover:text-white"
                                    }`}
                            >
                                {t === "login" ? "登录" : "注册"}
                            </button>
                        ))}
                    </div>

                    {/* 错误提示 */}
                    {error && (
                        <div className="mb-4 px-3 py-2 bg-red-500/10 border border-red-500/30
                            rounded-lg text-sm text-red-400">
                            {error}
                        </div>
                    )}

                    {/* 登录表单 */}
                    {tab === "login" && (
                        <div className="space-y-4">
                            <div>
                                <label className="text-xs text-gray-500 mb-1 block">工号</label>
                                <input
                                    value={loginForm.username}
                                    onChange={e => setLoginForm(f => ({ ...f, username: e.target.value }))}
                                    placeholder="6位工号"
                                    maxLength={6}
                                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700
                             rounded-lg text-sm text-gray-200 outline-none
                             focus:border-indigo-500"
                                />
                            </div>
                            <div>
                                <label className="text-xs text-gray-500 mb-1 block">密码</label>
                                <input
                                    type="password"
                                    value={loginForm.password}
                                    onChange={e => setLoginForm(f => ({ ...f, password: e.target.value }))}
                                    placeholder="请输入密码"
                                    onKeyDown={e => e.key === "Enter" && handleLogin()}
                                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700
                             rounded-lg text-sm text-gray-200 outline-none
                             focus:border-indigo-500"
                                />
                            </div>
                            <button
                                onClick={handleLogin}
                                disabled={loading || !loginForm.username || !loginForm.password}
                                className="w-full py-2 bg-indigo-600 text-white text-sm rounded-lg
                           hover:bg-indigo-500 disabled:opacity-40 transition-colors"
                            >
                                {loading ? "登录中..." : "登录"}
                            </button>
                        </div>
                    )}

                    {/* 注册表单 */}
                    {tab === "register" && (
                        <div className="space-y-4">
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="text-xs text-gray-500 mb-1 block">工号</label>
                                    <input
                                        value={registerForm.username}
                                        onChange={e => setRegisterForm(f => ({ ...f, username: e.target.value }))}
                                        placeholder="6位数字工号"
                                        maxLength={6}
                                        className="w-full px-3 py-2 bg-gray-800 border border-gray-700
                               rounded-lg text-sm text-gray-200 outline-none
                               focus:border-indigo-500"
                                    />
                                </div>
                                <div>
                                    <label className="text-xs text-gray-500 mb-1 block">姓名</label>
                                    <input
                                        value={registerForm.full_name}
                                        onChange={e => setRegisterForm(f => ({ ...f, full_name: e.target.value }))}
                                        placeholder="真实姓名"
                                        className="w-full px-3 py-2 bg-gray-800 border border-gray-700
                               rounded-lg text-sm text-gray-200 outline-none
                               focus:border-indigo-500"
                                    />
                                </div>
                            </div>
                            <div>
                                <label className="text-xs text-gray-500 mb-1 block">部门</label>
                                <input
                                    value={registerForm.department}
                                    onChange={e => setRegisterForm(f => ({ ...f, department: e.target.value }))}
                                    placeholder="所在部门"
                                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700
                             rounded-lg text-sm text-gray-200 outline-none
                             focus:border-indigo-500"
                                />
                            </div>
                            <div>
                                <label className="text-xs text-gray-500 mb-1 block">邮箱</label>
                                <input
                                    type="email"
                                    value={registerForm.email}
                                    onChange={e => setRegisterForm(f => ({ ...f, email: e.target.value }))}
                                    placeholder="工作邮箱"
                                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700
                             rounded-lg text-sm text-gray-200 outline-none
                             focus:border-indigo-500"
                                />
                            </div>
                            <div>
                                <label className="text-xs text-gray-500 mb-1 block">密码</label>
                                <input
                                    type="password"
                                    value={registerForm.password}
                                    onChange={e => setRegisterForm(f => ({ ...f, password: e.target.value }))}
                                    placeholder="至少6位"
                                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700
                             rounded-lg text-sm text-gray-200 outline-none
                             focus:border-indigo-500"
                                />
                            </div>
                            <button
                                onClick={handleRegister}
                                disabled={loading || !registerForm.username || !registerForm.password}
                                className="w-full py-2 bg-indigo-600 text-white text-sm rounded-lg
                           hover:bg-indigo-500 disabled:opacity-40 transition-colors"
                            >
                                {loading ? "注册中..." : "注册"}
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}