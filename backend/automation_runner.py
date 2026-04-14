import schedule
import time
import subprocess
import logging
from datetime import datetime, timedelta
from pathlib import Path
import json
import requests
from typing import List, Dict, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/automation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PremierLeagueAutomation:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.data_dir = self.base_dir / "data"
        self.data_dir.mkdir(exist_ok=True)
        
        # 配置文件路径
        self.config_file = self.data_dir / "automation_config.json"
        self.last_run_file = self.data_dir / "last_run.json"
        
        # 脚本路径
        self.scripts = {
            'player_premier_250': self.base_dir / "player_premier_250.py",
            'player_premier_team_200': self.base_dir / "player_premier_team_200.py",
            'merge_data': self.base_dir / "merge_player_data.py"
        }
        
        # 加载配置
        self.config = self.load_config()
        
    def load_config(self) -> Dict:
        """加载配置文件"""
        default_config = {
            "check_interval_minutes": 30,  # 检查间隔（分钟）
            "match_check_urls": [
                "https://www.premierleague.com/matchweek/4743",  # 示例URL，需要更新
                "https://api.football-data.org/v4/competitions/PL/matches"  # 备用API
            ],
            "run_times": ["02:00", "14:00", "20:00"],  # 每日运行时间
            "scripts_to_run": ["player_premier_250", "player_premier_team_200", "merge_data"],
            "notification_email": None,  # 可选：通知邮箱
            "max_retries": 3,
            "retry_delay_minutes": 5
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # 合并默认配置
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
            except Exception as e:
                logger.error(f"加载配置文件失败: {e}")
                return default_config
        else:
            # 创建默认配置文件
            self.save_config(default_config)
            return default_config
    
    def save_config(self, config: Dict):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
    
    def load_last_run(self) -> Dict:
        """加载上次运行记录"""
        if self.last_run_file.exists():
            try:
                with open(self.last_run_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载运行记录失败: {e}")
        return {}
    
    def save_last_run(self, run_info: Dict):
        """保存运行记录"""
        try:
            with open(self.last_run_file, 'w', encoding='utf-8') as f:
                json.dump(run_info, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存运行记录失败: {e}")
    
    def check_for_new_matches(self) -> bool:
        """
        通过 football-data.org 免费 API 检查近 3 天内是否有英超比赛已结束 (status=FINISHED)，
        且该场比赛在上次运行后才结束。

        需要在环境变量 FOOTBALL_DATA_API_KEY 中设置 API key（免费注册即可）。
        https://www.football-data.org/
        """
        import os
        api_key = os.environ.get("FOOTBALL_DATA_API_KEY", "")
        if not api_key:
            logger.warning("未设置 FOOTBALL_DATA_API_KEY，跳过比赛检测，使用定时运行模式")
            return False

        logger.info("通过 football-data.org 检查近期英超比赛...")
        last_run = self.load_last_run()
        last_triggered = last_run.get("last_match_triggered_run", "")

        try:
            now = datetime.utcnow()
            date_from = (now - timedelta(days=3)).strftime("%Y-%m-%d")
            date_to = now.strftime("%Y-%m-%d")

            resp = requests.get(
                "https://api.football-data.org/v4/competitions/PL/matches",
                headers={"X-Auth-Token": api_key},
                params={"status": "FINISHED", "dateFrom": date_from, "dateTo": date_to},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            matches = data.get("matches", [])

            if not matches:
                logger.info("近期无已完赛的英超比赛")
                return False

            # 取最近一场比赛的结束时间
            # football-data.org 以 utcDate 字段标记比赛时间
            latest_match_time_str = max(m["utcDate"] for m in matches)
            latest_match_time = datetime.fromisoformat(latest_match_time_str.replace("Z", "+00:00")).replace(tzinfo=None)

            # 假设比赛持续约 2 小时，赛后统计数据需再等 1 小时
            available_after = latest_match_time + timedelta(hours=3)
            if now < available_after:
                logger.info(f"最近一场比赛 {latest_match_time_str} 数据尚未稳定，等待至 {available_after} UTC")
                return False

            # 判断这场比赛是否在上次触发之后
            if last_triggered:
                last_triggered_time = datetime.fromisoformat(last_triggered)
                if latest_match_time <= last_triggered_time:
                    logger.info("未发现新完赛比赛（最近一场早于上次触发时间）")
                    return False

            logger.info(f"检测到新完赛比赛，最近一场: {latest_match_time_str}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"调用 football-data.org 失败: {e}")
            return False
        except Exception as e:
            logger.error(f"比赛检测时出错: {e}")
            return False
    
    def run_script(self, script_name: str) -> bool:
        """运行指定脚本"""
        if script_name not in self.scripts:
            logger.error(f"未知脚本: {script_name}")
            return False
        
        script_path = self.scripts[script_name]
        if not script_path.exists():
            logger.error(f"脚本文件不存在: {script_path}")
            return False
        
        logger.info(f"开始运行脚本: {script_name}")
        
        max_retries = self.config.get('max_retries', 3)
        retry_delay = self.config.get('retry_delay_minutes', 5)
        
        for attempt in range(max_retries):
            try:
                result = subprocess.run(
                    ['python3', str(script_path)],
                    cwd=str(self.base_dir),
                    capture_output=True,
                    text=True,
                    timeout=300  # 5分钟超时
                )
                
                if result.returncode == 0:
                    logger.info(f"脚本 {script_name} 运行成功")
                    logger.debug(f"输出: {result.stdout}")
                    return True
                else:
                    logger.error(f"脚本 {script_name} 运行失败 (尝试 {attempt + 1}/{max_retries})")
                    logger.error(f"错误输出: {result.stderr}")
                    
                    if attempt < max_retries - 1:
                        logger.info(f"{retry_delay}分钟后重试...")
                        time.sleep(retry_delay * 60)
                        
            except subprocess.TimeoutExpired:
                logger.error(f"脚本 {script_name} 运行超时 (尝试 {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * 60)
            except Exception as e:
                logger.error(f"运行脚本 {script_name} 时出错: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * 60)
        
        return False
    
    def run_all_scripts(self) -> bool:
        """运行所有配置的脚本"""
        scripts_to_run = self.config.get('scripts_to_run', [])
        
        if not scripts_to_run:
            logger.warning("没有配置要运行的脚本")
            return False
        
        logger.info(f"开始运行 {len(scripts_to_run)} 个脚本...")
        
        success_count = 0
        for script_name in scripts_to_run:
            if self.run_script(script_name):
                success_count += 1
            else:
                logger.error(f"脚本 {script_name} 运行失败")
                # 可以选择继续或停止
                # break
        
        logger.info(f"成功运行 {success_count}/{len(scripts_to_run)} 个脚本")
        return success_count == len(scripts_to_run)
    
    def scheduled_run(self):
        """定时运行"""
        logger.info("执行定时运行...")
        
        # 运行所有脚本
        success = self.run_all_scripts()
        
        # 保存运行记录
        run_info = {
            'last_scheduled_run': datetime.now().isoformat(),
            'success': success,
            'scripts_run': self.config.get('scripts_to_run', [])
        }
        self.save_last_run(run_info)
        
        if success:
            logger.info("定时运行完成")
        else:
            logger.error("定时运行部分失败")
    
    def match_triggered_run(self):
        """比赛触发的运行"""
        logger.info("检测到新比赛，触发运行...")
        
        # 运行所有脚本
        success = self.run_all_scripts()
        
        # 保存运行记录
        run_info = {
            'last_match_triggered_run': datetime.now().isoformat(),
            'success': success,
            'scripts_run': self.config.get('scripts_to_run', []),
            'last_match_check': datetime.now().isoformat()
        }
        self.save_last_run(run_info)
        
        if success:
            logger.info("比赛触发运行完成")
        else:
            logger.error("比赛触发运行部分失败")
    
    def setup_schedule(self):
        """设置定时任务"""
        logger.info("设置定时任务...")
        
        # 设置每日运行时间
        run_times = self.config.get('run_times', [])
        for run_time in run_times:
            try:
                schedule.every().day.at(run_time).do(self.scheduled_run)
                logger.info(f"设置每日运行时间: {run_time}")
            except Exception as e:
                logger.error(f"设置运行时间 {run_time} 失败: {e}")
        
        # 设置比赛检查间隔
        check_interval = self.config.get('check_interval_minutes', 30)
        schedule.every(check_interval).minutes.do(self.check_matches_and_run)
        logger.info(f"设置比赛检查间隔: {check_interval} 分钟")
    
    def check_matches_and_run(self):
        """检查比赛并决定是否运行"""
        try:
            if self.check_for_new_matches():
                self.match_triggered_run()
        except Exception as e:
            logger.error(f"检查比赛时出错: {e}")
    
    def run(self):
        """主运行循环"""
        logger.info("启动英超数据自动化系统")
        logger.info(f"配置: {json.dumps(self.config, indent=2, ensure_ascii=False)}")
        
        # 设置定时任务
        self.setup_schedule()
        
        logger.info("自动化系统已启动，等待定时任务...")
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次
        except KeyboardInterrupt:
            logger.info("收到停止信号，正在关闭...")
        except Exception as e:
            logger.error(f"运行时出错: {e}")
        finally:
            logger.info("自动化系统已停止")

def main():
    """主函数"""
    automation = PremierLeagueAutomation()
    
    # 可以选择不同的运行模式
    import sys
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == "once":
            # 立即运行一次
            logger.info("立即运行模式")
            automation.run_all_scripts()
        elif mode == "check":
            # 只检查比赛
            logger.info("检查比赛模式")
            automation.check_for_new_matches()
        else:
            print("可用模式: once, check")
            print("默认模式: 持续运行")
    else:
        # 默认：持续运行
        automation.run()

if __name__ == "__main__":
    main()
