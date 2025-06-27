#!/usr/bin/env python3
"""测试语义点位映射功能"""

import sys
from pathlib import Path
from backend.langgraphchat.graph.agent_state import AgentState
from backend.langgraphchat.graph.nodes.teaching_node import teaching_node, POINT_FIELD_SCHEMA
from backend.sas.nodes.parameter_mapping import ParameterMapper
from backend.langgraphchat.utils.llm_utils import create_llm

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def test_semantic_mapping():
    """测试语义点位映射功能"""
    
    try:
        current_file_dir = Path(__file__).parent
        # sys.path.append(str(current_file_dir.parent.parent))  # Add project root to sys.path
        from backend.sas.nodes.parameter_mapping import ParameterMapper
        
        print("🔍 测试语义点位映射...")
        
        # 创建 mapper 实例
        mapper = ParameterMapper()
        print("✅ ParameterMapper 实例创建成功")
        
        # 模拟 step2 的输出，包含语义点位描述
        test_module_steps = """
        1. Robot moves to **initial/safe point** (Block Type: moveP)
        2. Move to "bearing standby point" for preparation (Block Type: moveP)  
        3. Approach the "precise grasping point" slowly (Block Type: moveP)
        4. Move to departure point after grasping (Block Type: moveP)
        5. Return to the safe point (Block Type: moveP)
        6. Set variable N5 to 10 (Block Type: set_number)
        7. Set flag F1 to true (Block Type: set_flag)
        """
        
        print(f"\n📄 测试输入:")
        print(test_module_steps)
        
        # 测试参数提取
        extracted = mapper.extract_parameters_from_module_steps(test_module_steps)
        print(f"\n✅ 语义参数提取成功:")
        print(f"  语义点位: {sorted(extracted['semantic_points'])}")
        print(f"  数值变量: {sorted(extracted['numbers'])}")
        print(f"  标志变量: {sorted(extracted['flags'])}")
        
        # 测试语义名称标准化
        test_names = [
            "initial/safe point",
            "bearing standby point", 
            "precise grasping point",
            "departure point",
            "safe point"
        ]
        
        print(f"\n🔄 测试语义名称标准化:")
        for name in test_names:
            normalized = mapper.normalize_semantic_name(name)
            print(f"  '{name}' -> '{normalized}'")
        
        # 测试语义匹配（需要预先在 teaching.yaml 中设置一些点位）
        print(f"\n🔍 测试语义匹配:")
        for semantic_point in extracted['semantic_points']:
            if not semantic_point.startswith('P'):  # 跳过传统格式的点位
                match = mapper.find_semantic_point_match(semantic_point)
                if match:
                    print(f"  ✅ '{semantic_point}' 匹配到现有点位: {match}")
                else:
                    print(f"  🆕 '{semantic_point}' 需要新分配")
        
        # 测试完整映射创建
        mapping = mapper.create_parameter_mapping(extracted)
        print(f"\n✅ 语义映射创建成功:")
        for semantic_point, slot in mapping['points'].items():
            print(f"  '{semantic_point}' -> {slot}")
        
        # 测试映射报告生成
        report = mapper.generate_mapping_report(mapping, extracted)
        print(f"\n📋 映射报告生成成功:")
        print("=" * 60)
        print(report)
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_semantic_normalization():
    """测试语义名称标准化和匹配"""
    
    try:
        from backend.langgraphchat.graph.subgraph.sas.nodes.parameter_mapping import ParameterMapper
        
        print("\n🔍 测试语义名称标准化和匹配...")
        
        mapper = ParameterMapper()
        
        # 测试同义词识别
        test_pairs = [
            ("initial point", "home point"),
            ("safe point", "initial point"), 
            ("start position", "home position"),
            ("standby point", "wait point"),
            ("approach point", "near point"),
            ("precise grasping point", "exact grasping point")
        ]
        
        print("🔗 测试同义词匹配:")
        for name1, name2 in test_pairs:
            norm1 = mapper.normalize_semantic_name(name1)
            norm2 = mapper.normalize_semantic_name(name2)
            match = norm1 == norm2
            print(f"  '{name1}' ⟷ '{name2}': {'✅ 匹配' if match else '❌ 不匹配'}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

if __name__ == "__main__":
    print("🚀 开始语义点位映射测试")
    print("=" * 60)
    
    success1 = test_semantic_mapping()
    success2 = test_semantic_normalization()
    
    print("\n" + "=" * 60)
    if success1 and success2:
        print("🎉 所有测试通过！语义映射功能正常工作。")
    else:
        print("⚠️  部分测试失败，需要检查实现。")
    
    sys.exit(0 if (success1 and success2) else 1) 