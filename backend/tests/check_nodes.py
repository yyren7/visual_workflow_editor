from database.connection import get_db
from backend.app.services.flow_service import FlowService

flow_id = '30a17510-07bf-4371-aa18-6583ad908aa4'
flow_service = FlowService(next(get_db()))
flow = flow_service.get_flow(flow_id)
nodes = flow.get('nodes', [])

print(f'节点总数: {len(nodes)}')
for i, node in enumerate(nodes):
    print(f'{i+1}. ID: {node.get("id")}, 类型: {node.get("type")}, 位置: {node.get("position")}')

# 检查最新创建的节点
latest_node_id = 'moveL-1743056232559'
found = False
for node in nodes:
    if node.get('id') == latest_node_id:
        found = True
        print(f'\n找到最新节点: {latest_node_id}')
        print(f'节点详情: {node}')
        break

if not found:
    print(f'\n找不到最新节点: {latest_node_id}') 