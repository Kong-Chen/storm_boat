from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.models import ImageSendMessage
import os
import uuid
from psycopg2.extensions import adapt, register_adapter
import psycopg2
from datetime import datetime
import psycopg2
import requests
import re
from datetime import datetime, time, timedelta

app = Flask(__name__)

# 設置你的 LINE Bot 的 Channel Access Token 和 Channel Secret
line_bot_api = LineBotApi(os.environ['LINE_CHANNEL_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['LINE_CHANNEL_SECRET'])


def get_weekday_in_taiwan(date):
    
    date = datetime.strptime(date, '%Y-%m-%d')
    # 轉換成台灣時間
    taiwan_time = date + timedelta(hours=8)
    
    # 取得星期幾 (0 = 星期一, 1 = 星期二, ..., 6 = 星期日)
    weekday = taiwan_time.weekday()
    return weekday+1

# 註冊 UUID 型別的適應器
def adapt_uuid(uuid):
    return adapt(str(uuid))
register_adapter(uuid.UUID, adapt_uuid)

#發送line_notify
def send_line_notify(message):
    url = 'https://notify-api.line.me/api/notify'
    token = 'FyyMaWRVa0fzLT31LzqJ9kOIblJJk6oxJjq9wN8H7Cn'   #世壯
    # 'JFNVWXhtYadtX65B3U9g4s5vzgVTeUdLVZqykcE4TUs' #列車
    headers = {
        'Authorization': 'Bearer ' + token
    }
    data = {
        'message': message
    }
    response = requests.post(url, headers=headers, data=data)
    return response


@app.route("/callback", methods=['GET','POST'])
def callback():
    
    #排程用
    if request.method == 'GET':
        current_time = datetime.utcnow() + timedelta(hours=8)
        year = current_time.year
        month = current_time.month
        day = current_time.day
        hour = current_time.hour
        minute = current_time.minute
        
        if current_time.weekday() <= 4 and hour == 8 and minute == 0 :
            
            days_until_saturday = (5 - current_time.weekday() + 7) % 7
            if days_until_saturday == 0:
                days_until_saturday = 7  # 如果今天是周六，找到下一个周六

            next_saturday = current_time + timedelta(days=days_until_saturday)
            next_saturday_str = f"{next_saturday.year}-{next_saturday.month:02d}-{next_saturday.day:02d}"
            
            
            connection = psycopg2.connect(
                host="dpg-cpp4jouehbks73brha50-a.oregon-postgres.render.com",
                port="5432",
                database="nobody_y10j",
                user="kong",
                password="yydSDvrjnBhY68izhYu7UhRiiQPdPGth"
            )
            cursor = connection.cursor()
            query = """
            SELECT u.user_name
            FROM leave_records l
            LEFT JOIN users u ON l.user_id = u.user_id
            WHERE l.leave_date = %s;
            """
            cursor.execute(query, (next_saturday_str,))
            records = cursor.fetchall()
            if records:
                response_message = f'{next_saturday_str}請假的有：'
                for record in records:
                    user_name = record[0]
                    response_message += f"\n{user_name}"

            else:
                response_message = f"{next_saturday_str}沒有人請假！！"
            
            #增加天氣判斷
            if 2 <= current_time.weekday() <= 4:
                authorization = 'CWA-5AB2578A-4D37-4042-9FBB-777EAAED3040'
                url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-D0047-061"

                # 发出请求
                response = requests.get(url, {"Authorization": authorization})
                response.raise_for_status()  # 检查响应状态码是否为200
                resJson = response.json()
                locations = resJson["records"]["locations"][0]["location"]
                target_district = "士林區"
                target_date = next_saturday_str
                target_time = target_date +" 09:00:00"
                pop_time = target_date +" 06:00:00" 
                for location in locations:
                    if location["locationName"] == target_district:
                        # print(location["locationName"])
                        weatherElements = location["weatherElement"]
                        for weatherElement in weatherElements:
                            if weatherElement["elementName"] == "T":
                                timeDicts = weatherElement["time"]
                                for timeDict in timeDicts:
                                    if timeDict["dataTime"] == target_time:
                                        # print (target_date+":")
                                        response_message += f"\n"+"社子島當天早上氣象預測如下:"
                                        aaa = "溫度攝氏:"+timeDict["elementValue"][0]["value"]+"度"
                                        response_message += f"\n{aaa}"
                            elif weatherElement["elementName"] == "PoP6h":
                                popDicts = weatherElement["time"]
                                for popDict in popDicts:
                                    if popDict["startTime"] == pop_time:
                                        bbb= "降雨機率:"+popDict["elementValue"][0]["value"]+"%"
                                        response_message += f"\n{bbb}"
                            elif weatherElement["elementName"] == "WS":
                                windDicts = weatherElement["time"]
                                for windDict in windDicts:
                                    if windDict["dataTime"] == target_time:
                                        ccc="最大風速:"+windDict["elementValue"][0]["value"]+"公尺/秒"
                                        response_message += f"\n{ccc}"
            
            response = send_line_notify(response_message)
        
        return "OK"
    
      
    elif request.method == 'POST':
        # 處理 POST 請求的邏輯    
        # 取得 request headers 中的 X-Line-Signature 屬性
        signature = request.headers['X-Line-Signature']
        
        # 取得 request 的 body 內容
        body = request.get_data(as_text=True)
        
        try:
            # 驗證簽章
            handler.handle(body, signature)
        except InvalidSignatureError:
            abort(400)
        
        return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    
    # 建立連接 (修改)
    connection = psycopg2.connect(
        host="dpg-cpp4jouehbks73brha50-a.oregon-postgres.render.com",
        port="5432",
        database="nobody_y10j",
        user="kong",
        password="yydSDvrjnBhY68izhYu7UhRiiQPdPGth"
    )
      
    # 收到使用者的訊息
    user_message = event.message.text
    user_line_id = event.source.user_id

    if event.source.type == 'user' or event.source.type == 'group' or event.source.type == 'room':
        profile = line_bot_api.get_profile(user_line_id)
        user_nickname = profile.display_name

    try:
        # 新增使用者
        cursor = connection.cursor()
        query = """
        INSERT INTO users (user_id, user_name)
        VALUES (%s, %s)
        ON CONFLICT (user_id) DO NOTHING;
        """
        cursor.execute(query, (user_line_id, user_nickname))
        connection.commit()
        
        # 對話關鍵字判斷開始 *****************
        if user_message =='功能':
            aaa = (f"1.請假：0520請假"+'\n' + f"2.取消請假：0520取消請假"+'\n' + f"3.查詢請假：0520查詢請假" +'\n' + f"4.我的請假查詢")
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=aaa)
            )
            
        elif re.match(r'\d{4}請假', user_message):
            # 使用正規表達式匹配日期格式
            pattern = r'(\d{2})(\d{2})請假'
            match = re.match(pattern, user_message)

            if match:
                month = match.group(1)
                day = match.group(2)
                year = datetime.now().year
                date_str = f"{year}-{month}-{day}"

                try:
                    if get_weekday_in_taiwan(date_str) > 5 : #如果是假日
                        
                        query_check = """
                        SELECT COUNT(*) FROM leave_records
                        WHERE user_id = %s AND leave_date = %s;
                        """
                        cursor.execute(query_check, (user_line_id, date_str))
                        count = cursor.fetchone()[0]
                        
                        if count == 0:
                            # 插入请假记录到 leave_records 资料表
                            query_leave = """
                            INSERT INTO leave_records (user_id, leave_date)
                            VALUES (%s, %s);
                            """
                            cursor.execute(query_leave, (user_line_id, date_str))
                            connection.commit()

                            response_message = f'完成請假日期登記：{date_str}'
                            line_bot_api.reply_message(
                                event.reply_token,
                                TextSendMessage(text=response_message)
                            )
                        else:
                            response_message = f"您在此日期已請假!!"
                            line_bot_api.reply_message(
                                event.reply_token,
                                TextSendMessage(text=response_message)
                            )

                    else:
                        response_message = f"請假日期非練習時間!!!!"
                        line_bot_api.reply_message(
                            event.reply_token,
                            TextSendMessage(text=response_message)
                        )
                        
                except ValueError:
                    warning_message = '日期格式不正確。'
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text=warning_message)
                    )
            else:
                warning_message = '請輸入正確的日期格式，範例如：0520請假'
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=warning_message)
                )
        
        elif re.match(r'\d{4}取消請假', user_message):
            # 使用正規表達式匹配日期格式
            pattern = r'(\d{2})(\d{2})取消請假'
            match = re.match(pattern, user_message)

            if match:
                month = match.group(1)
                day = match.group(2)
                year = datetime.now().year
                date_str = f"{year}-{month}-{day}"

                try:
                    if get_weekday_in_taiwan(date_str) > 5 : #如果是假日
                        
                        query_check = """
                        SELECT COUNT(*) FROM leave_records
                        WHERE user_id = %s AND leave_date = %s;
                        """
                        cursor.execute(query_check, (user_line_id, date_str))
                        count = cursor.fetchone()[0]
                        
                        if count == 1:
                            # 插入请假记录到 leave_records 资料表
                            query_leave = """
                            DELETE FROM leave_records WHERE user_id =%s AND leave_date=%s;
                            """
                            cursor.execute(query_leave, (user_line_id, date_str))
                            connection.commit()

                            response_message = f'完成請假取消：{date_str}'
                            line_bot_api.reply_message(
                                event.reply_token,
                                TextSendMessage(text=response_message)
                            )
                        else:
                            response_message = f"您在此日期沒有請假紀錄!!!"
                            line_bot_api.reply_message(
                                event.reply_token,
                                TextSendMessage(text=response_message)
                            )

                    else:
                        response_message = f"請假日期非假日!!!!"
                        line_bot_api.reply_message(
                            event.reply_token,
                            TextSendMessage(text=response_message)
                        )
                        
                except ValueError:
                    warning_message = '日期格式不正確。'
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text=warning_message)
                    )
            else:
                warning_message = '請輸入正確的日期格式，範例如：0520取消請假'
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=warning_message)
                )
        
        
        elif re.match(r'\d{4}查詢請假', user_message):
            # 使用正規表達式匹配日期格式
            pattern = r'(\d{2})(\d{2})查詢請假'
            match = re.match(pattern, user_message)

            if match:
                month = match.group(1)
                day = match.group(2)
                year = datetime.now().year
                date_str = f"{year}-{month}-{day}"

                try:
                    datetime.strptime(date_str, '%Y-%m-%d')  # 檢查日期格式是否正確

                    # 查詢 leave_records 表格，找出符合該日期的所有 user_id
                    query = """
                    SELECT u.user_name
                    FROM leave_records l
                    LEFT JOIN users u ON l.user_id = u.user_id
                    WHERE l.leave_date = %s;
                    """
                    cursor.execute(query, (date_str,))
                    records = cursor.fetchall()

                    if records:
                        response_message = '請假的有：'
                        for record in records:
                            user_name = record[0]
                            response_message += f"\n{user_name}"

                        line_bot_api.reply_message(
                            event.reply_token,
                            TextSendMessage(text=response_message)
                        )
                    else:
                        response_message = f"在 {date_str} 沒有任何人請假。"
                        line_bot_api.reply_message(
                            event.reply_token,
                            TextSendMessage(text=response_message)
                        )

                except ValueError:
                    warning_message = '日期格式不正確。'
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text=warning_message)
                    )
            else:
                warning_message = '請輸入正確的日期格式，範例如：0520查詢請假'
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=warning_message)
                )

        elif user_message == '我的請假查詢':

            # 查詢 leave_records 表格，找出該用戶的所有請假日期
            query = """
            SELECT leave_date
            FROM leave_records
            WHERE user_id = %s
            ORDER BY leave_date;
            """
            cursor.execute(query, (user_line_id,))
            records = cursor.fetchall()

            if records:
                response_message = '您的請假紀錄如下：'
                for record in records:
                    leave_date = record[0]
                    response_message += f"\n{leave_date}"

                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=response_message)
                )
            else:
                response_message = "您沒有請假紀錄！"
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=response_message)
                )
        

        
        else: #不能亂講話
            warning_message = '請不要亂打，或輸入(功能)來看提示!!!!'
        
    except psycopg2.Error as e:
        # print("資料庫錯誤:", e)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="資料庫錯誤啦!")
        )

if __name__ == "__main__":
    # 在本地運行時才啟動伺服器
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))