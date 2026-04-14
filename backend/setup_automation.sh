#!/bin/bash

echo "英超数据自动化系统安装脚本"
echo "================================"

# 检查Python版本
python3 --version
if [ $? -ne 0 ]; then
    echo "错误: 未找到Python3，请先安装Python3"
    exit 1
fi

# 激活虚拟环境（如果存在）
if [ -d "bin" ]; then
    echo "激活虚拟环境..."
    source bin/activate
fi

# 安装必要的依赖包
echo "安装依赖包..."
pip3 install schedule requests pandas beautifulsoup4 lxml openpyxl

echo "安装完成！"
echo ""
echo "使用方法："
echo "1. 立即运行一次所有脚本："
echo "   python3 automation_runner.py once"
echo ""
echo "2. 检查是否有新比赛："
echo "   python3 automation_runner.py check"
echo ""
echo "3. 启动持续运行（推荐）："
echo "   python3 automation_runner.py"
echo ""
echo "配置文件位置: data/automation_config.json"
echo "日志文件位置: data/automation.log"
