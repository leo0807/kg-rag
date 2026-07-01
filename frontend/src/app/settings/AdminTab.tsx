"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchApi, ApiError } from "@/lib/api";
import type { UserRow } from "./types";
import { CreateUserPanel } from "./CreateUserPanel";
import { ResetPasswordModal } from "./ResetPasswordModal";

interface Props { showMsg: (m: string) => void; showError: (e: string) => void }

const EMPTY_FORM = { username: "", password: "", full_name: "", department: "", email: "", is_admin: false };

export function AdminTab({ showMsg, showError }: Props) {
  const [users,       setUsers]       = useState<UserRow[]>([]);
  const [showCreate,  setShowCreate]  = useState(false);
  const [createForm,  setCreateForm]  = useState(EMPTY_FORM);
  const [creating,    setCreating]    = useState(false);
  const [resetTarget, setResetTarget] = useState<UserRow | null>(null);
  const [resetPw,     setResetPw]     = useState("");
  const [resetting,   setResetting]   = useState(false);

  const loadUsers = useCallback(async () => {
    try { setUsers(await fetchApi<UserRow[]>("/api/users")); } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadUsers(); }, [loadUsers]);

  async function toggleUser(id: string) {
    try { await fetchApi(`/api/users/${id}/toggle`, { method: "PUT" }); loadUsers(); showMsg("操作成功"); }
    catch { showError("操作失败"); }
  }

  async function toggleAdmin(id: string) {
    try { await fetchApi(`/api/users/${id}/admin`, { method: "PUT" }); loadUsers(); showMsg("操作成功"); }
    catch { showError("操作失败"); }
  }

  async function createUser() {
    if (!createForm.username || !createForm.password) { showError("工号和密码为必填项"); return; }
    setCreating(true);
    try {
      const data = await fetchApi<{ username: string }>("/api/users", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(createForm),
      });
      showMsg(`用户 ${data.username} 创建成功`);
      setShowCreate(false); setCreateForm(EMPTY_FORM); await loadUsers();
    } catch (e) { showError(e instanceof ApiError ? e.message : "创建失败"); }
    finally { setCreating(false); }
  }

  async function doReset() {
    if (!resetTarget || !resetPw.trim()) return;
    if (resetPw.length < 6) { showError("密码至少6位"); return; }
    setResetting(true);
    try {
      await fetchApi(`/api/users/${resetTarget.user_id}/reset-password`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_password: resetPw }),
      });
      showMsg(`已重置 ${resetTarget.username} 的密码`);
      setResetTarget(null); setResetPw("");
    } catch (e) { showError(e instanceof ApiError ? e.message : "重置失败"); }
    finally { setResetting(false); }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <span className="text-sm text-gray-500">共 {users.length} 个用户</span>
        <button type="button" onClick={() => { setShowCreate(v => !v); setCreateForm(EMPTY_FORM); }}
          className="px-4 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-500 transition-colors">
          + 新建用户
        </button>
      </div>

      {showCreate && (
        <CreateUserPanel form={createForm} creating={creating}
          onChange={setCreateForm} onCreate={createUser} onCancel={() => setShowCreate(false)} />
      )}

      {resetTarget && (
        <ResetPasswordModal target={resetTarget} password={resetPw} resetting={resetting}
          onChange={setResetPw} onConfirm={doReset} onCancel={() => { setResetTarget(null); setResetPw(""); }} />
      )}

      <div className="bg-gray-900 rounded-2xl border border-gray-800 overflow-x-auto">
        <table className="min-w-[760px] w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 text-gray-400 text-left">
              {["工号","姓名","部门","权限","状态","操作"].map(h => <th key={h} className="px-4 py-3">{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.user_id} className="border-b border-gray-800/50 hover:bg-gray-800/20">
                <td className="px-4 py-3 font-mono text-gray-300">{u.username}</td>
                <td className="px-4 py-3 text-gray-300">{u.full_name || "—"}</td>
                <td className="px-4 py-3 text-gray-400">{u.department || "—"}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded text-xs ${u.is_admin ? "bg-indigo-500/20 text-indigo-400" : "bg-gray-700 text-gray-400"}`}>
                    {u.is_admin ? "管理员" : "普通用户"}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded text-xs ${u.is_active ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
                    {u.is_active ? "启用" : "禁用"}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1.5">
                    <button type="button" onClick={() => toggleUser(u.user_id)}
                      className="px-2 py-1 bg-gray-800 text-gray-400 text-xs rounded hover:text-white transition-colors">
                      {u.is_active ? "禁用" : "启用"}
                    </button>
                    <button type="button" onClick={() => toggleAdmin(u.user_id)}
                      className="px-2 py-1 bg-gray-800 text-gray-400 text-xs rounded hover:text-white transition-colors">
                      {u.is_admin ? "撤销管理员" : "设管理员"}
                    </button>
                    <button type="button" onClick={() => { setResetTarget(u); setResetPw(""); }}
                      className="px-2 py-1 bg-gray-800 text-amber-500/70 text-xs rounded hover:text-amber-400 transition-colors">
                      重置密码
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
