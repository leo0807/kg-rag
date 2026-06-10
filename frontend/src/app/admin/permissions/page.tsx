"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import { Shield, Users, Plus, X } from "lucide-react";

type RoleInfo = { id: string; name: string; display_name: string; description: string | null; is_system: boolean; permissions: string[] };
type UserInfo = { id: string; username: string; full_name: string; is_admin: boolean; roles: string[] };

const ROLE_COLOR: Record<string, string> = {
  super_admin: "bg-red-500/15 text-red-400 border-red-500/30",
  admin:       "bg-orange-500/15 text-orange-400 border-orange-500/30",
  editor:      "bg-blue-500/15 text-blue-400 border-blue-500/30",
  analyst:     "bg-purple-500/15 text-purple-400 border-purple-500/30",
  viewer:      "bg-green-500/15 text-green-400 border-green-500/30",
  guest:       "bg-gray-500/15 text-gray-400 border-gray-500/30",
};

type Tab = "roles" | "users";

export default function PermissionsPage() {
  const [tab, setTab] = useState<Tab>("roles");
  const [roles, setRoles] = useState<RoleInfo[]>([]);
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [selectedRole, setSelectedRole] = useState<RoleInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [assigning, setAssigning] = useState<string | null>(null); // user_id being edited
  const [newRole, setNewRole] = useState("");

  const loadRoles = useCallback(async () => {
    const d = await fetchApi<RoleInfo[]>("/api/admin/rbac/roles");
    if (d) setRoles(d);
  }, []);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    const d = await fetchApi<UserInfo[]>("/api/admin/rbac/users");
    if (d) setUsers(d);
    setLoading(false);
  }, []);

  useEffect(() => { loadRoles(); }, [loadRoles]);
  useEffect(() => { if (tab === "users") loadUsers(); }, [tab, loadUsers]);

  const assignRole = async (userId: string, roleName: string) => {
    await fetchApi(`/api/admin/rbac/users/${userId}/roles`, {
      method: "POST", body: JSON.stringify({ role_name: roleName }),
    });
    await loadUsers();
    setNewRole("");
    setAssigning(null);
  };

  const revokeRole = async (userId: string, roleName: string) => {
    await fetchApi(`/api/admin/rbac/users/${userId}/roles/${roleName}`, { method: "DELETE" });
    await loadUsers();
  };

  return (
    <div className="flex-1 overflow-hidden bg-gray-950 flex flex-col">
      <div className="p-5 border-b border-gray-800 shrink-0">
        <h1 className="text-xl font-semibold text-white flex items-center gap-2">
          <Shield size={20} className="text-blue-400" /> 权限管理
        </h1>
        <p className="text-sm text-gray-400 mt-0.5">RBAC 角色与权限配置</p>
      </div>

      <div className="flex gap-1 border-b border-gray-800 px-5 shrink-0">
        {(["roles", "users"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm border-b-2 transition-colors ${tab === t ? "border-blue-500 text-white" : "border-transparent text-gray-400 hover:text-gray-200"}`}>
            {t === "roles" ? "角色定义" : "用户角色"}
          </button>
        ))}
      </div>

      {tab === "roles" && (
        <div className="flex flex-1 overflow-hidden">
          <div className="w-64 border-r border-gray-800 overflow-y-auto">
            {roles.map((r) => (
              <button key={r.id} onClick={() => setSelectedRole(r)}
                className={`w-full text-left px-4 py-3 border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors ${selectedRole?.id === r.id ? "bg-gray-800" : ""}`}>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-white">{r.display_name}</span>
                  {r.is_system && <span className="text-[10px] text-gray-500">系统</span>}
                </div>
                <p className="text-xs text-gray-500 mt-0.5 truncate">{r.description}</p>
              </button>
            ))}
          </div>

          {selectedRole ? (
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className={`px-2 py-0.5 text-xs rounded border ${ROLE_COLOR[selectedRole.name] ?? "bg-gray-800 text-gray-400 border-gray-700"}`}>
                    {selectedRole.name}
                  </span>
                  <h2 className="text-base font-medium text-white">{selectedRole.display_name}</h2>
                </div>
                <p className="text-sm text-gray-400">{selectedRole.description}</p>
              </div>

              <div>
                <p className="text-xs font-medium text-gray-400 mb-2">已授予权限 ({selectedRole.permissions.length})</p>
                <div className="flex flex-wrap gap-1.5">
                  {selectedRole.permissions.sort().map((p) => (
                    <span key={p} className="px-2 py-0.5 text-xs rounded bg-gray-800 text-gray-300 font-mono">{p}</span>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-600 text-sm">
              选择左侧角色查看详情
            </div>
          )}
        </div>
      )}

      {tab === "users" && (
        <div className="flex-1 overflow-y-auto">
          {loading ? <p className="text-sm text-gray-500 p-5">加载中…</p> : (
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-gray-900 border-b border-gray-800">
                <tr className="text-left text-gray-400">
                  <th className="py-2 px-4 font-medium">用户</th>
                  <th className="py-2 px-4 font-medium">当前角色</th>
                  <th className="py-2 px-4 font-medium w-48">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/30">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-gray-900/50">
                    <td className="py-2.5 px-4">
                      <p className="text-white">{u.full_name || u.username}</p>
                      <p className="text-gray-500 text-[11px]">{u.username}</p>
                    </td>
                    <td className="py-2.5 px-4">
                      <div className="flex flex-wrap gap-1">
                        {u.is_admin && (
                          <span className="px-1.5 py-0.5 text-[11px] rounded border bg-red-500/10 text-red-400 border-red-500/20">
                            is_admin
                          </span>
                        )}
                        {u.roles.map((r) => (
                          <span key={r} className={`px-1.5 py-0.5 text-[11px] rounded border flex items-center gap-1 ${ROLE_COLOR[r] ?? "bg-gray-800 text-gray-400 border-gray-700"}`}>
                            {r}
                            <button onClick={() => revokeRole(u.id, r)} className="hover:text-white ml-0.5">
                              <X size={9} />
                            </button>
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-2.5 px-4">
                      {assigning === u.id ? (
                        <div className="flex items-center gap-1">
                          <select value={newRole} onChange={(e) => setNewRole(e.target.value)}
                            className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-white">
                            <option value="">选择角色</option>
                            {roles.filter((r) => !u.roles.includes(r.name)).map((r) => (
                              <option key={r.id} value={r.name}>{r.display_name}</option>
                            ))}
                          </select>
                          <button onClick={() => newRole && assignRole(u.id, newRole)}
                            disabled={!newRole}
                            className="p-1 rounded bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-40">
                            <Plus size={12} />
                          </button>
                          <button onClick={() => setAssigning(null)} className="p-1 rounded text-gray-400 hover:text-white">
                            <X size={12} />
                          </button>
                        </div>
                      ) : (
                        <button onClick={() => { setAssigning(u.id); setNewRole(""); }}
                          className="flex items-center gap-1 text-gray-400 hover:text-blue-400 transition-colors">
                          <Users size={12} /> 分配角色
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
