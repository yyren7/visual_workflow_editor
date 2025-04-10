import json
import logging
import os
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError, ConfigDict
from backend.config import AI_CONFIG
from langchain_core.output_parsers import BaseOutputParser
import re
# 导入类型提示
from typing import TypeVar, Type, Optional, Tuple

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

# 从 DeepSeekLLM 导入（假设路径正确）
from backend.langchainchat.llms.deepseek_client import DeepSeekLLM

class StructuredOutputParser(BaseOutputParser[T]):
    """
    解析 LLM 调用的输出以根据提供的 Pydantic 模式提取结构化信息。
    """
    pydantic_object: Type[T] = Field(..., description="要解析成的 Pydantic 模型")
    llm_client: DeepSeekLLM = Field(..., description="用于调用的 DeepSeek LLM 客户端")

    # Add model_config to allow arbitrary types like DeepSeekLLM
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def get_format_instructions(self) -> str:
        """返回格式化指令。"""
        schema = self.pydantic_object.model_json_schema()

        # 移除模式中的 title 和 description，因为 Deepseek API 不支持它们
        reduced_schema = {k: v for k, v in schema.items() if k not in ('title', 'description')}

        schema_str = json.dumps(reduced_schema, indent=2)

        # 返回包含 JSON schema 的格式化指令字符串
        return (
            f"请严格按照以下 JSON schema 格式提取信息并输出:\n"
            f"```json\n"
            f"{schema_str}\n"
            f"```\n"
            f"请确保只输出有效的 JSON 对象，不要包含任何额外的解释或文本。"
        )

    def parse(self, text: str) -> T:
        """解析 LLM 输出的文本。"""
        try:
            # 尝试去除可能的代码块标记
            match = re.search(r"```(json)?\n(.*)```", text, re.DOTALL)
            if match:
                json_str = match.group(2).strip()
            else:
                # 如果没有代码块，假设整个文本是 JSON 或包含 JSON
                # 尝试找到第一个 '{' 和最后一个 '}' 之间的内容
                first_brace = text.find('{')
                last_brace = text.rfind('}')
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    json_str = text[first_brace:last_brace+1]
                else:
                    json_str = text # 无法智能提取，假设整个是 JSON
            
            logger.debug(f"Attempting to parse JSON: {json_str}")
            parsed_object = json.loads(json_str)
            return self.pydantic_object.model_validate(parsed_object)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}\n原始文本: {text}")
            raise ValueError(f"无法将文本解析为 JSON: {e}")
        except ValidationError as e:
            logger.error(f"Pydantic 验证失败: {e}\n解析出的对象: {parsed_object}")
            raise ValueError(f"生成的 JSON 对象不符合 Pydantic 模式: {e}")
        except Exception as e:
            logger.error(f"解析过程中发生未知错误: {e}\n原始文本: {text}")
            raise ValueError(f"解析输出时出错: {e}")

    async def call_llm_with_structured_output(self, prompt: str, system_prompt: Optional[str] = None) -> Tuple[Optional[T], bool]:
        """
        调用 LLM 获取结构化输出并解析。

        Args:
            prompt: 发送给 LLM 的主要提示。
            system_prompt: 可选的系统提示。

        Returns:
            一个元组 (解析后的 Pydantic 对象 | None, 是否成功)。
        """
        try:
            logger.info("使用结构化解析器调用 LLM")
            format_instructions = self.get_format_instructions()
            full_prompt = f"{prompt}\n\n{format_instructions}"
            
            # 准备消息
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": full_prompt})

            # 调用 LLM
            response_text, success = await self.llm_client.chat_completion(
                messages=messages,
                # 这里可以添加其他参数，如 temperature, max_tokens 等
            )

            if not success or not response_text:
                logger.error("LLM 调用失败或返回空响应")
                return None, False

            # 解析响应
            logger.info("尝试解析 LLM 响应")
            parsed_data = self.parse(response_text)
            logger.info("成功解析结构化输出")
            return parsed_data, True

        except ValueError as e:
            logger.error(f"结构化输出解析失败: {e}")
            return None, False
        except Exception as e:
            logger.error(f"调用 LLM 或解析时发生意外错误: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None, False

    @property
    def _type(self) -> str:
        return "structured_output_parser"