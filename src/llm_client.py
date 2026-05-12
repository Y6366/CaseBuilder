"""
LLM Client — 统一的LLM调用接口，支持OpenAI API兼容模型。

论文设置:
- temperature = 0.0 (确保可复现性)
- top_p = 1.0 (保持受控多样性)
- frequency_penalty = 0.0
- presence_penalty = 0.0
"""

import os
import json
from openai import OpenAI


class LLMClient:
    """统一的LLM客户端，支持OpenAI API兼容的任意模型。"""

    def __init__(
        self,
        model: str = None,
        api_key: str = None,
        base_url: str = None,
    ):
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o")
        self.client = OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url or os.getenv("OPENAI_BASE_URL", None),
        )

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        top_p: float = 1.0,
        max_tokens: int = 4096,
    ) -> str:
        """调用LLM生成文本。"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            top_p=top_p,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        top_p: float = 1.0,
        max_tokens: int = 4096,
    ) -> dict:
        """调用LLM生成JSON格式输出，自动解析。"""
        text = self.generate(system_prompt, user_prompt, temperature, top_p, max_tokens)
        # 尝试从markdown代码块中提取JSON
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())
