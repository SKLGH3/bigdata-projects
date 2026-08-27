import json
import random
from datetime import datetime

# 日志文件路径
LOG_FILE = "/opt/module/datas/hbase/logs/user_action.log"

# 数据池
USERS = [f"user_{i}" for i in range(1, 101)]
ACTIONS = ["login", "view_product", "add_cart", "purchase", "logout"]
DEVICES = ["PC", "Mobile", "Tablet"]
PAGES = ["/home", "/product/101", "/product/202", "/cart", "/checkout", "/profile"]

def generate_record():
    """生成一条JSON格式的用户行为记录"""
    return {
        "id": str(random.randint(1000, 9999)),
        "user": random.choice(USERS),
        "action": random.choice(ACTIONS),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ip": f"192.168.{random.randint(1,255)}.{random.randint(1,255)}",
        "device": random.choice(DEVICES),
        "duration": str(random.randint(5, 600)),
        "page": random.choice(PAGES)
    }

if __name__ == "__main__":
    print("开始生成用户行为日志...")
    
    # 生成10万条测试数据（优化后可用于压测）
    for i in range(100000):
        with open(LOG_FILE, "a") as f:
            json.dump(generate_record(), f)
            f.write("\n")
        
        # 每1万条打印一次进度
        if (i + 1) % 10000 == 0:
            print(f"已生成 {i + 1} 条")
    
    print("完成！共生成 100000 条用户行为日志")
