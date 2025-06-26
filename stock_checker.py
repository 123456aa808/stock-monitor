import requests
import json
import os
import time
import hmac
import hashlib
import base64
import urllib.parse
from datetime import datetime

# 配置信息
GOODS_LIST = [
    {"id": "995206067625", "name": "华为TC32路由器"},
    {"id": "994210179268", "name": "塞那骨传导耳机"}
]
CITY_CODE = "110"  # 北京

# 钉钉配置
DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=8a3d89e7c3fc6458cbfbea977f4223843ff5e07cffa3698769c5140f5bc8909d"
DINGTALK_SECRET = "SECf0d625260b644e3bb349f43a19ff887c6eb44056a926c6c5cda49dfae2582746"

# 检查库存
def check_stock(goods_id, city_code=CITY_CODE):
    url = f"https://card.10010.com/mall-order/qryStock/v2?goodsId={goods_id}&cityCode={city_code}&isUni="
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data["code"] == "0000" and data["data"] and data["data"]["bareMetal"]:
            models = data["data"]["bareMetal"]["modelsList"]
            results = []
            
            for model in models:
                stock_amount = (model.get("articleAmount", 0) or 0) + (model.get("articleAmountNew", 0) or 0)
                model_info = {
                    "model": model.get("MODEL_DESC", "未知型号"),
                    "color": model.get("COLOR_DESC", "未知颜色"),
                    "stock": stock_amount,
                    "price": model.get("TERM_PRICE", "未知价格")
                }
                results.append(model_info)
            
            return results
        
        return []
    
    except Exception as e:
        print(f"检查库存出错: {e}")
        return []

# 发送钉钉通知
def send_dingtalk_notification(title, content):
    # 构建通知内容
    message = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": f"### {title}\n\n{content}"
        }
    }
    
    # 计算签名
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{DINGTALK_SECRET}"
    hmac_code = hmac.new(DINGTALK_SECRET.encode(), string_to_sign.encode(), digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code).decode())
    webhook_url = f"{DINGTALK_WEBHOOK}&timestamp={timestamp}&sign={sign}"
    
    # 发送请求
    try:
        response = requests.post(webhook_url, json=message, headers={"Content-Type": "application/json"})
        result = response.json()
        if result.get("errcode") == 0:
            print(f"钉钉通知发送成功: {title}")
        else:
            print(f"钉钉通知发送失败: {result}")
    except Exception as e:
        print(f"钉钉通知发送异常: {e}")

# 主函数
def check_and_notify():
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"开始检查库存: {current_time}")
    
    # 检查所有商品
    for goods in GOODS_LIST:
        goods_id = goods["id"]
        goods_name = goods["name"]
        
        print(f"检查商品: {goods_name}")
        models_info = check_stock(goods_id)
        
        # 发送每个商品的库存状态
        content = f"**商品**: {goods_name}\n\n**检查时间**: {current_time}\n\n"
        
        if not models_info:
            content += "**状态**: 查询失败或无数据\n\n"
            send_dingtalk_notification(f"{goods_name} 库存查询", content)
            continue
        
        has_stock = False
        for model in models_info:
            stock_amount = model["stock"]
            content += f"**型号**: {model['model']}\n\n"
            content += f"**颜色**: {model['color']}\n\n"
            content += f"**库存**: {stock_amount}件\n\n"
            content += f"**价格**: {model['price']}元\n\n"
            content += "---\n\n"
            
            if stock_amount > 0:
                has_stock = True
        
        # 添加购买链接
        content += f"**链接**: [点击购买](https://card.10010.com/terminal/hs?goodsId={goods_id})\n\n"
        
        # 发送通知
        if has_stock:
            title = f"🔔 {goods_name} 有库存!"
        else:
            title = f"{goods_name} 暂无库存"
        
        send_dingtalk_notification(title, content)

# 高频检查函数
def main():
    interval = 15  # 每15秒检查一次
    
    # 发送开始通知
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_dingtalk_notification("库存监控开始", f"开始时间: {start_time}\n\n将每{interval}秒检查一次")
    
    try:
        # 无限循环检查，直到GitHub Actions超时或被终止
        check_count = 0
        while True:
            check_count += 1
            print(f"\n第{check_count}次检查")
            
            check_and_notify()
            
            print(f"等待{interval}秒后进行下次检查...")
            time.sleep(interval)
            
    except Exception as e:
        error_msg = f"监控出错: {e}"
        print(error_msg)
        send_dingtalk_notification("库存监控出错", error_msg)

if __name__ == "__main__":
    main()
