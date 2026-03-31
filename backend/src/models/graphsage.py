"""
GraphSAGE 模型定义 (纯 PyTorch, 无需 PyG 依赖)

架构:
  - 2层 GraphSAGE，Mean 聚合
  - 输入: 节点特征 (文本嵌入 + 结构特征)
  - 输出: L2 归一化 embedding (与 BGE-M3 查询向量兼容)
"""
import torch
import torch.nn as nn
import torch.nn.functional as F


class SAGEConv(nn.Module):
    """单层 GraphSAGE 卷积（Mean 邻居聚合）"""

    def __init__(self, in_dim: int, out_dim: int):
        super().__init__()
        # 拼接 self + neighbor_mean 后做线性变换
        self.lin = nn.Linear(in_dim * 2, out_dim, bias=True)
        nn.init.xavier_uniform_(self.lin.weight)

    def forward(self, x: torch.Tensor, adj: torch.Tensor) -> torch.Tensor:
        """
        x:   [N, in_dim]  节点特征
        adj: [N, N] 稀疏 COO 张量（带自环，已 coalesce）
        """
        # 邻居 mean 聚合：度归一化防止高度节点梯度爆炸
        deg = torch.sparse.sum(adj, dim=1).to_dense().clamp(min=1.0).unsqueeze(1)
        agg = torch.sparse.mm(adj, x) / deg       # [N, in_dim]
        combined = torch.cat([x, agg], dim=1)      # [N, in_dim * 2]
        return F.relu(self.lin(combined))


class GraphSAGE(nn.Module):
    """
    2层 GraphSAGE:
      in_dim → hidden_dim → out_dim (L2 归一化)

    out_dim 默认与 BGE-M3 对齐 (1024)，使查询向量可直接与 GNN 嵌入做内积检索。
    """

    def __init__(
        self,
        in_dim: int,
        hidden_dim: int = 512,
        out_dim: int = 1024,
        dropout: float = 0.2,
    ):
        super().__init__()
        self.conv1 = SAGEConv(in_dim, hidden_dim)
        self.conv2 = SAGEConv(hidden_dim, out_dim)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, adj: torch.Tensor) -> torch.Tensor:
        """返回 L2 归一化后的节点嵌入 [N, out_dim]"""
        x = self.conv1(x, adj)
        x = self.dropout(x)
        x = self.conv2(x, adj)
        return F.normalize(x, p=2, dim=-1)
