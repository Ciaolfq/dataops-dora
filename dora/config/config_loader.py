"""
单例配置加载器
支持从 YAML 文件加载配置，并提供全局访问入口
支持环境变量替换（如 ${ENV_VAR:default_value}）
"""

import os
import re
import yaml
from typing import Any, Dict, Optional
from pathlib import Path


class Config:
    """
    单例配置类
    确保整个应用程序中只有一个配置实例
    """

    _instance: Optional["Config"] = None
    _initialized: bool = False
    cfg: Dict[str, Any] = {}

    def __new__(cls) -> "Config":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._load_config()

    def _load_config(self) -> None:
        """从 YAML 文件加载配置"""
        # 优先使用环境变量指定的配置路径
        config_path = os.environ.get("DORA_CONFIG_PATH")

        if not config_path:
            # 默认路径：项目根目录下的 config/settings.yaml
            base_dir = Path(__file__).resolve().parent.parent
            config_path = base_dir / "config" / "settings.yaml"

        config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(
                f"配置文件不存在: {config_path}. "
                f"请设置 DORA_CONFIG_PATH 环境变量或确保配置文件位于默认位置。"
            )

        with open(config_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        # 替换环境变量占位符 ${ENV_VAR:default_value}
        raw_content = self._substitute_env_vars(raw_content)

        self.cfg = yaml.safe_load(raw_content) or {}

    def _substitute_env_vars(self, content: str) -> str:
        """
        替换配置文件中的环境变量占位符

        支持格式：${ENV_VAR_NAME} 或 ${ENV_VAR_NAME:default_value}

        Args:
            content: 原始配置文件内容

        Returns:
            替换后的配置内容
        """
        pattern = re.compile(r"\$\{([^}:]+)(?::([^}]*))?\}")

        def replace_match(match: re.Match) -> str:
            env_var = match.group(1)
            default_value = match.group(2) or ""
            return os.environ.get(env_var, default_value)

        return pattern.sub(replace_match, content)

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项，支持点号分隔的嵌套访问

        Args:
            key: 配置键名，支持 "a.b.c" 格式访问嵌套配置
            default: 默认值，键不存在时返回

        Returns:
            配置值
        """
        keys = key.split(".")
        value = self.cfg

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def reload(self) -> None:
        """重新加载配置文件"""
        self._initialized = False
        self._initialized = True
        self._load_config()


# 全局配置实例
global_cfg = Config()
