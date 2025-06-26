import requests
import json
import os
import time
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
    
    # 检查是否需要通知
    if key in notification_history:
        last_notify_time = notification_history[key]
        # 如果在6小时内已经通知过，则不再通知
        if current_time - last_notify_time < 6 * 3600:
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
        content = "【库存监控通知】\n\n"
        
        for item in stock_items:
            content += f"商品: {item['name']}\n"
            content += f"型号: {item['model']}\n"
            content += f"颜色: {item['color']}\n"
            content += f"库存: {item['stock']}件\n"
            content += f"价格: {item['price']}元\n"
            content += f"链接: https://card.10010.com/terminal/hs?goodsId={item['id']}\n\n"
        
        # 发送通知
        send_wxpusher_notification(title, content)
        send_email_notification(title, content)
    
    # 打印结果摘要
    print("\n检查结果摘要:")
    for name, info in all_results.items():
        status = "有库存" if info["has_stock"] else "无库存"
        print(f"{name}: {status}")
    
    return "检查完成"

if __name__ == "__main__":
    main()
