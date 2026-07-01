"use client";

export function GNNInstructions() {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-3">
      <h2 className="font-semibold text-white">使用说明</h2>
      <ol className="text-sm text-gray-400 space-y-2 list-decimal list-inside">
        <li>确保已导入文档（图谱中有 Section 节点和 Milvus 文本嵌入）</li>
        <li>点击「开始训练」，后台运行 GraphSAGE 训练（约 5–20 分钟，取决于数据量）</li>
        <li>训练完成后 GNN 嵌入自动热加载，无需重启服务</li>
        <li>在智能问答中将检索策略切换为 <code className="bg-gray-800 px-1.5 py-0.5 rounded">gnn</code>，
          即可享受结构感知检索（邻居类型分布 + 关系密度融入节点 Embedding）</li>
      </ol>
      <div className="mt-2 p-3 bg-gray-800/60 rounded-lg text-xs text-gray-500 space-y-1">
        <div className="text-gray-300 font-medium mb-1">技术细节</div>
        <div>• 节点特征: BGE-M3 文本嵌入 (1024 维) + 结构特征 (16 维: 实体数量、doc_type one-hot 等)</div>
        <div>• 架构: 2 层 GraphSAGE，Mean 聚合，输出 1024 维 L2 归一化嵌入</div>
        <div>• 邻接: HAS_SUBSECTION + NEXT_SECTION + 共享实体边 + SIMILAR_TO</div>
        <div>• 训练目标: InfoNCE 对比损失，同文档章节为正样本对</div>
        <div>• 检索: 用 BGE-M3 查询嵌入与 GNN 节点嵌入做内积（余弦相似度），再与全文检索 RRF 融合</div>
      </div>
    </div>
  );
}
