"""
提供多语言翻译功能的工具模块
"""
import os
from typing import Optional
import logging
import re

# 导入DeepSeek模型
from backend.langchainchat.models.llm import get_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# 配置日志
logger = logging.getLogger(__name__)

# 翻译器缓存
translation_cache = {}

class Translator:
    """
    多语言翻译器，使用DeepSeek模型进行翻译
    """
    
    def __init__(self):
        """初始化翻译器"""
        logger.info("初始化DeepSeek翻译器")
        
        # 初始化DeepSeek翻译器
        try:
            # 使用项目中已有的DeepSeek模型
            self.llm = get_chat_model()
            logger.info("成功初始化DeepSeek翻译器")
        except Exception as e:
            logger.error(f"初始化DeepSeek翻译器失败: {e}")
            self.llm = None
        
        # 语言代码到语言名称的映射
        self.language_map = {
            'en': 'English',
            'zh': 'Chinese',
            'ja': 'Japanese'
        }
    
    def detect_language(self, text: str) -> str:
        """
        检测文本的语言
        
        Args:
            text: 要检测的文本
            
        Returns:
            语言代码 ('en', 'zh', 'ja')
        """
        if not text or not self.llm:
            return "en"  # 默认返回英语
        
        # 简单的启发式检测 - 如果有足够多的中文字符，认为是中文
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        if chinese_chars > len(text) * 0.5:
            return "zh"
        
        # 如果有足够多的日文字符，认为是日文
        japanese_chars = len(re.findall(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]', text))
        if japanese_chars > len(text) * 0.5 and chinese_chars < len(text) * 0.5:
            return "ja"
        
        # 其他情况默认为英文
        return "en"
        
        # 注意：以上是简单的启发式检测，如果需要更准确的检测，可以使用LLM进行检测
        # 以下是使用LLM进行检测的代码，但为了性能考虑暂时注释掉
        # try:
        #     system_message = SystemMessage(content="""You are a language detector.
        # Your task is to identify the language of the given text.
        # Respond ONLY with the language code:
        # - 'en' for English
        # - 'zh' for Chinese
        # - 'ja' for Japanese
        # - 'unknown' if you can't determine
        # """)
        #     human_message = HumanMessage(content=f"Detect the language of this text: {text[:200]}...")
        #     messages = [system_message, human_message]
        #     response = self.llm.invoke(messages)
        #     detected = response.content.strip().lower()
        #     
        #     if 'en' in detected or 'english' in detected:
        #         return 'en'
        #     elif 'zh' in detected or 'chinese' in detected:
        #         return 'zh'
        #     elif 'ja' in detected or 'japanese' in detected:
        #         return 'ja'
        #     else:
        #         return 'en'  # 默认英语
        # except Exception as e:
        #     logger.error(f"语言检测失败: {e}")
        #     return 'en'  # 出错时默认英语
    
    def translate(self, text: str, target_language: str, source_language: Optional[str] = None) -> str:
        """
        使用DeepSeek模型翻译文本到目标语言
        
        Args:
            text: 要翻译的文本
            target_language: 目标语言代码 (如 'en', 'zh', 'ja')
            source_language: 源语言代码，可选
            
        Returns:
            翻译后的文本
        """
        # 如果没有文本或没有指定目标语言，直接返回原文
        if not text or not target_language:
            return text
        
        # 如果LLM不可用，直接返回原文
        if not self.llm:
            logger.warning("翻译器不可用，返回原始文本")
            return text
        
        # 检测源语言（如果未指定）
        detected_language = source_language or self.detect_language(text)
        
        # 如果检测到的语言与目标语言相同，则不需要翻译
        if detected_language == target_language:
            logger.info(f"检测到的语言({detected_language})与目标语言相同，无需翻译")
            return text
        
        target_lang_name = self.language_map.get(target_language, target_language)
        source_lang_hint = f" from {self.language_map.get(detected_language, 'the original language')}"
        
        try:
            # 构建提示信息
            system_message = SystemMessage(content=f"""You are a professional translator. 
Your task is to translate the given text to {target_lang_name}{source_lang_hint}.
Translate only the content, maintaining the original formatting as much as possible.
Do not add any explanations or notes - just return the translated text.
""")
            
            human_message = HumanMessage(content=text)
            
            # 调用LLM进行翻译
            messages = [system_message, human_message]
            response = self.llm.invoke(messages)
            
            # 返回翻译结果
            translated_text = response.content.strip()
            logger.info(f"翻译完成: {detected_language} -> {target_language}, {len(text)} 字符 -> {len(translated_text)} 字符")
            return translated_text
            
        except Exception as e:
            logger.error(f"使用DeepSeek翻译失败: {e}")
            # 如果翻译失败，返回原文
            return text

# 创建翻译器实例
translator = Translator() 