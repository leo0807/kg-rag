"use client";

interface CreateForm {
  username: string; password: string; full_name: string;
  department: string; email: string; is_admin: boolean;
}

interface Props {
  form:    CreateForm;
  creating: boolean;
  onChange: (f: CreateForm) => void;
  onCreate: () => void;
  onCancel: () => void;
}

const INPUT = "w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 outline-none focus:border-indigo-500";

export function CreateUserPanel({ form, creating, onChange, onCreate, onCancel }: Props) {
  const set = (patch: Partial<CreateForm>) => onChange({ ...form, ...patch });

  return (
    <div className="bg-gray-900 border border-indigo-700/50 rounded-2xl p-4 sm:p-5 space-y-4">
      <h3 className="text-sm font-semibold text-white">新建用户</h3>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">工号 <span className="text-red-400">*</span></label>
          <input value={form.username} onChange={e => set({ username: e.target.value })}
            placeholder="6位数字工号" maxLength={6} className={INPUT} />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">初始密码 <span className="text-red-400">*</span></label>
          <input type="password" value={form.password} onChange={e => set({ password: e.target.value })}
            placeholder="至少6位" className={INPUT} />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">姓名</label>
          <input value={form.full_name} onChange={e => set({ full_name: e.target.value })}
            placeholder="真实姓名" className={INPUT} />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">部门</label>
          <input value={form.department} onChange={e => set({ department: e.target.value })}
            placeholder="所在部门" className={INPUT} />
        </div>
        <div className="sm:col-span-2">
          <label className="text-xs text-gray-500 mb-1 block">邮箱</label>
          <input type="email" value={form.email} onChange={e => set({ email: e.target.value })}
            placeholder="工作邮箱（选填）" className={INPUT} />
        </div>
      </div>
      <div className="pt-1">
        <div className="text-xs text-gray-500 mb-2">用户权限</div>
        <div className="flex flex-col gap-3 sm:flex-row">
          {[{ value: false, label: "普通用户", desc: "可查询、浏览文档" }, { value: true, label: "管理员", desc: "全部权限 + 用户管理" }].map(opt => (
            <label key={String(opt.value)}
              className={`flex items-start gap-2.5 flex-1 p-3 rounded-lg border cursor-pointer transition-colors ${
                form.is_admin === opt.value ? "border-indigo-600 bg-indigo-600/10" : "border-gray-700 hover:border-gray-600"
              }`}>
              <input type="radio" name="is_admin" checked={form.is_admin === opt.value}
                onChange={() => set({ is_admin: opt.value })} className="mt-0.5 accent-indigo-600" />
              <div>
                <div className="text-sm text-gray-200">{opt.label}</div>
                <div className="text-xs text-gray-500 mt-0.5">{opt.desc}</div>
              </div>
            </label>
          ))}
        </div>
      </div>
      <div className="flex gap-2 pt-1">
        <button type="button" onClick={onCreate} disabled={creating}
          className="px-5 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-500 disabled:opacity-40">
          {creating ? "创建中..." : "创建用户"}
        </button>
        <button type="button" onClick={onCancel}
          className="px-4 py-2 bg-gray-800 text-gray-400 text-sm rounded-lg hover:text-white">
          取消
        </button>
      </div>
    </div>
  );
}
