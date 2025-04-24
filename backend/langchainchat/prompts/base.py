import logging

logger = logging.getLogger(__name__)

# BasePromptService 类已确认未被使用，在此移除
# class BasePromptService:
#     """
#     基础Prompt处理服务
#     处理prompt模板、变量替换和通用处理逻辑
#     """
#     
#     def process_template(self, prompt_template: str, variables: Dict[str, Any]) -> str:
#         """
#         处理prompt模板，替换变量
#         
#         Args:
#             prompt_template: 包含变量占位符的模板
#             variables: 变量名和值的字典
#             
#         Returns:
#             处理后的prompt字符串
#         """
#         try:
#             processed_prompt = prompt_template
#             for key, value in variables.items():
#                 placeholder = f"{{{key}}}"
#                 if isinstance(value, dict):
#                     value = json.dumps(value, ensure_ascii=False)
#                 processed_prompt = processed_prompt.replace(placeholder, str(value))
#             return processed_prompt
#         except Exception as e:
#             logger.error(f"处理prompt模板时出错: {str(e)}")
#             return prompt_template
#     
#     def combine_prompts(self, prompts: list[str], separator: str = "\n\n") -> str:
#         """
#         组合多个prompt
#         
#         Args:
#             prompts: prompt字符串列表
#             separator: 分隔符
#             
#         Returns:
#             组合后的prompt
#         """
#         return separator.join([p for p in prompts if p]) 