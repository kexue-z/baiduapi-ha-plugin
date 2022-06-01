# @Author: kexue

import base64
import time
import paho.mqtt.client as mqtt
import requests
import json

from aip import AipFace
# 读取配置文件
with open("settings.json", "r") as f:
    data = json.load(f)

face_data = data["face_recognition"]
baidu_api = face_data["baidu_api"]
mqtt_server = face_data["mqtt_server"]
request = face_data["request"]

mqtt_server["subscribe"] = str(mqtt_server["client_id"] + mqtt_server["subscribe"])


class FaceRecognition():
    """ 人脸识别模块 """
    def __init__(self):
        # 读取配置文件
        self._baidu_client = AipFace(baidu_api["app_id"],baidu_api["api_key"], baidu_api["secret_key"])
        self._group_list = baidu_api["group_list"]
        self._options = baidu_api["options"]

        self._token = request["request_token"]
        self._port = request["request_port"]
        self._addr = request["request_addr"]
        self._camera_entity_id = request["request_camera_entity_id"]
        self._type = request["request_type"]
        # 开始人脸识别
        global result_name
        global result_score
        result = self.Face_Searching()
        if result["error_code"] == 0:
            # 无错误，返回结果
            result_name = result["result"]["user_list"][0]["user_id"]
            result_score = result["result"]["user_list"][0]["score"]
            send("logs", f"RESULT:  {result_name},{result_score}")
        else:
            # 返回错误信息 
            result_name = result["error_msg"]
            result_score = None
            send("logs", f"RESULT:  {result_name},{result_score}")


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


    def Face_Searching(self):
        """
        编码图片到base64格式
        通过baiduAPI请求结果
        """
        origin_img = self.Get_Picture()
        encode_img = base64.b64encode(origin_img)
        encode_img = bytes.decode(encode_img)
        image_type = "BASE64"
        ret = self._baidu_client.search(encode_img, image_type, self._group_list) 
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
        get_msg(msg.topic, str(msg.payload.decode("utf-8")))


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
    if payload == "start":
        send("logs", f"CMD:     {payload}")
        FaceRecognition()
        send("result/name", payload=str(result_name))
        send("result/score", payload=str(result_score))
        send("logs", "CMD:     done")
    else:
        send("logs", f"CMD:     {payload}")
       
        
def startup():
    """发送启动状态"""
    send("state", "online")
    send("result/score", "None")  
    send("result/name", "None")  
    send("logs", "STATUS:  online")


def send(type, payload):
    """快速发送消息"""
    MQTT.Send_Meassage(client, mqtt_server["client_id"] + f"/{type}", payload)

# 运行点
if __name__ == "__main__":
    try:
        global client
        client = mqtt.Client(mqtt_server["client_id"])
        client.on_connect = MQTT.on_Connect
        client.on_message = MQTT.on_Message

        client = MQTT.Connect(client)
        startup()
        client.loop_forever()
    except KeyboardInterrupt:
        send("state", "offline")
        send("logs", f"\nSTATUS:  offline")

    