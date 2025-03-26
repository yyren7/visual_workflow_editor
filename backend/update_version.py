#!/usr/bin/env python3
# backend/update_version.py - 更新系统版本信息的工具

import os
import sys
import json
import argparse
import datetime
from pathlib import Path

# 将父目录添加到Python路径以解决导入问题
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from backend.app.database import Base, engine, SessionLocal
from backend.app.models import VersionInfo

def update_version_from_file(file_path=None):
    """从version.json文件更新版本信息到数据库"""
    try:
        if file_path is None:
            # 默认使用workspace目录下的version.json
            workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            file_path = os.path.join(workspace_dir, 'version.json')
        
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                version_data = json.load(f)
                version = version_data.get('version', '0.0.0')
                last_updated = version_data.get('lastUpdated', str(datetime.date.today()))
                
                print(f"从文件 {file_path} 读取版本信息: {version}, {last_updated}")
                update_database(version, last_updated)
        else:
            print(f"错误: 文件 {file_path} 不存在")
            return False
        
        return True
    except Exception as e:
        print(f"从文件更新版本信息失败: {e}")
        return False

def update_database(version, last_updated):
    """更新数据库中的版本信息"""
    try:
        # 确保表存在
        Base.metadata.create_all(bind=engine)
        
        # 获取数据库会话
        db = SessionLocal()
        try:
            # 查找已有的版本记录
            db_version = db.query(VersionInfo).first()
            
            if db_version:
                # 更新现有记录
                db_version.version = version
                db_version.last_updated = last_updated
                print(f"更新数据库中的版本记录: {version}, {last_updated}")
            else:
                # 创建新记录
                db_version = VersionInfo(
                    version=version,
                    last_updated=last_updated
                )
                db.add(db_version)
                print(f"创建数据库版本记录: {version}, {last_updated}")
            
            db.commit()
            print(f"版本信息已成功保存到数据库")
            return True
        except Exception as e:
            db.rollback()
            print(f"保存到数据库时出错: {e}")
            return False
        finally:
            db.close()
    except Exception as e:
        print(f"连接数据库失败: {e}")
        return False

def update_version_file(version, last_updated=None):
    """更新version.json文件"""
    try:
        if last_updated is None:
            last_updated = str(datetime.date.today())
        
        # 准备版本数据
        version_data = {
            "version": version,
            "lastUpdated": last_updated
        }
        
        # 保存到文件
        workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(workspace_dir, 'version.json')
        
        with open(file_path, 'w') as f:
            json.dump(version_data, f, indent=2)
        
        print(f"版本信息已更新到文件: {file_path}")
        print(f"版本: {version}, 日期: {last_updated}")
        
        return True
    except Exception as e:
        print(f"更新版本文件失败: {e}")
        return False

def display_current_version():
    """显示当前版本信息"""
    try:
        db = SessionLocal()
        try:
            db_version = db.query(VersionInfo).first()
            if db_version:
                print(f"数据库中的版本信息:")
                print(f"  版本: {db_version.version}")
                print(f"  更新日期: {db_version.last_updated}")
                print(f"  创建时间: {db_version.created_at}")
                print(f"  最后更新: {db_version.updated_at}")
            else:
                print("数据库中没有版本信息记录")
        finally:
            db.close()
            
        # 查看文件中的版本
        workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(workspace_dir, 'version.json')
        
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                version_data = json.load(f)
                print(f"\n文件中的版本信息 ({file_path}):")
                print(f"  版本: {version_data.get('version', '未知')}")
                print(f"  更新日期: {version_data.get('lastUpdated', '未知')}")
        else:
            print(f"\n版本文件 {file_path} 不存在")
            
        return True
    except Exception as e:
        print(f"显示版本信息失败: {e}")
        return False

def main():
    """主函数，处理命令行参数"""
    parser = argparse.ArgumentParser(description="更新系统版本信息工具")
    
    # 创建互斥的参数组
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--from-file', action='store_true', help='从version.json文件更新版本信息到数据库')
    group.add_argument('--to-file', action='store_true', help='将命令行指定的版本信息更新到version.json文件')
    group.add_argument('--show', action='store_true', help='显示当前版本信息')
    
    # 版本和日期参数
    parser.add_argument('--version', type=str, help='指定版本号 (例如: 1.0.0)')
    parser.add_argument('--date', type=str, help='指定更新日期 (例如: 2025-03-15)')
    
    args = parser.parse_args()
    
    # 显示当前版本
    if args.show:
        return display_current_version()
    
    # 从文件更新到数据库
    if args.from_file:
        return update_version_from_file()
    
    # 更新到文件
    if args.to_file:
        if not args.version:
            print("错误: 使用--to-file选项时必须指定--version参数")
            return False
        return update_version_file(args.version, args.date)
    
    # 直接更新数据库
    if args.version:
        return update_database(args.version, args.date or str(datetime.date.today()))
    
    # 如果没有指定任何操作，显示帮助
    parser.print_help()
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 