#!/usr/bin/env python3
"""
批量国际化nodes目录中的组件文件
"""

import os
import re
from pathlib import Path

def update_generic_node():
    """更新GenericNode.tsx"""
    file_path = Path("frontend/src/components/nodes/GenericNode.tsx")
    
    if not file_path.exists():
        return
    
    content = file_path.read_text(encoding='utf-8')
    
    # 添加import语句
    if "useTranslation" not in content:
        content = content.replace(
            "import { Card, CardContent, Typography, Box, Tooltip } from '@mui/material';",
            "import { Card, CardContent, Typography, Box, Tooltip } from '@mui/material';\nimport { useTranslation } from 'react-i18next';"
        )
    
    # 添加hook
    if "const { t } = useTranslation();" not in content:
        content = content.replace(
            "const GenericNode = memo(({ data, isConnectable, selected }: NodeProps<GenericNodeData>) => {\n  // console.log('GenericNode data:', data); // Remove this debug log",
            "const GenericNode = memo(({ data, isConnectable, selected }: NodeProps<GenericNodeData>) => {\n  // console.log('GenericNode data:', data); // Remove this debug log\n  const { t } = useTranslation();"
        )
    
    # 替换硬编码文本
    replacements = [
        ("return 'none';", "return t('nodes.generic.none');"),
        ("return '✓';", "return t('nodes.generic.booleanTrue');"),
        ("return '✗';", "return t('nodes.generic.booleanFalse');"),
        ("], []);", "], [t]);")
    ]
    
    for old, new in replacements:
        content = content.replace(old, new)
    
    file_path.write_text(content, encoding='utf-8')
    print(f"✓ 已更新 {file_path}")

def update_detail_node():
    """更新LangGraphDetailNode.tsx"""
    file_path = Path("frontend/src/components/nodes/LangGraphDetailNode.tsx")
    
    if not file_path.exists():
        return
    
    content = file_path.read_text(encoding='utf-8')
    
    # 添加import语句
    if "useTranslation" not in content:
        content = content.replace(
            "import { useAgentStateSync } from '../../hooks/useAgentStateSync';",
            "import { useAgentStateSync } from '../../hooks/useAgentStateSync';\nimport { useTranslation } from 'react-i18next';"
        )
    
    # 添加hook
    if "const { t } = useTranslation();" not in content:
        content = content.replace(
            "export const LangGraphDetailNode: React.FC<LangGraphDetailNodeProps> = ({ id, data, selected }) => {",
            "export const LangGraphDetailNode: React.FC<LangGraphDetailNodeProps> = ({ id, data, selected }) => {\n  const { t } = useTranslation();"
        )
    
    # 替换硬编码文本
    replacements = [
        ('label="详情步骤"', 'label={t(\'nodes.detail.chipLabel\')}'),
        ('{data.taskName} - 模块步骤', '{data.taskName} - {t(\'nodes.detail.moduleSteps\')}'),
        ('label="步骤"', 'label={t(\'nodes.detail.step\')}'),
        ('primary={`步骤 ${index + 1}`}', 'primary={t(\'nodes.detail.stepNumber\', { number: index + 1 })}'),
        ('还没有步骤详情', '{t(\'nodes.detail.noStepsYet\')}'),
        ('添加步骤', '{t(\'nodes.detail.addStep\')}'),
        ('`${details.length} 个步骤`', 't(\'nodes.detail.stepsCount\', { count: details.length })'),
        ('点击查看详情', 't(\'nodes.detail.clickToView\')'),
        ('添加新步骤', '{t(\'nodes.detail.addNewStep\')}'),
        ('label="步骤描述"', 'label={t(\'nodes.detail.stepDescription\')}'),
        ('取消', '{t(\'nodes.detail.cancel\')}'),
        ('添加', '{t(\'nodes.detail.add\')}')
    ]
    
    for old, new in replacements:
        content = content.replace(old, new)
    
    file_path.write_text(content, encoding='utf-8')
    print(f"✓ 已更新 {file_path}")

def update_task_node():
    """更新LangGraphTaskNode.tsx"""
    file_path = Path("frontend/src/components/nodes/LangGraphTaskNode.tsx")
    
    if not file_path.exists():
        return
    
    content = file_path.read_text(encoding='utf-8')
    
    # 添加import语句
    if "useTranslation" not in content:
        content = content.replace(
            "import { selectActiveLangGraphStreamFlowId } from '../../store/slices/flowSlice';",
            "import { selectActiveLangGraphStreamFlowId } from '../../store/slices/flowSlice';\nimport { useTranslation } from 'react-i18next';"
        )
    
    # 添加hook
    if "const { t } = useTranslation();" not in content:
        content = content.replace(
            "export const LangGraphTaskNode: React.FC<LangGraphTaskNodeProps> = ({ id, data, selected }) => {",
            "export const LangGraphTaskNode: React.FC<LangGraphTaskNodeProps> = ({ id, data, selected }) => {\n  const { t } = useTranslation();"
        )
    
    # 替换硬编码文本
    replacements = [
        ('Task {data.taskIndex + 1}:', 't(\'nodes.task.taskPrefix\') + \' \' + (data.taskIndex + 1) + \':'),
        ('类型: {editedTask.type}', 't(\'nodes.task.type\') + \' \' + editedTask.type'),
        ('子任务 ({editedTask.sub_tasks.length}):', 't(\'nodes.task.subTasksCount\', { count: editedTask.sub_tasks.length }) + \':'),
        ('label="任务名称"', 'label={t(\'nodes.task.taskName\')}'),
        ('label="任务类型"', 'label={t(\'nodes.task.taskType\')}'),
        ('label="任务描述"', 'label={t(\'nodes.task.taskDescription\')}'),
        ('label="子任务 (逗号分隔)"', 'label={t(\'nodes.task.subTasksInput\')}'),
        ('Generating Details...', '{t(\'nodes.task.generatingDetails\')}')
    ]
    
    for old, new in replacements:
        content = content.replace(old, new)
    
    file_path.write_text(content, encoding='utf-8')
    print(f"✓ 已更新 {file_path}")

def main():
    """主函数"""
    print("开始国际化nodes目录中的组件...")
    
    # 更改到工作区目录
    os.chdir("/workspace")
    
    try:
        update_generic_node()
        update_detail_node() 
        update_task_node()
        print("\n✅ 所有节点组件国际化完成!")
    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    main() 