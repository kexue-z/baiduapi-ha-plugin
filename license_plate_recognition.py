# @Author: kexue

import requests
import time
import paho.mqtt.client as mqtt
import json

from aip import AipOcr
# 读取配置文件
with open('settings.json', 'r') as f:
    data = json.load(f)

face_data = data["license_plate_recognition"]
baidu_api = face_data["baidu_api"]
mqtt_server = face_data["mqtt_server"]
request = face_data["request"]

mqtt_server["subscribe"] = str(mqtt_server["client_id"] + mqtt_server["subscribe"])


class licensePlateRecognition():
    """ 车牌识别模块 """
    def __init__(self):
        self._baidu_client = AipOcr(baidu_api["app_id"],baidu_api["api_key"], baidu_api["secret_key"])
        self._options = baidu_api["options"]

        self._token= request["request_token"]
        self._port = request["request_port"]
        self._addr = request["request_addr"]
        self._type = request["request_type"]
        self._camera_entity_id = request["request_camera_entity_id"]
        # 开始车牌识别
        global number 
        global color
        result = self.licensePlate_Searching()
        try:
            # 无错误，返回结果
            number = result["words_result"]["number"]
            color = result["words_result"]["color"]
            send("logs", f"RESULT:  {number},{color}")
            
        except:
            # 返回错误信息 
            number = None
            color = None
            send("logs", "RESULT:  ERROR")

    def Get_Picture(self):
        """ 
        从 HomeAssistant 中下载图片 
        返回二进制数据
        """
        t = int(round(time.time()))
        headers = {"Authorization": f"Bearer {self._token}",
                   "content-type": "application/json"}
        if self._type == "HTTP":
            http_url = f"http://{self._addr}:{self._port}"
            camera_url = f"{http_url}/api/camera_proxy/{self._camera_entity_id}?time={t} -o image.jpg"
            response = requests.get(camera_url, headers=headers)
            return response.content
        if self._type == "HTTPS": 
            https_url = f"https://{self._addr}:{self._port}"
            camera_url = f"{https_url}/api/camera_proxy/{self._camera_entity_id}?time={t} -o image.jpg"
            response = requests.get(camera_url, headers=headers, verify=False)
            return response.content


    def licensePlate_Searching(self):
        """
        编码图片到base64格式
        通过baiduAPI请求结果
        """
        origin_img = self.Get_Picture()
        ret = self._baidu_client.licensePlate(origin_img, self._options)
        return ret


class MQTT():
    """
    MQTT主模块
    """
    def Connect(client):
        """连接MQTT服务器"""
        client.username_pw_set(mqtt_server["username"], mqtt_server["password"])
        client.connect(mqtt_server["HOST"], mqtt_server["PORT"], 60)
        return client
        

    def on_Connect(client, userdata, flags, rc):
        """订阅主题"""
        client.subscribe(mqtt_server["subscribe"])

    
    def on_Message(client, userdata, msg):
        """获取消息后运行"""
        get_msg(msg.topic, msg.payload.decode("utf-8"))


    def Send_Meassage(client, topic, payload=None) -> bool:
        """发送消息"""
        try:
            client.publish(topic, payload, mqtt_server["qos"])
            return True
        except Exception:
            send("logs", f"ERR:     {Exception}")
            return False


def get_msg(topic, payload=None):
    """获取消息后处理"""
    send("logs", f"CMD:     {payload}")
    if payload == "start":
        licensePlateRecognition()
        send("number", payload=str(number))
        send("color", payload=str(color))
        send("logs", f"CMD:     done")
        

def startup():
    """发送启动状态"""
    send("state", "online")
    send("result", payload="None")
    send("logs", "STATUS:  online")


def send(type, payload):
    """快速发送消息"""
    MQTT.Send_Meassage(client, mqtt_server["client_id"] + f"/{type}", payload)

# 运行点
if __name__ == "__main__":
    global client
    client = mqtt.Client(mqtt_server["client_id"])
    client = MQTT.Connect(client)

    startup()
    client.on_connect = MQTT.on_Connect
    client.on_message = MQTT.on_Message

    try:
       client.loop_forever()
    except KeyboardInterrupt:
        send("state", "offline")
        send("logs", "STATUS:  offline")


