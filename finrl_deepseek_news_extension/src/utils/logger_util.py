"""
統一的日誌記錄器配置
"""

import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

def setup_logger(name: str, config: Dict[str, Any]) -> logging.Logger:
    """
    設置並配置日誌記錄器
    
    Args:
        name: 記錄器名稱
        config: 日誌配置字典
        
    Returns:
        logging.Logger: 配置好的記錄器
    """
    # 創建記錄器
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, config.get('level', 'INFO')))
    
    # 清除現有的處理器以避免重複
    logger.handlers.clear()
    
    # 創建格式器
    formatter = logging.Formatter(
        config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    
    # 控制台處理器
    if config.get('console_enabled', True):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # 文件處理器
    if config.get('file_enabled', True):
        log_file_path = config.get('file_path', 'logs/application.log')
        
        # 確保日誌目錄存在
        log_dir = os.path.dirname(log_file_path)
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        
        # 使用輪轉文件處理器
        max_bytes = config.get('max_file_size_mb', 100) * 1024 * 1024  # 轉換為字節
        backup_count = config.get('backup_count', 5)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

class ProgressLogger:
    """
    進度記錄器，用於長時間運行的任務
    """
    
    def __init__(self, logger: logging.Logger, total_items: int, 
                 report_interval: int = 100):
        """
        初始化進度記錄器
        
        Args:
            logger: 日誌記錄器
            total_items: 總項目數
            report_interval: 報告間隔
        """
        self.logger = logger
        self.total_items = total_items
        self.report_interval = report_interval
        self.processed_items = 0
        self.start_time = datetime.now()
        self.last_report_time = self.start_time
    
    def update(self, count: int = 1) -> None:
        """
        更新進度
        
        Args:
            count: 增加的項目數量
        """
        self.processed_items += count
        
        # 檢查是否需要報告進度
        if (self.processed_items % self.report_interval == 0 or 
            self.processed_items == self.total_items):
            self._report_progress()
    
    def _report_progress(self) -> None:
        """報告當前進度"""
        current_time = datetime.now()
        elapsed_time = current_time - self.start_time
        
        # 計算進度百分比
        progress_percent = (self.processed_items / self.total_items) * 100
        
        # 估算剩餘時間
        if self.processed_items > 0:
            avg_time_per_item = elapsed_time.total_seconds() / self.processed_items
            remaining_items = self.total_items - self.processed_items
            estimated_remaining = remaining_items * avg_time_per_item
            
            eta_str = str(datetime.timedelta(seconds=int(estimated_remaining)))
        else:
            eta_str = "Unknown"
        
        # 計算處理速度
        time_since_last = (current_time - self.last_report_time).total_seconds()
        if time_since_last > 0:
            speed = self.report_interval / time_since_last
        else:
            speed = 0
        
        self.logger.info(
            f"進度: {self.processed_items}/{self.total_items} "
            f"({progress_percent:.1f}%) | "
            f"速度: {speed:.1f} items/sec | "
            f"已用時間: {str(elapsed_time).split('.')[0]} | "
            f"預估剩餘: {eta_str}"
        )
        
        self.last_report_time = current_time
    
    def finish(self) -> None:
        """完成進度記錄"""
        total_time = datetime.now() - self.start_time
        avg_speed = self.processed_items / max(total_time.total_seconds(), 1)
        
        self.logger.info(
            f"✅ 任務完成! 總計處理 {self.processed_items} 項目，"
            f"用時 {str(total_time).split('.')[0]}，"
            f"平均速度 {avg_speed:.2f} items/sec"
        )

class CostTracker:
    """
    成本追蹤器，用於監控API使用成本
    """
    
    def __init__(self, logger: logging.Logger, cost_limit: float = 100.0):
        """
        初始化成本追蹤器
        
        Args:
            logger: 日誌記錄器
            cost_limit: 成本上限（美元）
        """
        self.logger = logger
        self.cost_limit = cost_limit
        self.total_cost = 0.0
        self.api_calls = 0
        self.start_time = datetime.now()
    
    def add_cost(self, cost: float, api_name: str = "API") -> bool:
        """
        添加成本記錄
        
        Args:
            cost: 增加的成本
            api_name: API名稱
            
        Returns:
            bool: 是否未超過成本上限
        """
        self.total_cost += cost
        self.api_calls += 1
        
        # 檢查是否超過成本上限
        if self.total_cost >= self.cost_limit:
            self.logger.warning(
                f"⚠️ 成本警告: 已達成本上限 ${self.cost_limit:.2f}! "
                f"當前總成本: ${self.total_cost:.4f}"
            )
            return False
        
        # 當成本達到上限的80%時發出警告
        elif self.total_cost >= self.cost_limit * 0.8:
            self.logger.warning(
                f"⚠️ 成本警告: 已達成本上限80% "
                f"(${self.total_cost:.4f}/${self.cost_limit:.2f})"
            )
        
        # 每100次API調用報告一次成本
        if self.api_calls % 100 == 0:
            avg_cost_per_call = self.total_cost / self.api_calls
            self.logger.info(
                f"💰 成本更新: ${self.total_cost:.4f} "
                f"({self.api_calls} {api_name} calls, "
                f"avg ${avg_cost_per_call:.6f}/call)"
            )
        
        return True
    
    def get_summary(self) -> Dict[str, Any]:
        """
        獲取成本摘要
        
        Returns:
            Dict[str, Any]: 成本摘要
        """
        elapsed_time = datetime.now() - self.start_time
        
        return {
            'total_cost_usd': round(self.total_cost, 4),
            'total_api_calls': self.api_calls,
            'avg_cost_per_call': round(self.total_cost / max(self.api_calls, 1), 6),
            'cost_limit_usd': self.cost_limit,
            'cost_utilization_percent': round((self.total_cost / self.cost_limit) * 100, 2),
            'elapsed_time': str(elapsed_time).split('.')[0],
            'calls_per_minute': round(self.api_calls / max(elapsed_time.total_seconds() / 60, 1), 2)
        }

# 預設的記錄器配置
DEFAULT_LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file_enabled': True,
    'file_path': 'logs/finrl_extension.log',
    'console_enabled': True,
    'max_file_size_mb': 100,
    'backup_count': 5
}

if __name__ == "__main__":
    # 測試範例
    logger = setup_logger('test_logger', DEFAULT_LOGGING_CONFIG)
    
    logger.info("測試日誌記錄器")
    logger.warning("這是一個警告訊息")
    logger.error("這是一個錯誤訊息")
    
    # 測試進度記錄器
    progress = ProgressLogger(logger, 1000, report_interval=100)
    
    for i in range(1000):
        progress.update()
        if i % 100 == 99:  # 模擬一些處理時間
            import time
            time.sleep(0.01)
    
    progress.finish()
    
    # 測試成本追蹤器
    cost_tracker = CostTracker(logger, cost_limit=10.0)
    
    for i in range(150):
        cost_tracker.add_cost(0.05, "OpenAI")
    
    print("成本摘要:", cost_tracker.get_summary())
