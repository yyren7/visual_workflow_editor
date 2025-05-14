from database.connection import get_db
from backend.app.services.flow_service import FlowService

flow_service = FlowService(next(get_db()))
flows = flow_service.get_flows()

print('流程列表:')
for flow in flows:
    flow_id = flow.id
    name = flow.name
    # 先获取流程的详细信息
    flow_detail = flow_service.get_flow(flow_id)
    nodes = flow_detail.get('nodes', [])
    print(f'ID: {flow_id}, 名称: {name}, 节点数: {len(nodes)}')
    
    # 检查是否有最新创建的节点
    latest_node_id = 'loop-1743664177011'
    found = False
    for node in nodes:
        if node.get('id') == latest_node_id:
            found = True
            print(f'  找到节点 {latest_node_id} 在流程 {flow_id} 中')
            print(f'  节点详情: {node}')
            break
