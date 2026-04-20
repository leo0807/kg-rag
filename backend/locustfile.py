from locust import HttpUser, task, between, events
import requests

class KG_RAG_User(HttpUser):
    # 更激进的等待时间以达到 20 QPS
    wait_time = between(0.1, 0.5)

    @task
    def query(self):
        questions = [
            "什么是液压导管安装步骤？",
            "如何修理液压导管？",
            "航空工艺规范中关于导管连接的要求是什么？",
            "导管弯曲有哪些技术指标？",
            "液压系统压力测试的标准流程是什么？"
        ]
        import random
        question = random.choice(questions)
        self.client.post("/api/query", json={"question": question})

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """预热缓存"""
    host = environment.host or "http://localhost:8000"
    questions = [
        "什么是液压导管安装步骤？",
        "如何修理液压导管？",
        "航空工艺规范中关于导管连接的要求是什么？",
        "导管弯曲有哪些技术指标？",
        "液压系统压力测试的标准流程是什么？"
    ]
    print("Warming up cache...")
    for q in questions:
        try:
            requests.post(f"{host}/api/query", json={"question": q}, timeout=60)
        except Exception as e:
            print(f"Warmup failed for {q}: {e}")
    print("Warmup complete.")
