import requests
import json
import os
import time
import hmac
import hashlib
import base64
import urllib.parse
from datetime import datetime, timedelta

# 配置信息 - 一般商品组
NORMAL_GOODS_LIST = [
    {"id": "994210179268", "name": "塞那骨传导耳机"},
    {"id": "995206173862", "name": "联通商务手提背包"},
    {"id": "995206162886", "name": "欧普护眼台灯"},
    {"id": "994210179232", "name": "黑胶高尔夫雨伞"}
]

# 配置信息 - 路由器组（频繁变化）
ROUTER_GOODS_LIST = [
    {"id": "995206067625", "name": "华为TC32路由器", "min_stock_threshold": 10}
]

CITY_CODE = "110"  # 北京

# 钉钉配置 - 统一使用一个机器人
DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=8a3d89e7c3fc6458cbfbea977f4223843ff5e07cffa3698769c5140f5bc8909d"
DINGTALK_SECRET = "SECf0d625260b644e3bb349f43a19ff887c6eb44056a926c6c5cda49dfae2582746"

# 存储上次检查的库存状态
last_stock_status = {}

# 获取中国时间
def get_china_time():
    utc_time = datetime.utcnow()
    china_time = utc_time + timedelta(hours=8)
    return china_time

# 检查库存
def check_stock(goods_id, city_code=CITY_CODE):
    url = f"https://card.10010.com/mall-order/qryStock/v2?goodsId={goods_id}&cityCode={city_code}&isUni="
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data["code"] == "0000" and data["data"] and data["data"]["bareMetal"]:
            total_stock = 0
            for model in data["data"]["bareMetal"]["modelsList"]:
                stock_amount = (model.get("articleAmount", 0) or 0) + (model.get("articleAmountNew", 0) or 0)
                total_stock += stock_amount
            
            return total_stock
        
        return 0
    
    except Exception as e:
        print(f"检查库存出错: {e}")
        return 0

# 发送钉钉通知
def send_dingtalk_notification(title, content, webhook, secret):
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
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(secret.encode(), string_to_sign.encode(), digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code).decode())
    webhook_url = f"{webhook}&timestamp={timestamp}&sign={sign}"
    
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

# 检查商品组并发送通知
def check_goods_group(goods_list, webhook, secret, group_name):
    global last_stock_status
    current_time = get_china_time().strftime("%Y-%m-%d %H:%M:%S")
    print(f"开始检查{group_name}库存: {current_time}")
    
    # 检查所有商品
    stock_changes = []
    current_stock_items = []
    out_of_stock_items = []
    
    for goods in goods_list:
        goods_id = goods["id"]
        goods_name = goods["name"]
        min_threshold = goods.get("min_stock_threshold", 1)  # 默认阈值为1，路由器设为10
        
        print(f"检查商品: {goods_name}")
        total_stock = check_stock(goods_id)
        
        # 判断商品是否"有货"（对于路由器，库存>=10才算有货）
        has_stock = total_stock >= min_threshold
        
        # 检查库存状态是否变化
        if goods_id in last_stock_status:
            last_has_stock = last_stock_status[goods_id] >= min_threshold
            
            if not last_has_stock and has_stock:
                # 由无货变为有货
                if "路由器" in goods_name:
                    stock_changes.append(f"**{goods_name}** 库存充足！当前库存: {total_stock}件")
                else:
                    stock_changes.append(f"**{goods_name}** 有库存了！库存数量: {total_stock}件")
            elif last_has_stock and not has_stock:
                # 由有货变为无货
                if "路由器" in goods_name and total_stock > 0:
                    stock_changes.append(f"**{goods_name}** 库存不足，仅剩: {total_stock}件")
                else:
                    stock_changes.append(f"**{goods_name}** 已无库存")
        else:
            # 首次检查
            if has_stock:
                if "路由器" in goods_name:
                    stock_changes.append(f"**{goods_name}** 库存充足！当前库存: {total_stock}件")
                else:
                    stock_changes.append(f"**{goods_name}** 有库存！库存数量: {total_stock}件")
        
        # 更新库存状态
        last_stock_status[goods_id] = total_stock
        
        # 记录当前有库存的商品
        if total_stock > 0:
            if "路由器" in goods_name:
                if has_stock:
                    current_stock_items.append(f"**{goods_name}**: {total_stock}件 (库存充足)")
                else:
                    current_stock_items.append(f"**{goods_name}**: {total_stock}件 (库存不足)")
            else:
                current_stock_items.append(f"**{goods_name}**: {total_stock}件")
        else:
            out_of_stock_items.append(f"**{goods_name}**")
    
    # 如果有库存变化，发送通知
    if stock_changes:
        content = f"**{group_name}库存变化通知**\n\n"
        content += "\n\n".join(stock_changes)
        content += "\n\n---\n\n"
        
        # 添加当前有库存商品
        if current_stock_items:
            content += "**当前有库存商品**\n\n"
            content += "\n\n".join(current_stock_items)
        else:
            content += "**当前所有商品均无库存**"
        
        # 添加待补货商品
        content += "\n\n---\n\n"
        if out_of_stock_items:
            content += "**待补货商品**\n\n"
            content += "\n\n".join(out_of_stock_items)
        else:
            content += "**所有商品均有库存**"
        
        send_dingtalk_notification(f"{group_name}库存状态变化", content, webhook, secret)

# 主函数
def main():
    interval = 5  # 每5秒检查一次
    
    # 发送开始通知
    start_time = get_china_time().strftime("%Y-%m-%d %H:%M:%S")
    send_dingtalk_notification("库存监控开始", f"开始时间: {start_time} (北京时间)\n\n注意：路由器商品库存大于等于10件才视为有货", DINGTALK_WEBHOOK, DINGTALK_SECRET)
    
    try:
        # 无限循环检查，直到GitHub Actions超时或被终止
        check_count = 0
        while True:
            check_count += 1
            print(f"\n第{check_count}次检查")
            
            # 检查一般商品组
            check_goods_group(NORMAL_GOODS_LIST, DINGTALK_WEBHOOK, DINGTALK_SECRET, "一般商品")
            
            # 检查路由器组
            check_goods_group(ROUTER_GOODS_LIST, DINGTALK_WEBHOOK, DINGTALK_SECRET, "路由器")
            
            print(f"等待{interval}秒后进行下次检查...")
            time.sleep(interval)
            
    except Exception as e:
        error_msg = f"监控出错: {e}"
        print(error_msg)
        send_dingtalk_notification("库存监控出错", error_msg, DINGTALK_WEBHOOK, DINGTALK_SECRET)

if __name__ == "__main__":
    main()
