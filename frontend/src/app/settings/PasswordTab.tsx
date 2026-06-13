"use client";

import { useState } from "react";
import { fetchApi, ApiError } from "@/lib/api";

interface Props {
  showMsg: (m: string) => void;
  showError: (e: string) => void;
}

export function PasswordTab({ showMsg, showError }: Props) {
  const [pwForm, setPwForm] = useState({
    old_password: "",
    new_password: "",
    confirm: "",
  });

  async function save() {
    if (pwForm.new_password !== pwForm.confirm) {
      showError("两次密码不一致");
      return;
    }
    try {
      await fetchApi("/api/auth/password", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          old_password: pwForm.old_password,
          new_password: pwForm.new_password,
        }),
      });
      showMsg("密码修改成功");
      setPwForm({ old_password: "", new_password: "", confirm: "" });
    } catch (e) {
      showError(e instanceof ApiError ? e.message : "修改失败");
    }
  }

  return (
    <div className="space-y-4 bg-gray-900 rounded-2xl p-4 sm:p-5 border border-gray-800">
      {[
        { key: "old_password", label: "原密码", placeholder: "请输入原密码" },
        { key: "new_password", label: "新密码", placeholder: "至少6位" },
        { key: "confirm", label: "确认新密码", placeholder: "再次输入新密码" },
      ].map((field) => {
        const inputId = `password-${field.key}`;
        return (
          <div key={field.key}>
            <label
              htmlFor={inputId}
              className="text-xs text-gray-500 mb-1 block"
            >
              {field.label}
            </label>
            <input
              id={inputId}
              type="password"
              value={pwForm[field.key as keyof typeof pwForm]}
              onChange={(e) =>
                setPwForm((f) => ({ ...f, [field.key]: e.target.value }))
              }
              placeholder={field.placeholder}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 outline-none focus:border-indigo-500"
            />
          </div>
        );
      })}
      <button
        type="button"
        onClick={save}
        className="px-5 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-500"
      >
        修改密码
      </button>
    </div>
  );
}
