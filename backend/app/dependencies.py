from backend.app.services.node_template_service import NodeTemplateService

# 单例模式存储NodeTemplateService实例
_node_template_service = None

def get_node_template_service() -> NodeTemplateService:
    """
    获取NodeTemplateService实例的依赖函数
    
    每次应用启动只创建一个实例，遵循单例模式
    
    返回:
        NodeTemplateService: 节点模板服务实例
    """
    global _node_template_service
    if _node_template_service is None:
        _node_template_service = NodeTemplateService()
        _node_template_service.load_templates()
    return _node_template_service 