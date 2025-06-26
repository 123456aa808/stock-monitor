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
                
                # 如果有库存，返回详细信息
                if stock_amount > 0:
                    return True, results
            
            # 如果所有型号都没有库存
            return False, results
        
        return False, [{"error": "API返回格式错误", "response": data}]
    
    except Exception as e:
        return False, [{"error": str(e)}]

# 发送微信通知 - WxPusher
def send_wxpusher_notification(title, content):
    app_token = os.environ.get("WXPUSHER_APP_TOKEN")
    uid = os.environ.get("WXPUSHER_UID")
    
    if not app_token or not uid:
        print("WxPusher配置不完整，跳过通知")
        return False
    
    url = "https://wxpusher.zjiecode.com/api/send/message"
    data = {
        "appToken": app_token,
        "content": content,
        "summary": title,
        "contentType": 1,
        "uids": [uid]
    }
    
    try:
        response = requests.post(url, json=data, timeout=10)
        result = response.json()
        if result["success"]:
            print("WxPusher通知发送成功")
            return True
        else:
            print(f"WxPusher通知发送失败: {result['msg']}")
            return False
    except Exception as e:
        print(f"WxPusher通知发送异常: {e}")
        return False

# 发送邮件通知
def send_email_notification(subject, content):
    import smtplib
    from email.mime.text import MIMEText
    from email.header import Header
    
    sender = os.environ.get("EMAIL_SENDER")
    password = os.environ.get("EMAIL_PASSWORD")
    receiver = os.environ.get("EMAIL_RECEIVER")
    smtp_server = os.environ.get("EMAIL_SMTP_SERVER", "smtp.qq.com")
    smtp_port = int(os.environ.get("EMAIL_SMTP_PORT", "465"))
    
    if not sender or not password or not receiver:
        print("邮箱配置不完整，跳过通知")
        return False
    
    message = MIMEText(content, 'plain', 'utf-8')
    message['From'] = f'库存监控 <{sender}>'
    message['To'] = receiver
    message['Subject'] = Header(subject, 'utf-8')
    
    try:
        if smtp_port == 465:
            smtp_obj = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else:
            smtp_obj = smtplib.SMTP(smtp_server, smtp_port)
        
        smtp_obj.login(sender, password)
        smtp_obj.sendmail(sender, receiver, message.as_string())
        smtp_obj.quit()
        print("邮件发送成功")
        return True
    except Exception as e:
        print(f"邮件发送失败: {e}")
        return False

# 发送钉钉通知
def send_dingtalk_notification(title, content):
    webhook = os.environ.get("DINGTALK_WEBHOOK", "https://oapi.dingtalk.com/robot/send?access_token=8a3d89e7c3fc6458cbfbea977f4223843ff5e07cffa3698769c5140f5bc8909d")
    secret = os.environ.get("DINGTALK_SECRET", "SECf0d625260b644e3bb349f43a19ff887c6eb44056a926c6c5cda49dfae2582746")
    
    if not webhook:
        print("钉钉配置不完整，跳过通知")
        return False
    
    # 构建通知内容
    message = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": f"### {title}\n\n{content}"
        },
        "at": {
            "isAtAll": False
        }
    }
    
    # 计算签名（如果使用加签安全模式）
    timestamp = str(round(time.time() * 1000))
    if secret:
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(secret.encode(), string_to_sign.encode(), digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code).decode())
        webhook_url = f"{webhook}&timestamp={timestamp}&sign={sign}"
    else:
        webhook_url = webhook
    
    # 发送请求
    try:
        response = requests.post(webhook_url, json=message, headers={"Content-Type": "application/json"})
        result = response.json()
        if result.get("errcode") == 0:
            print("钉钉通知发送成功")
            return True
        else:
            print(f"钉钉通知发送失败: {result.get('errmsg')}")
            return False
    except Exception as e:
        print(f"钉钉通知发送异常: {e}")
        return False

# 保存结果到历史记录
def save_history(results):
    history_file = "stock_history.json"
    
    # 读取现有历史记录
    history = []
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except:
            history = []
    
    # 添加新记录
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    history.append({
        "timestamp": timestamp,
        "results": results
    })
    
    # 只保留最近50条记录
    if len(history) > 50:
        history = history[-50:]
    
    # 保存历史记录
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

# 检查是否需要发送通知（避免重复通知）
def should_notify(goods_id, model_info):
    history_file = "notification_history.json"
    
    # 读取通知历史
    notification_history = {}
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                notification_history = json.load(f)
        except:
            notification_history = {}
    
    # 生成当前商品的唯一键
    key = f"{goods_id}_{model_info['color']}"
    current_time = time.time()
    
    # 如果使用高频检查模式，减少通知间隔时间
    if os.environ.get("RAPID_CHECK", "").lower() == "true":
        # 高频模式下，每5分钟最多通知一次
        notification_interval = 5 * 60  # 5分钟
    else:
        # 普通模式下，每6小时最多通知一次
        notification_interval = 6 * 3600  # 6小时
    
    # 检查是否需要通知
    if key in notification_history:
        last_notify_time = notification_history[key]
        # 如果在规定时间内已经通知过，则不再通知
        if current_time - last_notify_time < notification_interval:
            return False
    
    # 更新通知历史
    notification_history[key] = current_time
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(notification_history, f)
    
    return True

# 主函数
def main():
    all_results = {}
    has_stock = False
    stock_items = []
    
    # 检查所有商品
    for goods in GOODS_LIST:
        goods_id = goods["id"]
        goods_name = goods["name"]
        
        print(f"检查商品: {goods_name} (ID: {goods_id})")
        has_stock_for_item, models_info = check_stock(goods_id)
        
        all_results[goods_name] = {
            "id": goods_id,
            "has_stock": has_stock_for_item,
            "models": models_info
        }
        
        # 如果有库存，准备通知
        if has_stock_for_item:
            has_stock = True
            for model in models_info:
                if model["stock"] > 0:
                    # 检查是否需要发送通知
                    if should_notify(goods_id, model):
                        stock_items.append({
                            "name": goods_name,
                            "id": goods_id,
                            "model": model["model"],
                            "color": model["color"],
                            "stock": model["stock"],
                            "price": model["price"]
                        })
    
    # 保存历史记录
    save_history(all_results)
    
    # 如果有库存变化，发送通知
    if stock_items:
        # 构建通知内容
        title = f"🔔 发现{len(stock_items)}个商品有库存!"
        content = "**【库存监控通知】**\n\n"
        
        for item in stock_items:
            content += f"**商品**: {item['name']}\n\n"
            content += f"**型号**: {item['model']}\n\n"
            content += f"**颜色**: {item['color']}\n\n"
            content += f"**库存**: {item['stock']}件\n\n"
            content += f"**价格**: {item['price']}元\n\n"
            content += f"**链接**: [点击购买](https://card.10010.com/terminal/hs?goodsId={item['id']})\n\n"
            content += "---\n\n"
        
        # 发送通知
        send_wxpusher_notification(title, content)
        send_email_notification(title, content)
        send_dingtalk_notification(title, content)
    
    # 打印结果摘要
    print("\n检查结果摘要:")
    for name, info in all_results.items():
        status = "有库存" if info["has_stock"] else "无库存"
        print(f"{name}: {status}")
    
    return "检查完成"

# 高频检查函数 - 每15秒检查一次
def rapid_check(duration_seconds=300, interval_seconds=15):
    """
    高频检查库存
    
    参数:
    duration_seconds: 持续检查的总时间（秒）
    interval_seconds: 检查间隔（秒）
    """
    start_time = time.time()
    end_time = start_time + duration_seconds
    check_count = 0
    
    print(f"开始高频检查，将持续{duration_seconds}秒，每{interval_seconds}秒检查一次")
    
    # 首次运行时发送测试通知
    test_title = "库存监控高频检查开始"
    test_content = f"高频检查已启动，将每{interval_seconds}秒检查一次，持续{duration_seconds}秒\n\n开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    send_dingtalk_notification(test_title, test_content)
    
    while time.time() < end_time:
        check_count += 1
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"第{check_count}次检查，时间: {current_time}")
        
        main()  # 执行主检查函数
        
        # 计算剩余时间
        remaining = end_time - time.time()
        if remaining <= 0:
            break
            
        # 等待到下次检查
        sleep_time = min(interval_seconds, remaining)
        if sleep_time > 0:
            print(f"等待{sleep_time:.1f}秒后进行下次检查...")
            time.sleep(sleep_time)
    
    # 检查结束后发送通知
    end_notification = f"高频检查结束，共执行了{check_count}次检查\n\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    send_dingtalk_notification("库存监控高频检查结束", end_notification)
    
    print(f"高频检查结束，共执行了{check_count}次检查")

# 本地高频检查 - 按Ctrl+C停止
def local_rapid_check(interval_seconds=15):
    """本地高频检查，直到用户按Ctrl+C停止"""
    try:
        check_count = 0
        start_time = datetime.now()
        print(f"开始本地高频检查，每{interval_seconds}秒检查一次，按Ctrl+C停止")
        
        # 发送开始通知
        start_notification = f"本地高频检查已启动，将每{interval_seconds}秒检查一次\n\n开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}"
        send_dingtalk_notification("库存监控本地检查开始", start_notification)
        
        while True:
            check_count += 1
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"\n第{check_count}次检查，时间: {current_time}")
            
            main()  # 执行主检查函数
            
            print(f"等待{interval_seconds}秒后进行下次检查...")
            time.sleep(interval_seconds)
            
    except KeyboardInterrupt:
        # 计算总运行时间
        duration = datetime.now() - start_time
        hours, remainder = divmod(duration.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        duration_str = f"{int(hours)}小时{int(minutes)}分{int(seconds)}秒"
        
        print("\n用户中断，停止检查")
        
        # 发送结束通知
        end_notification = f"本地高频检查已停止\n\n总计运行: {duration_str}\n共执行检查: {check_count}次\n停止时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        send_dingtalk_notification("库存监控本地检查结束", end_notification)

if __name__ == "__main__":
    # 根据环境变量选择运行模式
    if os.environ.get("LOCAL_MODE", "").lower() == "true":
        # 本地模式 - 直到用户中断
        interval = int(os.environ.get("CHECK_INTERVAL", "15"))
        local_rapid_check(interval)
    elif os.environ.get("RAPID_CHECK", "").lower() == "true":
        # GitHub Actions中的高频模式 - 持续有限时间
        duration = int(os.environ.get("CHECK_DURATION", "300"))  # 默认5分钟
        interval = int(os.environ.get("CHECK_INTERVAL", "15"))   # 默认15秒
        rapid_check(duration, interval)
    else:
        # 普通模式 - 执行一次
        main()
