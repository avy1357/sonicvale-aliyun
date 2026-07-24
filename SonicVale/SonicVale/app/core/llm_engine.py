# app/core/llm_engine.py
import json
import logging
import re
import time
import random
from openai import OpenAI

from app.core.prompts import get_auto_fix_json_prompt


class LLMEngine:
    def __init__(self, api_key: str, base_url: str, model_name: str, custom_params: str):
        """
        api_key: LLM API Key
        base_url: OpenAI-compatible API URL（例如企业版/自建 LLM）
        model_name: 模型名称
        custom_params: 自定义参数（JSON字符串）
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")  # 去掉末尾斜杠
        self.model_name = model_name
        
        # custom_params从string转为dict，添加异常处理
        try:
            custom_params = json.loads(custom_params)
            if not isinstance(custom_params, dict):
                raise ValueError("无效的 custom_params")
        except json.JSONDecodeError as e:
            logging.error("custom_params JSON解析失败: %s, 使用默认值", str(e))
            custom_params = {
                "response_format": {"type": "json_object"},
                "temperature": 0.7,
                "top_p": 0.9
            }
        self.custom_params = custom_params
        
        # 使用新版 OpenAI 客户端
        self.client = OpenAI(
            api_key=api_key,
            base_url=self.base_url
        )

    def _extract_result_tag(self, text: str) -> str:
        """提取 <result> 标签内容"""
        match = re.search(r"<result>(.*?)</result>", text, re.DOTALL)
        if not match:
            raise ValueError("Response does not contain <result>...</result> tag")
        return match.group(1).strip()

    def generate_text_test(self, prompt: str) -> str:
        """
        测试：生成结果并返回（非流式）
        """
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            timeout=120,
            **self.custom_params
        )
        return response.choices[0].message.content
    def generate_text(self, prompt: str, retries: int = 3, delay: float = 1.0) -> str:
        """
        非流式生成：直接获取完整响应
        """
        for attempt in range(retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    stream=False,
                    timeout=120,
                    **self.custom_params
                )

                full_text = response.choices[0].message.content
                return full_text

            except Exception as e:
                if attempt < retries - 1:
                    sleep_time = delay * (2 ** attempt) + random.random()
                    time.sleep(sleep_time)
                else:
                    raise e
        # 理论上不会到达此处，显式抛出避免隐式返回 None
        raise RuntimeError("generate_text: 重试耗尽但未返回结果")

    def save_load_json(self, json_str: str, depth: int = 0, max_depth: int = 2):
        """解析JSON，支持自动提取<result>标签内容。

        Args:
            json_str: 待解析的 JSON 字符串
            depth: 当前递归深度
            max_depth: 最大递归深度，超过则抛出原始 JSONDecodeError

        Raises:
            json.JSONDecodeError: 超过最大重试深度仍无法解析时抛出
        """
        # 先尝试提取 <result> 标签内容
        try:
            json_str = self._extract_result_tag(json_str)
        except ValueError:
            # 没有 <result> 标签，直接使用原文本
            pass

        # 尝试加载json
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # 超过最大深度，直接抛出避免无限递归
            if depth >= max_depth:
                logging.error("save_load_json 超过最大重试深度 %d，放弃修复", max_depth)
                raise
            # JSON解析失败，尝试让LLM修复
            prompt = get_auto_fix_json_prompt(json_str)
            res = self.generate_text(prompt)
            # 递归调用，修复后的结果也可能包含 <result> 标签
            return self.save_load_json(res, depth=depth + 1, max_depth=max_depth)

    def generate_smart_text(self, prompt: str) -> str:
        """
        智能文本生成（流式）
        """
        stream = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            timeout=120
        )

        # 拼接 delta.content
        full_text = ""
        for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                content = delta.content if hasattr(delta, 'content') else None
                if content:
                    # print(content, end="", flush=True)
                    full_text += content

        logging.debug("流式生成完成")
        return full_text
