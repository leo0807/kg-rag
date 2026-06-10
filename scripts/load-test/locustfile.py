"""
KG-RAG 压测脚本（Locust）
安装：pip install locust
运行：locust -f scripts/load-test/locustfile.py --host http://localhost:8000
      # 或无界面模式：
      locust -f scripts/load-test/locustfile.py --host http://localhost:8000 \
             --headless -u 10 -r 2 --run-time 60s --csv results
"""
import json
import random
from locust import HttpUser, TaskSet, between, task

# ── 测试数据 ─────────────────────────────────────────────────────────
QUESTIONS = [
    "铝合金表面处理的主要工艺步骤是什么？",
    "复合材料修复的一般要求有哪些？",
    "密封剂的固化时间和温度要求？",
    "阳极氧化处理的工艺规范是什么？",
    "结构铆接的工艺要求和检验标准？",
    "底漆涂装的表面预处理要求？",
    "NDT无损检测的适用范围？",
    "热处理工艺参数如何确定？",
    "蒙皮修复的许可限制是什么？",
    "搭铁连接的安装工艺要求？",
]

TEST_USER = {"username": "100001", "password": "admin123"}


class KGRAGTaskSet(TaskSet):
    token: str = ""
    conv_id: str = ""

    def on_start(self) -> None:
        self._login()

    def _login(self) -> None:
        resp = self.client.post(
            "/api/auth/login",
            json=TEST_USER,
            name="/api/auth/login",
        )
        if resp.status_code == 200:
            self.token = resp.json().get("access_token", "")
        else:
            self.token = ""

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    # ── 问答（核心接口）权重最高 ─────────────────────────────────────
    @task(5)
    def ask_question_sync(self) -> None:
        question = random.choice(QUESTIONS)
        payload  = {"question": question, "strategy": "parallel"}
        if self.conv_id:
            payload["conversation_id"] = self.conv_id
        with self.client.post(
            "/api/query/sync",
            json=payload,
            headers=self._headers(),
            name="/api/query/sync",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                self.conv_id = data.get("conversation_id", self.conv_id)
                resp.success()
            elif resp.status_code == 401:
                self._login()
                resp.failure("需要重新登录")
            else:
                resp.failure(f"HTTP {resp.status_code}")

    # ── 搜索 ────────────────────────────────────────────────────────
    @task(3)
    def search(self) -> None:
        q = random.choice(["铝合金", "密封", "复合材料", "无损检测", "热处理"])
        self.client.get(
            f"/api/search?q={q}&limit=10",
            headers=self._headers(),
            name="/api/search",
        )

    # ── 历史会话 ──────────────────────────────────────────────────
    @task(2)
    def list_sessions(self) -> None:
        self.client.get(
            "/api/sessions?limit=20",
            headers=self._headers(),
            name="/api/sessions",
        )

    # ── Wiki 文档列表 ─────────────────────────────────────────────
    @task(1)
    def wiki_index(self) -> None:
        self.client.get(
            "/api/wiki/index",
            headers=self._headers(),
            name="/api/wiki/index",
        )

    # ── 健康检查 ──────────────────────────────────────────────────
    @task(1)
    def health_check(self) -> None:
        self.client.get("/api/health", name="/api/health")


class KGRAGUser(HttpUser):
    tasks = [KGRAGTaskSet]
    wait_time = between(1, 5)       # 模拟用户思考间隔 1-5秒

    # 未登录时先登录
    def on_start(self) -> None:
        pass
