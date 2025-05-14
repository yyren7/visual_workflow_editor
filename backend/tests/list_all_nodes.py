from database.connection import get_db
from backend.app.services.flow_service import FlowService

flow_id = 'ed10ef28-ad53-41c0-860f-f359e3ea9640'
flow_service = FlowService(next(get_db()))
flow = flow_service.get_flow(flow_id)
nodes = flow.get('nodes', [])

print(f'流程 {flow_id} 的节点总数: {len(nodes)}')
print(f'流程 {flow_id} 的原始内容: {flow}')
print('所有节点详细信息:')
for i, node in enumerate(nodes):
    print(f'{i+1}. ID: {node.get("id")}')
    print(f'   类型: {node.get("type")}')
    print(f'   位置: {node.get("position")}')
    print(f'   数据: {node.get("data", {})}')
    print('---') 