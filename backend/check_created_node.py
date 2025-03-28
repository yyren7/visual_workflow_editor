from database.connection import get_db
from backend.app.services.flow_service import FlowService

flow_id = '30a17510-07bf-4371-aa18-6583ad908aa4'
node_id = 'moveL-1743056408817'  # 最新创建的节点ID

flow_service = FlowService(next(get_db()))
flow = flow_service.get_flow(flow_id)
nodes = flow.get('nodes', [])

print(f'流程 {flow_id} 中的节点总数: {len(nodes)}')
print(f'所有节点ID:')
for i, node in enumerate(nodes):
    print(f'{i+1}. {node.get("id")}')

# 检查指定节点
found = False
for node in nodes:
    if node.get('id') == node_id:
        found = True
        print(f'\n找到节点 {node_id}:')
        print(f'节点类型: {node.get("type")}')
        print(f'节点位置: {node.get("position")}')
        print(f'节点数据: {node.get("data", {})}')
        break

if not found:
    print(f'\n未找到节点 {node_id}')
else:
    # 如果找到了，检查节点是否已保存到数据库
    try:
        # 重新加载流程，确保数据是最新的
        flow_refreshed = flow_service.get_flow(flow_id)
        nodes_refreshed = flow_refreshed.get('nodes', [])
        found_refreshed = any(node.get('id') == node_id for node in nodes_refreshed)
        print(f'\n重新加载后，节点 {node_id} {"仍然存在" if found_refreshed else "不存在"}')
    except Exception as e:
        print(f'检查数据库时出错: {e}') 