import logging
import requests
import time
import hashlib
import hmac
import json
import datetime
from typing import Optional, List
from urllib.parse import quote


class VolcanoVoiceManagerClient:

    HOST = "open.volcengineapi.com"
    SERVICE = "speech_saas_prod"
    REGION = "cn-north-1"
    VERSION = "2023-11-07"

    MAX_RETRIES = 3
    RETRY_DELAY = 2

    def __init__(self, access_key_id: str, access_key_secret: str, appid: str):
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.appid = appid
        self.session = requests.Session()

        logging.info("火山引擎音色管理客户端初始化成功，appid: %s", self.appid)

    def _sign_request(self, method: str, action: str, body: str) -> dict:
        now = datetime.datetime.now(datetime.timezone.utc)
        x_date = now.strftime("%Y%m%dT%H%M%SZ")
        short_date = x_date[:8]

        canonical_uri = "/"
        canonical_query_string = "Action=" + action + "&Version=" + self.VERSION

        content_type = "application/json; charset=utf-8"
        canonical_headers = (
            "content-type:" + content_type + "\n"
            + "host:" + self.HOST + "\n"
            + "x-content-sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest() + "\n"
            + "x-date:" + x_date + "\n"
        )
        signed_headers = "content-type;host;x-content-sha256;x-date"

        hashed_payload = hashlib.sha256(body.encode("utf-8")).hexdigest()

        canonical_request = (
            method.upper() + "\n"
            + canonical_uri + "\n"
            + canonical_query_string + "\n"
            + canonical_headers + "\n"
            + signed_headers + "\n"
            + hashed_payload
        )

        hashed_canonical_request = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()

        credential_scope = short_date + "/" + self.REGION + "/" + self.SERVICE + "/request"
        string_to_sign = (
            "HMAC-SHA256\n"
            + x_date + "\n"
            + credential_scope + "\n"
            + hashed_canonical_request
        )

        k_date = hmac.new(self.access_key_secret.encode("utf-8"), short_date.encode("utf-8"), hashlib.sha256).digest()
        k_region = hmac.new(k_date, self.REGION.encode("utf-8"), hashlib.sha256).digest()
        k_service = hmac.new(k_region, self.SERVICE.encode("utf-8"), hashlib.sha256).digest()
        k_signing = hmac.new(k_service, b"request", hashlib.sha256).digest()

        signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        authorization = (
            "HMAC-SHA256 Credential=" + self.access_key_id + "/" + credential_scope
            + ", SignedHeaders=" + signed_headers
            + ", Signature=" + signature
        )

        return {
            "Authorization": authorization,
            "X-Date": x_date,
        }

    def _build_headers(self, method: str, action: str, body_json: str) -> dict:
        sign_headers = self._sign_request(method, action, body_json)
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Host": self.HOST,
            "X-Content-Sha256": hashlib.sha256(body_json.encode("utf-8")).hexdigest(),
        }
        headers.update(sign_headers)
        return headers

    def _do_request(self, action: str, payload: dict) -> dict:
        body_json = json.dumps(payload)
        url = "https://" + self.HOST + "/?Action=" + action + "&Version=" + self.VERSION

        for attempt in range(self.MAX_RETRIES):
            try:
                headers = self._build_headers("POST", action, body_json)
                resp = self.session.post(url, headers=headers, data=body_json.encode("utf-8"), timeout=30)
                resp.raise_for_status()
                result = resp.json()

                response_metadata = result.get("ResponseMetadata", {})
                if "Error" in response_metadata:
                    error = response_metadata["Error"]
                    raise Exception(f"API错误: {error.get('Code', 'Unknown')} - {error.get('Message', '未知错误')}")

                return result

            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logging.warning("请求失败，第 %d 次重试: %s", attempt + 1, str(e))
                    time.sleep(self.RETRY_DELAY * (2 ** attempt))
                else:
                    logging.exception("请求失败，已达到最大重试次数")
                    raise

    def batch_list_train_status(
        self,
        speaker_ids: Optional[List[str]] = None,
        state: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 10,
        next_token: Optional[str] = None,
        max_results: Optional[int] = None,
        order_time_start: Optional[int] = None,
        order_time_end: Optional[int] = None,
        expire_time_start: Optional[int] = None,
        expire_time_end: Optional[int] = None,
    ) -> dict:
        payload = {
            "AppID": self.appid,
            "PageNumber": page_number,
            "PageSize": page_size,
        }

        if speaker_ids is not None:
            payload["SpeakerIDs"] = speaker_ids
        if state is not None:
            payload["State"] = state
        if next_token is not None:
            payload["NextToken"] = next_token
        if max_results is not None:
            payload["MaxResults"] = max_results
        if order_time_start is not None:
            payload["OrderTimeStart"] = order_time_start
        if order_time_end is not None:
            payload["OrderTimeEnd"] = order_time_end
        if expire_time_start is not None:
            payload["ExpireTimeStart"] = expire_time_start
        if expire_time_end is not None:
            payload["ExpireTimeEnd"] = expire_time_end

        result = self._do_request("BatchListMegaTTSTrainStatus", payload)
        logging.info("查询音色训练状态成功，TotalCount: %s", result.get("Result", {}).get("TotalCount", 0))
        return result

    def order_access_resource_packs(
        self,
        times: int,
        quantity: int,
        resource_id: str = "volc.megatts.voiceclone",
        code: str = "Model_storage",
        auto_use_coupon: Optional[bool] = None,
        coupon_id: Optional[str] = None,
    ) -> dict:
        payload = {
            "AppID": int(self.appid),
            "ResourceID": resource_id,
            "Code": code,
            "Times": times,
            "Quantity": quantity,
        }

        if auto_use_coupon is not None:
            payload["AutoUseCoupon"] = auto_use_coupon
        if coupon_id is not None:
            payload["CouponID"] = coupon_id

        result = self._do_request("OrderAccessResourcePacks", payload)
        logging.info("音色下单成功，OrderIDs: %s", result.get("Result", {}).get("OrderIDs", []))
        return result

    def renew_access_resource_packs(
        self,
        times: int,
        speaker_ids: Optional[List[str]] = None,
        auto_use_coupon: Optional[bool] = None,
        coupon_id: Optional[str] = None,
    ) -> dict:
        payload = {
            "Times": times,
        }

        if speaker_ids is not None:
            payload["SpeakerIDs"] = speaker_ids
        if auto_use_coupon is not None:
            payload["AutoUseCoupon"] = auto_use_coupon
        if coupon_id is not None:
            payload["CouponID"] = coupon_id

        result = self._do_request("RenewAccessResourcePacks", payload)
        logging.info("音色续费成功，OrderIDs: %s", result.get("Result", {}).get("OrderIDs", []))
        return result
