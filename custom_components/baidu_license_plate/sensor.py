""" 利用百度OCR APIv3 车牌识别 """
""" 每日免费额度 200次 """
from homeassistant.components.sensor import PLATFORM_SCHEMA
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
import logging
import requests
import time
from homeassistant.helpers.entity import Entity
from datetime import timedelta
from aip import AipOcr
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_API_KEY,
    CONF_NAME,
    CONF_ENTITY_ID
)

_LOGGER = logging.getLogger(__name__)

ATTR_NUMBER = "number"
ATTR_COLOR = "color"

CONF_APP_ID = "app_id"
CONF_SECRET_KEY = "secret_key"
CONF_PORT = "port"

DEFAULT_NAME = "license plate"
DEFAULT_PORT = 8123
DEFAULT_REQUEST_TYPE = "HTTP"

SCAN_INTERVAL = timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_APP_ID): cv.string,
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_SECRET_KEY): cv.string,
    vol.Required(CONF_ENTITY_ID): cv.string,
    vol.Required(CONF_ACCESS_TOKEN): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port
})

def setup_platform(hass, config, add_devices,
                   discovery_info=None):

    """  添加传感器实体 """
    app_id = config.get(CONF_APP_ID)
    api_key = config.get(CONF_API_KEY)
    secret_key = config.get(CONF_SECRET_KEY)
    camera_entity_id = config.get(CONF_ENTITY_ID)
    name = config.get(CONF_NAME)
    port = config.get(CONF_PORT)
    token = config.get(CONF_ACCESS_TOKEN)

    """ 检查HTTPS/HTTP """
    try: 
        http_url = "https://127.0.0.1:{}".format(port)
        camera_url = "{}/api/camera_proxy/{}".format(http_url, camera_entity_id)
        headers = {"Authorization": "Bearer {}".format(token),
               "content-type": "application/json"}
        response = requests.get(camera_url, headers=headers, verify=False)
        if response.status_code == 200:
            DEFAULT_REQUEST_TYPE = "HTTPS"
    except BaseException:
        DEFAULT_REQUEST_TYPE = "HTTP"
    baidu_client = AipOcr(app_id, api_key, secret_key)
    add_devices([LicenseSensor(name, camera_entity_id, port, token, baidu_client, DEFAULT_REQUEST_TYPE)])

class LicenseSensor(Entity):

    def __init__(self, name, camera_entity_id, port, token, baidu_client:AipOcr, request_type):
        self._camera_entity_id = camera_entity_id
        self._name = name
        self._port = str(port)
        self._token = token
        self._baidu_client = baidu_client
        self._state = False
        self._attr = None
        self._type = request_type

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def device_state_attributes(self):
        return self._attr

    def update(self):
        self.face_searching()

    def get_picture(self):
        """ 
        从 HomeAssistant 中下载图片 
        返回二进制数据
        """
        t = int(round(time.time()))
        headers = {"Authorization": "Bearer {}".format(self._token),
                   "content-type": "application/json"}
        if self._type == "HTTP":
            http_url = "http://127.0.0.1:{}".format(self._port)
            camera_url = "{}/api/camera_proxy/{}?time={} -o image.jpg".format(http_url, self._camera_entity_id, t)
            response = requests.get(camera_url, headers=headers)
            return response.content
        if self._type == "HTTPS": 
            https_url = "https://127.0.0.1:{}".format(self._port)
            camera_url = "{}/api/camera_proxy/{}?time={} -o image.jpg".format(https_url, self._camera_entity_id, t)
            response = requests.get(camera_url, headers=headers, verify=False)
            return response.content

    def face_searching(self):
        """ 获取图片 调用API 返回参数 """
        origin_img = self.get_picture()
        ret = self._baidu_client.licensePlate(origin_img)
        self._attr = {}
        self._attr[ATTR_NUMBER] = "None"
        self._attr[ATTR_COLOR] = "None"
        try:
            self._state = True
            self._attr[ATTR_NUMBER] = ret["words_result"]["number"]
            self._attr[ATTR_COLOR] = ret["words_result"]["color"]

        except:
            self._state = False
        