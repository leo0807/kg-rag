"use client";

import { useEffect, useState } from "react";
import { getToken, type UserInfo } from "./types";

interface Props {
  showMsg: (m: string) => void;
  showError: (e: string) => void;
}

export function ProfileTab({ showMsg, showError }: Props) {
  const [profile, setProfile] = useState<UserInfo | null>(null);

  useEffect(() => {
    fetch("/api/auth/profile", {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => data && setProfile(data));
  }, []);

  async function save() {
    if (!profile) return;
    const res = await fetch("/api/auth/profile", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${getToken()}`,
      },
      body: JSON.stringify(profile),
    });
    if (res.ok) {
      const data = await res.json();
      const stored = JSON.parse(localStorage.getItem("user") ?? "{}");
      const nextUser = { ...stored, ...data };
      localStorage.setItem("user", JSON.stringify(nextUser));
      window.dispatchEvent(
        new CustomEvent("user-updated", { detail: nextUser }),
      );
      setProfile((prev) => (prev ? { ...prev, ...nextUser } : prev));
      showMsg("个人资料已保存");
    } else {
      const err = await res.json();
      showError(err.detail || "保存失败");
    }
  }

  if (!profile) return <div className="text-sm text-gray-500">加载中…</div>;

  return (
    <div className="space-y-4 bg-gray-900 rounded-2xl p-4 sm:p-5 border border-gray-800">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label
            htmlFor="profile-username"
            className="text-xs text-gray-500 mb-1 block"
          >
            工号
          </label>
          <input
            id="profile-username"
            value={profile.username}
            disabled
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-500 cursor-not-allowed"
          />
        </div>
        <div>
          <label
            htmlFor="profile-full-name"
            className="text-xs text-gray-500 mb-1 block"
          >
            姓名
          </label>
          <input
            id="profile-full-name"
            value={profile.full_name}
            onChange={(e) =>
              setProfile((p) => (p ? { ...p, full_name: e.target.value } : p))
            }
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 outline-none focus:border-indigo-500"
          />
        </div>
      </div>
      <div>
        <label
          htmlFor="profile-department"
          className="text-xs text-gray-500 mb-1 block"
        >
          部门
        </label>
        <input
          id="profile-department"
          value={profile.department}
          onChange={(e) =>
            setProfile((p) => (p ? { ...p, department: e.target.value } : p))
          }
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 outline-none focus:border-indigo-500"
        />
      </div>
      <div>
        <label
          htmlFor="profile-email"
          className="text-xs text-gray-500 mb-1 block"
        >
          邮箱
        </label>
        <input
          id="profile-email"
          type="email"
          value={profile.email}
          onChange={(e) =>
            setProfile((p) => (p ? { ...p, email: e.target.value } : p))
          }
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 outline-none focus:border-indigo-500"
        />
      </div>
      <button
        type="button"
        onClick={save}
        className="px-5 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-500"
      >
        保存
      </button>
    </div>
  );
}
